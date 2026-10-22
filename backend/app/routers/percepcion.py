"""Router del feature Percepción — dashboard filtrable de percepción de la comunidad.

Endpoints (prefijo /percepcion). ACCESO (Bóveda DAI): listas por módulo en la base de
accesos, falla cerrado. Toda lectura (GET) exige acceso al módulo ``percepcion``; todo
POST/PUT/DELETE exige además rol equipo o administrador (ver ``_exigir_acceso``).
La CURACIÓN (``/curacion/*``) es solo de ADMINISTRADORES y toda respuesta con texto crudo
de comentarios queda auditada (ver ``_auditar_texto``). Los GET son de LECTURA sobre la tabla de HECHOS que produce
el worker externo. Todos aceptan el FILTRO
global común: dias (rango), sede, facultad, departamento, tema.

  GET /filtros                      opciones disponibles para la barra de filtros
  GET /resumen                      indicador general + distribución + confianza
  GET /evolucion                    serie temporal (con anomalías)
  GET /por-tema                     comparación entre temas
  GET /por-unidad?nivel=...         comparación entre unidades (facultad/campus/departamento)
  GET /emociones                    distribución de emociones
  GET /eventos                      eventos institucionales (overlay)
  GET /anomalias                    cambios inusuales detectados

Importa app.services.percepcion.models para registrar las tablas en Base.metadata
antes de Base.metadata.create_all(...) en app/main.py.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.schemas import AuthUser
from app.services import accesos
from app.services.auth import (
    check_module_access,
    get_authenticated_user,
    require_admin,
    require_module,
)
from app.services.percepcion import (  # noqa: F401
    calidad,
    comunicacion,
    conflicto,
    curacion,
    eventos as eventos_svc,
    models,
    prediccion,
    repository,
    resumen_llm,
    schemas,
    shock,
    volatilidad,
)
from app.services.percepcion.db import (
    get_percepcion_db,
    get_percepcion_proceso_db,
    get_percepcion_write_db,
)

MODULO = "percepcion"
_METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})
_leer = require_module(MODULO)
_escribir = require_module(MODULO, write=True)

# La curación es una función de administradores: corrige el modelo comentario por
# comentario y parte de ella devuelve texto crudo.
_SOLO_ADMIN = [Depends(require_admin)]


def _exigir_acceso(request: Request, user: AuthUser = Depends(get_authenticated_user)) -> AuthUser:
    """Compuerta de TODO el router, por método HTTP (así un endpoint nuevo nace cerrado).

    * Lectura (GET/HEAD/OPTIONS): acceso al módulo ``percepcion`` (``get_authenticated_user``
      ya respondió 401 sin sesión y 403 si la cuenta no tiene acceso a nada).
    * Cualquier otro método (POST/PUT/DELETE/PATCH): rol equipo o administrador en el
      módulo. En la Torre esto no existía: cualquier sesión ``*.ucn.cl`` podía escribir
      eventos y curación.
    """
    return (_leer if request.method in _METODOS_SEGUROS else _escribir)(user)


def _auditar_texto(user: AuthUser, request: Request, ids: list[int]) -> None:
    """Deja constancia de quién vio el texto crudo de qué comentarios, y por qué endpoint.

    Se llama ANTES de devolver el texto y si no se puede registrar la petición FALLA:
    no hay texto crudo sin auditoría. Sin comentarios en la respuesta no hay nada que
    auditar.
    """
    if not ids:
        return
    try:
        accesos.get_repository().record_text_view(user.email, MODULO, request.url.path, ids)
    except accesos.AuditError as exc:
        raise HTTPException(
            status_code=503,
            detail="No se pudo registrar la auditoría; por eso no se entrega el texto de los comentarios.",
        ) from exc


router = APIRouter(
    prefix="/percepcion",
    tags=["percepcion"],
    dependencies=[Depends(_exigir_acceso)],
)


# Sesión de solo lectura sobre la base del worker (percepcion_real.db), SEPARADA
# de la operacional para no acoplar los datos reales con la seed simulada.
get_db = get_percepcion_db


# Filtro global reutilizable como dependencia (evita repetir params en cada endpoint).
class Filtro:
    def __init__(
        self,
        dias: int = Query(30, ge=1, le=36500),  # 36500 ≈ "Todo"
        sede: str | None = None,
        facultad: str | None = None,
        departamento: str | None = None,
        tema: str | None = None,
        # Control de peso del índice (dos sliders del dashboard):
        peso_likes: float = Query(1.0, ge=0.0, le=1.0),  # 0 = ignora likes, 1 = pondera full
        vida_media: int = Query(30, ge=0, le=3650),      # 0 = sin decaimiento temporal
        # Selección de la REGLA horizontal: día puntual o rango. Cuando viene, filtra
        # TODO el tablero a ese intervalo (menos la evolución, que se queda entera).
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
    ):
        self.dias = dias
        self.sede = sede
        self.facultad = facultad
        self.departamento = departamento
        self.tema = tema
        self.peso_likes = peso_likes
        self.vida_media = vida_media
        self.fecha_desde = fecha_desde
        self.fecha_hasta = fecha_hasta

    def kwargs(self) -> dict:
        """Filtro dimensional (para endpoints sin control de peso, p.ej. emociones)."""
        return {
            "dias": self.dias, "campus": self.sede, "facultad": self.facultad,
            "departamento": self.departamento, "tema": self.tema,
            "fecha_desde": self.fecha_desde, "fecha_hasta": self.fecha_hasta,
        }

    def kwargs_peso(self) -> dict:
        """Filtro dimensional + control de peso (para los que calculan índice)."""
        return {**self.kwargs(), "peso_likes": self.peso_likes,
                "vida_media": self.vida_media}


@router.get("/filtros", response_model=schemas.FiltrosResponse)
def get_filtros(db: Session = Depends(get_db)):
    return repository.filtros(db)


@router.get("/resumen", response_model=schemas.ResumenPercepcion)
def get_resumen(f: Filtro = Depends(), db: Session = Depends(get_db)):
    return repository.resumen(db, **f.kwargs_peso())


@router.get("/concentracion", response_model=schemas.ConcentracionResponse)
def get_concentracion(
    nivel: str = Query("facultad", pattern="^(facultad|departamento|campus)$"),
    f: Filtro = Depends(), db: Session = Depends(get_db),
):
    """Gini de la prevalencia de cada tema entre unidades.

    Contesta «¿es mío o es de todos?», que el tablero no podía: mostraba VOLUMEN por
    unidad, y eso confunde «este tema pesa acá» con «esta unidad comenta mucho».
    """
    return repository.concentracion_temas(db, nivel=nivel, **f.kwargs())


@router.get("/postura", response_model=schemas.PosturaInstitucionalResponse)
def get_postura(f: Filtro = Depends(), db: Session = Depends(get_db)):
    """Postura institucional: favorable / sin postura / adverso.

    Usa `kwargs()` y no `kwargs_peso()` A PROPÓSITO: acá se CUENTAN comentarios, no
    se mide temperatura. Ponderar por likes o por recencia daría un número que nadie
    puede verificar contando, y la pregunta que contesta este bloque —«cuántos
    adversos hubo»— es literalmente un conteo.
    """
    return repository.postura_institucional(db, **f.kwargs())


@router.get("/evolucion", response_model=schemas.SerieEvolucion)
def get_evolucion(f: Filtro = Depends(), db: Session = Depends(get_db)):
    kw = f.kwargs_peso()
    kw["dias"] = max(kw["dias"], 1)
    return repository.evolucion(db, **kw)


@router.get("/por-tema", response_model=schemas.ComparacionTemas)
def get_por_tema(f: Filtro = Depends(), db: Session = Depends(get_db)):
    # El desglose por tema no se filtra por tema (mostraría uno solo).
    return repository.por_tema(
        db, dias=f.dias, campus=f.sede, facultad=f.facultad, departamento=f.departamento,
        peso_likes=f.peso_likes, vida_media=f.vida_media,
        fecha_desde=f.fecha_desde, fecha_hasta=f.fecha_hasta,
    )


@router.get("/por-unidad", response_model=schemas.ComparacionUnidades)
def get_por_unidad(
    nivel: str = Query("facultad", pattern="^(facultad|campus|departamento)$"),
    f: Filtro = Depends(),
    db: Session = Depends(get_db),
):
    return repository.por_unidad(
        db, nivel=nivel, dias=f.dias, campus=f.sede, departamento=f.departamento, tema=f.tema,
        peso_likes=f.peso_likes, vida_media=f.vida_media,
        fecha_desde=f.fecha_desde, fecha_hasta=f.fecha_hasta,
    )


@router.get("/emociones", response_model=schemas.EmocionesResponse)
def get_emociones(f: Filtro = Depends(), db: Session = Depends(get_db)):
    return repository.emociones(db, **f.kwargs())


@router.get("/nube", response_model=schemas.NubeResponse)
def get_nube(
    limite: int = Query(120, ge=10, le=400),
    min_frecuencia: int = Query(2, ge=1, le=50),
    excluir: str = Query("", description="Palabras a excluir, separadas por coma"),
    agrupar_variantes: bool = Query(True, description="Fundir singular/plural en una sola palabra"),
    f: Filtro = Depends(),
    db: Session = Depends(get_db),
):
    """Nube de palabras: el vocabulario CRUDO de los comentarios del filtro.

    Complementa la síntesis — los temas son 8 categorías del clasificador; acá se
    ve qué se dice literalmente, incluso lo que todavía no tiene categoría. Cada
    palabra trae su desglose de sentimiento/tema/emoción para colorear en el front.
    """
    return repository.nube_palabras(
        db, dias=f.dias, campus=f.sede, facultad=f.facultad,
        departamento=f.departamento, tema=f.tema,
        limite=limite, min_frecuencia=min_frecuencia,
        excluir=[p for p in excluir.split(",") if p.strip()],
        agrupar_variantes=agrupar_variantes,
        fecha_desde=f.fecha_desde, fecha_hasta=f.fecha_hasta,
    )


@router.get("/sintesis", response_model=schemas.SintesisResponse)
def get_sintesis(
    nivel: str = Query("facultad", pattern="^(facultad|campus|departamento)$"),
    orden: str = Query("peor", pattern="^(peor|volumen)$"),
    f: Filtro = Depends(),
    db: Session = Depends(get_db),
):
    """Resumen ejecutivo del período: de qué se habla, con qué emoción y en qué área.

    Capa 1 (DETERMINISTA) del resumen. Devuelve los dos cortes juntos (temas y
    áreas) para que el front no cruce N endpoints a mano, más `focos` con lo
    accionable. Ignora `vida_media`: la síntesis va sin decaimiento a propósito
    (ver repository). `f.tema` aplica a áreas/focos, no al desglose por tema.
    """
    return repository.sintesis(
        db, nivel=nivel, orden=orden, dias=f.dias, campus=f.sede, facultad=f.facultad,
        departamento=f.departamento, tema=f.tema, peso_likes=f.peso_likes,
        vida_media=f.vida_media, fecha_desde=f.fecha_desde, fecha_hasta=f.fecha_hasta,
    )


@router.get("/publicaciones-dominantes",
            response_model=schemas.PublicacionesDominantesResponse)
def get_publicaciones_dominantes(
    f: Filtro = Depends(),
    limite: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """De qué se habló en el período: las publicaciones que concentran la
    conversación, con cuánto pesa cada una en la muestra."""
    return repository.publicaciones_dominantes(db, limite=limite, **f.kwargs())


@router.get("/destacados", response_model=schemas.DestacadosResponse)
def get_destacados(f: Filtro = Depends(), db: Session = Depends(get_db)):
    """Lo que el RESUMEN muestra de un vistazo, en una sola llamada.

    Tres cosas que no están en ninguna otra pestaña, para no repetir:
      * `palabras`: el vocabulario que más PESA. No el más frecuente — medido
        sobre el corpus real, el más frecuente es "felicitaciones" (121, 0%
        negativo) y sería el mismo todos los meses. Se ordena por negativos
        absolutos, que pondera volumen y carga a la vez.
      * `serie_mensual`: la silueta del índice mes a mes (la evolución diaria,
        interactiva y con eventos, vive en Conversación).
      * `emocion_cambio`: qué emoción ganó terreno contra el período anterior.
    """
    return repository.destacados(
        db, dias=f.dias, campus=f.sede, facultad=f.facultad,
        departamento=f.departamento, tema=f.tema, peso_likes=f.peso_likes,
        fecha_desde=f.fecha_desde, fecha_hasta=f.fecha_hasta,
    )


@router.get("/terminos", response_model=schemas.TerminosResponse)
def get_terminos(f: Filtro = Depends(), db: Session = Depends(get_db)):
    """Términos bajo vigilancia: paro, toma, petitorio, asamblea, movilización.

    Cuenta un léxico institucional FIJO y auditable (versionado en
    `services/percepcion/lexico.py`) que hoy queda repartido entre "académico",
    "organización estudiantil" y "otros" y por eso no se ve. Por familia devuelve
    cuántas menciones, separando lo dicho EN SERIO de lo dicho en broma, con qué
    carga, en qué temas, cómo evolucionó y unas fichas de ejemplo (etiquetas, sin texto) para auditar.

    NO toca el índice: la fórmula canónica queda intacta. Ignora `vida_media`
    (es un conteo del período, no una serie decaída), igual que `/nube`.
    """
    return repository.terminos_vigilancia(db, **f.kwargs())


@router.get("/eventos", response_model=schemas.EventosResponse)
def get_eventos(dias: int = Query(120, ge=1, le=36500), db: Session = Depends(get_db)):
    return repository.eventos(db, dias=dias)


# --------------------------------------------------------------------------- #
# ABM de marcas de contexto (eventos) — GET lectura; POST/PUT/DELETE escriben en
# la base del worker vía el engine de escritura (mismo patrón que la curación).
# --------------------------------------------------------------------------- #
@router.get("/eventos/tipos", response_model=schemas.TiposEventoResponse)
def get_eventos_tipos():
    return {"items": eventos_svc.tipos_disponibles()}


@router.get("/eventos/todos", response_model=schemas.EventosResponse)
def get_eventos_todos(db: Session = Depends(get_db)):
    # Sin ventana: es la tabla de administración del panel.
    return eventos_svc.listar(db)


@router.post("/eventos", response_model=schemas.EventoItem)
def post_evento(
    req: schemas.EventoRequest, db: Session = Depends(get_percepcion_write_db),
):
    try:
        return eventos_svc.crear(db, **req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/eventos/{evento_id}", response_model=schemas.EventoItem)
def put_evento(
    evento_id: int, req: schemas.EventoRequest,
    db: Session = Depends(get_percepcion_write_db),
):
    try:
        return eventos_svc.actualizar(db, evento_id, **req.model_dump())
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/eventos/{evento_id}", response_model=schemas.EliminarEventoResponse)
def delete_evento(evento_id: int, db: Session = Depends(get_percepcion_write_db)):
    try:
        return eventos_svc.eliminar(db, evento_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/anomalias", response_model=schemas.AnomaliasResponse)
def get_anomalias(f: Filtro = Depends(), db: Session = Depends(get_db)):
    return repository.anomalias(db, **f.kwargs_peso())


@router.get("/comentarios", response_model=schemas.ComentariosResponse)
def get_comentarios(
    f: Filtro = Depends(),
    limite: int = Query(20, ge=1, le=100),
    incluir_neutrales: bool = False,
    sentimiento: str | None = Query(None, pattern="^(POS|NEU|NEG)$"),
    emocion: str | None = None,
    db: Session = Depends(get_db),
):
    # Fichas (solo etiquetas, sin texto) de los comentarios recientes que más afectan la percepción.
    # Acota por sentimiento (POS/NEU/NEG) y/o emoción (joy/anger/…) si se piden.
    # fecha_desde/fecha_hasta llegan por el Filtro (la regla): día puntual o rango.
    return repository.comentarios_recientes(
        db, **f.kwargs(), limite=limite, incluir_neutrales=incluir_neutrales,
        sentimiento=sentimiento, emocion=emocion,
    )


@router.get("/subtemas", response_model=schemas.SubtemasResponse)
def get_subtemas(tema: str | None = None, db: Session = Depends(get_db)):
    # Subtemas agrupados por un modelo local: solo etiqueta/términos anonimizados, sin texto.
    return repository.subtemas(db, tema=tema)


# --------------------------------------------------------------------------- #
# Curación manual de temas (asignar a mano lo que quedó en "otros").
# GET = lectura; POST = escritura sobre la base del worker + reagregado.
# --------------------------------------------------------------------------- #
@router.get("/resumen-semanal", response_model=schemas.ResumenSemanalResponse)
def get_resumen_semanal(
    nivel: str = Query("campus", pattern="^(campus|facultad|global)$"),
    dimension: str | None = None,
    semana: date | None = None,
    forzar: bool = Query(False),
    db: Session = Depends(get_db),
    wdb: Session = Depends(get_percepcion_write_db),
    tdb: Session = Depends(get_percepcion_proceso_db),   # captions que se envían al modelo
    user: AuthUser = Depends(get_authenticated_user),
):
    """Resumen narrativo de UNA semana para UN alcance, escrito por el LLM.

    ⚠️ ES EL ÚNICO ENDPOINT DEL MÓDULO QUE PUEDE GASTAR PLATA, y por eso solo lo hace
    cuando los datos cambiaron: `resumen_llm` compara la huella (sha256) del paquete
    de insumos contra la guardada y, si coinciden, devuelve el texto cacheado sin
    tocar OpenAI. Así se cumple «que solo se corra al cargar los datos» sin que la
    Torre tenga que enterarse de la ingesta del worker, que corre en otro proceso.

    `semana` es cualquier día de la semana buscada (se normaliza al lunes, mismo
    ancla que toda la agregación semanal del módulo). Sin `semana`, la última CON
    DATOS — no la de hoy: si el worker se atrasa, anclar al reloj devolvería una
    semana vacía y diría "no pasó nada" cuando lo que no pasó fue la ingesta.

    `forzar=true` regenera aunque la huella coincida. Es la única vía para volver a
    pagar por los mismos datos; existe para cuando se cambia el prompt, no para uso
    normal (el botón del panel lo usa, y por eso el costo de cada corrida se guarda).
    """
    # `forzar=true` vuelve a PAGAR al modelo aunque los datos no hayan cambiado: aunque sea
    # un GET, es una acción con costo y escritura, así que queda reservada al equipo DAI.
    if forzar:
        check_module_access(user, MODULO, write=True)
    return resumen_llm.resumen_semanal(
        db, wdb, semana_inicio=semana, nivel=nivel,
        dimension=dimension, forzar=forzar, db_texto=tdb,
    )


@router.get("/conflicto", response_model=schemas.ConflictoResponse)
def get_conflicto(f: Filtro = Depends(), db: Session = Depends(get_db)):
    """Volumen adverso del período, y si su variación resiste el cambio de ventana.

    Complementa al índice con las dos cosas que un promedio no puede dar: **cuántos**
    comentarios adversos hubo (no qué proporción del promedio), y **cuánto depende el
    resultado de con qué período se lo compare**.

    Lo segundo no es un escrúpulo: sobre el episodio "Toma Campus Angamos", comparar
    contra 21 días decía que el conflicto bajaba y contra 28 decía que se triplicaba —
    porque adentro de la segunda ventana caía Fiestas Patrias. Acá se barren seis
    ventanas de 7 a 90 días y solo se afirma algo si el signo aguanta en todas.

    Usa `kwargs()` y no `kwargs_peso()` a propósito: acá se CUENTAN comentarios
    adversos, no se mide temperatura. Ponderar por likes o recencia daría un número
    que nadie puede verificar contando, y la pregunta que contesta es un conteo.
    """
    return conflicto.senal_de_conflicto(db, **f.kwargs())


@router.get("/comunicacion", response_model=schemas.ComunicacionResponse)
def get_comunicacion(db: Session = Depends(get_db)):
    """B · ¿Qué rasgos de una publicación se asocian con generar conversación?

    No predice el índice de un post —para eso harían falta muchos comentarios por
    publicación y solo 186 tienen cinco o más—. Predice algo mejor medido: si la
    publicación genera conversación o no. Ahí la muestra es 925 contra 1.769, y se
    verificó que solo 49 de los "sin comentarios" son un problema de ingesta.

    Cada rasgo se mide DOS veces: en crudo y **dentro de cada cuenta**. El segundo es
    el que vale — el crudo mide quién publica tanto como cómo publica. Un rasgo solo
    se marca `solido` si supera las dos pruebas.

    ⚠️ Es correlación, no causa, y el servicio lo dice en sus `avisos`.
    """
    return comunicacion.efecto_de_caracteristicas(db)


@router.get("/ensayo", response_model=schemas.EnsayoResponse)
def get_ensayo(
    rasgos: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
):
    """B · El ENSAYO: «¿una publicación así va a generar conversación?».

    Se describe la publicación por sus rasgos (`?rasgos=es_reel&rasgos=emojis_3_o_mas`)
    y devuelve la probabilidad de que genere conversación, con su margen.

    DOS VÍAS, y la respuesta declara cuál usó en `fuente`. Si esa combinación exacta
    de rasgos existe en el corpus con muestra suficiente se informa **la tasa
    observada** —un dato contado, no un modelo—; solo si es rara se cae a sumar los
    efectos intra-cuenta de los rasgos sólidos, que asume que no interactúan.

    ⚠️ Predice si va a haber CONVERSACIÓN, no de qué color: no dice nada sobre el
    índice ni sobre si los comentarios serán favorables. Y es correlación, no causa.
    Las dos advertencias viajan en `avisos` para que la UI no pueda omitirlas.
    """
    return comunicacion.ensayar(db, {r for r in rasgos if r})


@router.get("/shock", response_model=schemas.ShockResponse)
def get_shock(
    solo_confirmados: bool = Query(False),
    semanas_recuperacion: int = Query(12, ge=4, le=52),
    db: Session = Depends(get_db),
):
    """C · ¿Cuánto cae la percepción tras un paro y cuánto tarda en recuperarse?

    Devuelve CASOS, no un promedio: sobre el corpus hay diez episodios disruptivos
    pero la ingesta tiene volumen recién desde fines de 2024, así que la mayoría no
    tiene comentarios alrededor con los cuales medir nada. Promediar dos casos
    medibles con ocho vacíos da un número con aspecto de resultado y contenido de ruido.

    `solo_confirmados` excluye los episodios de fechas estimadas. Es lo que hay que
    usar para hablar de DURACIÓN o de velocidad de recuperación: con un término
    aproximado, esos dos números miden la suposición y no el hecho.

    NO usa el filtro global: cada episodio se mide en su propia ventana y en su propio
    ámbito (un paro de Antofagasta contra Antofagasta, no contra el índice de la UCN).
    """
    return shock.respuesta_a_shock(
        db, solo_confirmados=solo_confirmados,
        semanas_recuperacion=semanas_recuperacion)


@router.get("/baselines", response_model=schemas.BaselinesResponse)
def get_baselines(
    n_min_semana: int = Query(prediccion.N_MIN_SEMANA, ge=5, le=500),
    # Contra qué serie se valida. Default = la del tablero (ponderada por tema); con
    # False, el índice canónico de conteos crudos, que sirve de contraste histórico.
    # La respuesta declara cuál se usó — los MAE de las dos NO son comparables.
    ponderar_tema: bool = Query(prediccion.PONDERAR_TEMA_VALIDACION),
    db: Session = Depends(get_db),
):
    """La VARA de la fase 1 del plan de simulación (pregunta A).

    Backtesting walk-forward de cuatro baselines triviales sobre el índice semanal:
    persistencia, media móvil, estacionalidad y calendario. Cada semana se predice
    usando SOLO las anteriores.

    No es un pronóstico para consumir: es el piso que cualquier modelo posterior tiene
    que superar para justificar su existencia. `error_irreducible` es el ruido de
    muestreo del propio índice — nadie puede bajar de ahí, y un modelo que ya lo tocó
    no se puede mejorar por más ingenio que se le ponga.

    La serie sobre la que corre viene declarada en `serie`: por defecto la PONDERADA,
    que es la que muestra el tablero. Hasta 09-2026 la vara corría sobre la canónica
    mientras el tablero mostraba otra cosa, y eso hacía que «el modelo le ganó a la
    vara» y «el índice subió» hablaran de series distintas.

    NO usa el filtro global: la serie completa es el objeto de estudio.
    """
    return prediccion.evaluar_baselines(db, n_min=n_min_semana,
                                        ponderar_tema=ponderar_tema)


@router.get("/volatilidad", response_model=schemas.VolatilidadResponse)
def get_volatilidad(
    nivel: str = Query("facultad", pattern="^(campus|facultad|departamento)$"),
    n_min_semana: int = Query(volatilidad.N_MIN_SEMANA, ge=1, le=200),
    min_semanas: int = Query(volatilidad.MIN_SEMANAS, ge=2, le=200),
    db: Session = Depends(get_db),
):
    """¿Qué unidad se mueve de verdad y cuál solo lo parece?

    Ordena por volatilidad ESTRUCTURAL: la variación del índice semanal con el ruido
    de muestreo descontado. Sin ese descuento, el ranking mediría tamaño de muestra
    disfrazado de volatilidad — una unidad de 5 comentarios por semana oscila sola.

    NO respeta el filtro global de días a propósito: la volatilidad es una propiedad
    de la serie completa de la unidad, no de una ventana. Medirla sobre 30 días daría
    4 puntos, que no alcanzan para separar señal de ruido.

    Los umbrales son ajustables porque el corte cambia cuántas unidades entran: con
    los estrictos del módulo (30 comentarios) el ranking se queda vacío. `avisos` y
    `sin_evidencia` viajan con el dato para que la lectura no se infle.
    """
    return volatilidad.volatilidad_por_unidad(
        db, nivel=nivel, n_min_semana=n_min_semana, min_semanas=min_semanas)


@router.get("/resumen-semanal/semanas", response_model=schemas.SemanasDisponiblesResponse)
def get_resumen_semanal_semanas(
    limite: int = Query(52, ge=1, le=520),
    nivel: str = Query("global", pattern="^(campus|facultad|global)$"),
    dimension: str | None = None,
    db: Session = Depends(get_db),
):
    """Semanas navegables del bloque «Resumen semanal», de la más nueva a la más vieja.

    Solo las que tienen datos: con un selector de fechas libre, la mayoría de los
    saltos caerían en semanas sin un comentario y el usuario vería el empty-state sin
    entender por qué. `tiene_resumen` separa navegar (instantáneo y gratis) de generar
    (una llamada al modelo), para que la UI pueda avisarlo ANTES del clic.

    Es de solo lectura y no gasta un token.
    """
    return {"semanas": resumen_llm.semanas_disponibles(
        db, limite=limite, nivel=nivel, dimension=dimension)}


@router.get("/curacion/temas", dependencies=_SOLO_ADMIN, response_model=schemas.TemasAsignablesResponse)
def get_curacion_temas(db: Session = Depends(get_db)):
    return {"items": curacion.temas_asignables(db)}


@router.post("/curacion/tema", dependencies=_SOLO_ADMIN, response_model=schemas.TemaAsignable)
def post_curacion_tema(
    req: schemas.CrearTemaRequest, db: Session = Depends(get_percepcion_write_db),
):
    # Crea un tema NUEVO con keywords: asignable a mano ya, y el worker lo usará
    # para clasificar en las próximas ingestas.
    try:
        r = curacion.crear_tema_custom(db, req.etiqueta, req.keywords)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"tema": r["tema"], "etiqueta": r["etiqueta"]}


@router.get("/curacion/publicaciones", dependencies=_SOLO_ADMIN, response_model=schemas.PublicacionesCurarResponse)
def get_curacion_publicaciones(
    solo_con_otros: bool = True, db: Session = Depends(get_percepcion_proceso_db)
):
    return curacion.publicaciones_a_curar(db, solo_con_otros=solo_con_otros)


@router.get("/curacion/comentarios", dependencies=_SOLO_ADMIN, response_model=schemas.ComentariosCurarResponse)
def get_curacion_comentarios(
    request: Request, db: Session = Depends(get_percepcion_proceso_db),
    user: AuthUser = Depends(get_authenticated_user),
):
    # TEXTO CRUDO: solo administradores, y cada vista queda auditada.
    respuesta = curacion.comentarios_a_curar(db)
    _auditar_texto(user, request, [i["id"] for i in respuesta["items"]])
    return respuesta


@router.post("/curacion/publicacion/{pub_id}", dependencies=_SOLO_ADMIN, response_model=schemas.AsignarTemaResponse)
def post_curacion_publicacion(
    pub_id: int, req: schemas.AsignarTemaRequest,
    db: Session = Depends(get_percepcion_write_db),
):
    if not curacion.tema_valido(db, req.tema):
        raise HTTPException(status_code=400, detail="tema inválido")
    return curacion.asignar_tema_publicacion(db, pub_id, req.tema)


@router.post("/curacion/comentario/{com_id}", dependencies=_SOLO_ADMIN, response_model=schemas.AsignarTemaResponse)
def post_curacion_comentario(
    com_id: int, req: schemas.AsignarTemaRequest,
    db: Session = Depends(get_percepcion_write_db),
):
    if not curacion.tema_valido(db, req.tema):
        raise HTTPException(status_code=400, detail="tema inválido")
    return curacion.asignar_tema_comentario(db, com_id, req.tema)


# --- Corrección de sentimiento/emoción (dataset de aprendizaje) ---
def _email(user) -> str | None:
    if isinstance(user, dict):
        return user.get("email")
    return getattr(user, "email", None)


@router.get("/curacion/scoring/opciones", dependencies=_SOLO_ADMIN, response_model=schemas.OpcionesScoringResponse)
def get_scoring_opciones():
    return {"sentimientos": curacion.SENTIMIENTOS, "emociones": curacion.EMOCIONES,
            "posturas": list(curacion.POSTURAS)}


@router.get("/curacion/scoring", dependencies=_SOLO_ADMIN, response_model=schemas.ComentariosScoringResponse)
def get_scoring(
    request: Request,
    user: AuthUser = Depends(get_authenticated_user),
    limite: int = Query(50, ge=1, le=200),
    sentimiento: str | None = Query(None, pattern="^(POS|NEU|NEG)$"),
    emocion: str | None = None,
    orden: str = Query("duda", pattern="^(duda|reciente|aleatorio|adversos|estratificado)$"),
    solo_pendientes: bool = Query(True),
    db: Session = Depends(get_percepcion_proceso_db),
):
    """Cola de revisión manual, con órdenes que NO sirven para lo mismo.

    `duda` (default) ordena por incertidumbre del modelo: es donde el trabajo de
    revisión rinde, y justamente por eso **no sirve para medir** (la muestra está
    dirigida a donde el modelo es peor). `reciente` ordena por fecha.

    `aleatorio` toma una muestra insesgada de todo el corpus con semilla fija —
    reproducible entre revisores— y es el ÚNICO orden simple con el que se puede
    estimar la calidad real del modelo. `adversos` es su opuesto: concentra el
    trabajo donde el adverso es probable, y no sirve para estimar nada.

    `estratificado` resuelve el dilema entre esos dos. Sobremuestrea el estrato rico
    en adversos pero conserva muestra del pobre, y RE-PESANDO por el tamaño de cada
    estrato (`curacion.repesar_por_estrato`) la estimación vuelve a ser insesgada.
    Medido: llegar a 50 adversos cuesta 227 anotaciones al azar y ~105 así. Es el
    orden recomendado para destrabar el lado adverso de la regla de postura.

    `solo_pendientes` (default) saltea lo ya revisado del todo. En False devuelve
    todo, que es lo que hay que usar para AUDITAR lo anotado, no para anotar.
    """
    # TEXTO CRUDO: solo administradores, y cada vista queda auditada.
    respuesta = curacion.comentarios_para_scoring(
        db, limite=limite, sentimiento=sentimiento, emocion=emocion, orden=orden,
        solo_pendientes=solo_pendientes,
    )
    _auditar_texto(user, request, [i["id"] for i in respuesta["items"]])
    return respuesta


@router.post("/curacion/sentimiento/{com_id}", dependencies=_SOLO_ADMIN, response_model=schemas.CorregirResponse)
def post_corregir_sentimiento(
    com_id: int, req: schemas.CorregirRequest,
    db: Session = Depends(get_percepcion_write_db),
    user=Depends(get_authenticated_user),
):
    if not curacion.sentimiento_valido(req.valor):
        raise HTTPException(status_code=400, detail="sentimiento inválido")
    # Todo lo que entra por este endpoint pasó por una sesión autenticada: es una
    # persona. Los agentes escriben por script y quedan marcados como tales.
    return curacion.corregir_sentimiento(
        db, com_id, req.valor, req.justificacion, _email(user),
        autor_tipo=models.AUTOR_HUMANO, origen_muestra=req.origen_muestra,
    )


@router.post("/curacion/tema/{com_id}", dependencies=_SOLO_ADMIN, response_model=schemas.CorregirResponse)
def post_corregir_tema(
    com_id: int, req: schemas.CorregirRequest,
    db: Session = Depends(get_percepcion_write_db),
    user=Depends(get_authenticated_user),
):
    """Revisa el TEMA dejando constancia, a diferencia de `/curacion/comentario/{id}`
    que lo asigna sin registrar nada. Es lo que permite medir el clasificador de
    temas, que hoy no tiene NINGUNA evaluación."""
    if not curacion.tema_valido(db, req.valor):
        raise HTTPException(status_code=400, detail="tema inválido")
    return curacion.corregir_tema(
        db, com_id, req.valor, req.justificacion, _email(user),
        autor_tipo=models.AUTOR_HUMANO, origen_muestra=req.origen_muestra,
    )


@router.put("/curacion/subtemas/{subtema_id}", dependencies=_SOLO_ADMIN, response_model=schemas.SubtemaItem)
def put_renombrar_subtema(
    subtema_id: int, req: schemas.RenombrarSubtemaRequest,
    db: Session = Depends(get_percepcion_write_db),
    user=Depends(get_authenticated_user),
):
    """Nombre manual de un subtema (null o en blanco = volver al automático)."""
    try:
        return curacion.renombrar_subtema(db, subtema_id, req.etiqueta, _email(user), req.etiqueta_auto)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except curacion.SubtemaDesactualizado as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ProgrammingError:
        # Columnas creadas pero 003 aún no re-ejecutado: el rol de la app no tiene el UPDATE.
        db.rollback()
        raise HTTPException(status_code=503, detail="Falta otorgar permisos para renombrar subtemas "
                            "(re-ejecuta scripts/crear_roles_percepcion.py).")


@router.post("/curacion/postura/{com_id}", dependencies=_SOLO_ADMIN, response_model=schemas.CorregirResponse)
def post_corregir_postura(
    com_id: int, req: schemas.CorregirRequest,
    db: Session = Depends(get_percepcion_write_db),
    user=Depends(get_authenticated_user),
):
    """Anota la POSTURA hacia la institución, que NO es el tono.

    «Paro?😍» es positivo en tono y adverso en postura. Medido: de 141 comentarios
    sobre publicaciones de conflicto, 33 (23%) están marcados POSITIVO. Esta
    dimensión está EN OBSERVACIÓN: no toca el índice ni los hechos.
    """
    if not curacion.postura_valida(req.valor):
        raise HTTPException(status_code=400, detail="postura inválida")
    return curacion.corregir_postura(
        db, com_id, req.valor, req.justificacion, _email(user),
        autor_tipo=models.AUTOR_HUMANO, origen_muestra=req.origen_muestra,
    )


@router.post("/curacion/emocion/{com_id}", dependencies=_SOLO_ADMIN, response_model=schemas.CorregirResponse)
def post_corregir_emocion(
    com_id: int, req: schemas.CorregirRequest,
    db: Session = Depends(get_percepcion_write_db),
    user=Depends(get_authenticated_user),
):
    if not curacion.emocion_valida(req.valor):
        raise HTTPException(status_code=400, detail="emoción inválida")
    return curacion.corregir_emocion(
        db, com_id, req.valor, req.justificacion, _email(user),
        autor_tipo=models.AUTOR_HUMANO, origen_muestra=req.origen_muestra,
    )


# --------------------------------------------------------------------------- #
# Calidad del modelo (A1) — la primera métrica de "¿esto está bien?" del módulo.
# --------------------------------------------------------------------------- #
@router.get("/impacto-palabras", response_model=schemas.ImpactoPalabrasResponse)
def get_impacto_palabras(f: Filtro = Depends(), db: Session = Depends(get_db)):
    """Qué palabras movieron la conversación respecto del período anterior.

    Leave-one-out word impacts (Rieger et al., Text2Story'26 §3.2): se comparan las
    dos ventanas por su vector de conteos y se mide cuánto MÁS se parecerían sin
    cada palabra. Responde «qué cambió», no «qué se dice» — que es lo que ya
    contesta la nube.
    """
    return repository.impacto_palabras(
        db, dias=f.dias, campus=f.sede, facultad=f.facultad,
        departamento=f.departamento, tema=f.tema,
    )


@router.get("/curacion/calidad", dependencies=_SOLO_ADMIN, response_model=schemas.CalidadResponse)
def get_calidad(db: Session = Depends(get_db)):
    """Qué tan bien lee el modelo, medido contra el histórico de revisiones.

    Devuelve matriz de confusión, acuerdo, kappa de Cohen y los cortes por autor,
    por tipo de muestra y por margen original del modelo. **Trae también `avisos`
    con los límites metodológicos de cada número** (falta de confirmaciones, muestra
    sesgada, ausencia de anotación humana): el servicio los emite, la UI solo los
    muestra, para que ningún número se publique sin su advertencia.
    """
    return calidad.calidad_modelo(db)


@router.get("/curacion/correcciones", dependencies=_SOLO_ADMIN, response_model=schemas.CorreccionesResponse)
def get_correcciones(limite: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    """Historial de revisiones. `curacion.correcciones_recientes()` existía desde
    siempre y no la llamaba ningún endpoint: el trabajo de curación se guardaba y
    no lo veía nadie."""
    return curacion.correcciones_recientes(db, limite=limite)
