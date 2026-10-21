"""Esquemas Pydantic (v2) del feature Percepción (respuestas del dashboard)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class Distribucion(BaseModel):
    positivo: int = 0
    neutral: int = 0
    negativo: int = 0


class ResumenPercepcion(BaseModel):
    """Tarjeta principal del dashboard: el número grande + contexto."""

    indice_actual: float | None = None      # índice del día más reciente [0..100]
    indice_promedio: float | None = None     # promedio ponderado por volumen en la ventana
    tendencia: float | None = None           # delta reciente (últimos 7d vs 7d previos)
    n_comentarios: int = 0
    confianza_promedio: float | None = None  # [0..1]
    distribucion: Distribucion = Distribucion()
    fecha_desde: date | None = None
    fecha_hasta: date | None = None
    hay_datos: bool = False


class PuntoEvolucion(BaseModel):
    fecha: date
    indice: float | None = None
    confianza: float | None = None
    n_comentarios: int = 0
    # La marca viene de la detección SEMANAL, que corre sobre otra serie: se
    # dibuja suave y se detecta crudo. Cada día hereda el veredicto de SU semana.
    es_anomalia: bool = False
    severidad: float = 0.0
    motivos: list[str] = []


class SerieEvolucion(BaseModel):
    nivel: str
    dimension: str | None = None
    puntos: list[PuntoEvolucion] = []


class UnidadComparacion(BaseModel):
    nombre: str
    indice_promedio: float | None = None
    n_comentarios: int = 0
    confianza_promedio: float | None = None


class ComparacionUnidades(BaseModel):
    nivel: str
    unidades: list[UnidadComparacion] = []


class TemaItem(BaseModel):
    tema: str
    etiqueta: str
    indice_promedio: float | None = None
    confianza_promedio: float | None = None
    n_comentarios: int = 0
    n_pos: int = 0
    n_neu: int = 0
    n_neg: int = 0


class ComparacionTemas(BaseModel):
    temas: list[TemaItem] = []


class EmocionItem(BaseModel):
    emocion: str
    etiqueta: str
    n: int


class EmocionesResponse(BaseModel):
    items: list[EmocionItem] = []


class EmocionDominante(BaseModel):
    emocion: str
    etiqueta: str
    n: int
    pct: float          # % dentro de su tema/área, no del total global


class AreaBreve(BaseModel):
    nombre: str
    n_comentarios: int


class TemaDominante(BaseModel):
    tema: str
    etiqueta: str
    n_comentarios: int


class PalabraDestacada(BaseModel):
    """Una palabra del vocabulario con su carga de sentimiento.

    El vocabulario se valida sobre TODO el período y NO por área: es lo único que
    separa las palabras reales de los handles de personas que el tokenizador no
    atrapa (son letras puras, sin "_" ni dígitos). Se probaron heurísticas por
    publicaciones y por autores distintos: las dos fallaron. Ver la nota anti-PII
    en `repository`.
    """

    texto: str
    n: int = 0                       # en cuántos COMENTARIOS aparece
    n_pos: int = 0
    n_neu: int = 0
    n_neg: int = 0
    pct_neg: float = 0.0


class SintesisTema(BaseModel):
    """Una fila de "de qué hablan": volumen, cómo se siente y dónde se concentra."""

    tema: str
    etiqueta: str
    n_comentarios: int
    share_pct: float                        # peso del tema en la conversación
    indice: float | None = None
    confianza: float = 0.0
    # n < n_min_evidencia => el índice es anecdótico. El front DEBE marcarlo:
    # sin esto, una fila de 7 comentarios se lee igual que una de 88.
    evidencia_suficiente: bool = False
    n_pos: int = 0
    n_neu: int = 0
    n_neg: int = 0
    emocion_dominante: EmocionDominante | None = None
    areas_top: list[AreaBreve] = []
    # Qué se DICE literalmente en este tema (vocabulario validado global).
    palabras_top: list[PalabraDestacada] = []


class PosturaTramo(BaseModel):
    postura: str
    etiqueta: str
    n: int
    pct: float


class SintesisArea(BaseModel):
    """Una fila de "cómo está cada unidad": índice, de qué se habla y con qué emoción."""

    nombre: str
    n_comentarios: int
    share_pct: float
    indice: float | None = None
    confianza: float = 0.0
    evidencia_suficiente: bool = False
    n_pos: int = 0
    n_neu: int = 0
    n_neg: int = 0
    tema_dominante: TemaDominante | None = None
    emocion_dominante: EmocionDominante | None = None
    # Reparto favorable / sin postura / adverso de la unidad. None cuando no hay
    # comentarios: unos ceros dibujarían una barra vacía que parece un dato.
    postura: list[PosturaTramo] | None = None
    # Qué se DICE literalmente en esta unidad. Vacío cuando ninguna de sus
    # palabras alcanza el mínimo GLOBAL — que es justamente el resguardo que
    # impide publicar el nombre de una persona en un departamento chico.
    palabras_top: list[PalabraDestacada] = []


class SintesisCambio(BaseModel):
    """Un tema que SE MOVIÓ respecto del período anterior.

    Reemplaza a los "focos por umbral fijo": con el índice < 50 el bloque quedó
    vacío apenas se corrigió la clasificación, y "lo más hablado" repite siempre
    los mismos temas. Lo informativo es la variación.
    """

    tema: str
    etiqueta: str
    n_comentarios: int
    n_anterior: int = 0
    delta_volumen_pct: float | None = None  # None = sin base previa (tema nuevo)
    indice: float | None = None
    indice_anterior: float | None = None
    delta_indice: float | None = None
    evidencia_suficiente: bool = False
    emocion_dominante: EmocionDominante | None = None
    es_nuevo: bool = False


class SintesisPeriodo(BaseModel):
    desde: date
    hasta: date
    dias: int


class SintesisPeriodoSimple(BaseModel):
    """Ventana previa contra la que se comparan los cambios."""

    desde: date
    hasta: date


class CoberturaArea(BaseModel):
    """Qué parte de la conversación tiene la dimensión de área atribuida. Sin este
    dato, el corte por área se lee como si cubriera el total (no lo hace)."""

    n_con_area: int = 0
    n_total: int = 0
    pct: float = 0.0


class SintesisGlobal(BaseModel):
    n_comentarios: int = 0
    indice: float | None = None
    confianza: float = 0.0
    distribucion: Distribucion = Distribucion()
    emocion_dominante: EmocionDominante | None = None


class SintesisResponse(BaseModel):
    """Capa 1 (determinista) del resumen ejecutivo. La narración en lenguaje
    natural (capa 2) se genera en la ingesta del worker CONSUMIENDO esta salida,
    para que las cifras del tablero nunca dependan de un LLM."""

    hay_datos: bool = False
    periodo: SintesisPeriodo | None = None
    # `global` es palabra reservada en Python, así que el campo se llama `global_`
    # y viaja como "global" en el JSON vía alias. FastAPI serializa con
    # by_alias=True por defecto, y populate_by_name deja construirlo con
    # cualquiera de los dos nombres (el repository devuelve la clave "global").
    global_: SintesisGlobal | None = Field(default=None, alias="global")
    nivel_area: str = "facultad"
    orden: str = "peor"
    tema_filtrado: str | None = None    # el filtro global de tema aplica a áreas/focos
    cobertura_area: CoberturaArea = CoberturaArea()
    temas: list[SintesisTema] = []
    areas: list[SintesisArea] = []
    cambios: list[SintesisCambio] = []
    periodo_anterior: SintesisPeriodoSimple | None = None
    n_min_evidencia: int = 30

    model_config = {"populate_by_name": True}


class PalabraNube(BaseModel):
    """Una palabra del corpus con su frecuencia y el desglose de los comentarios
    donde aparece. Trae las tres dimensiones (sentimiento/tema/emoción) para que
    el front pueda cambiar el criterio de color sin volver a pedir datos."""

    texto: str
    n: int                              # en cuántos COMENTARIOS aparece (no veces)
    pos: int = 0
    neu: int = 0
    neg: int = 0
    sentimiento_dominante: str = "NEU"
    tema_dominante: str | None = None
    tema_etiqueta: str | None = None
    emocion_dominante: str | None = None
    emocion_etiqueta: str | None = None
    variantes: list[str] = []           # otras formas fundidas acá (p.ej. "curso")


class NubePeriodo(BaseModel):
    desde: date | None = None
    hasta: date | None = None


class NubeResponse(BaseModel):
    hay_datos: bool = False
    palabras: list[PalabraNube] = []
    n_comentarios: int = 0
    n_palabras_unicas: int = 0
    min_frecuencia: int = 2
    agrupar_variantes: bool = True
    n_variantes_agrupadas: int = 0      # cuántas formas se fundieron en otra
    truncado: bool = False              # se alcanzó el tope de comentarios
    periodo: NubePeriodo | None = None


# --------------------------------------------------------------------------- #
# Palabras destacadas — el vocabulario que PESA, no el que más se repite.
# --------------------------------------------------------------------------- #
class MesSerie(BaseModel):
    mes: date                        # día 1 del mes
    indice: float | None = None
    n_comentarios: int = 0


class EmocionCambio(BaseModel):
    """La emoción que más ganó terreno contra el período anterior.

    Se compara el SHARE, no el conteo: si el volumen total se duplica, todas
    "crecen" y no se aprendió nada.
    """

    emocion: str
    etiqueta: str
    n: int = 0
    pct: float = 0.0                 # participación en el período actual
    pct_anterior: float = 0.0
    delta_pp: float = 0.0            # variación en PUNTOS PORCENTUALES
    es_nueva: bool = False           # no aparecía en el período anterior


class PublicacionDominante(BaseModel):
    """Una publicación y cuánto de la conversación del período concentra."""

    publicacion_id: int
    cuenta: str | None = None
    cuenta_tipo: str | None = None
    n_comentarios: int = 0
    # Cuánto de la muestra del período es ESTA publicación. Es el dato que decide
    # si el promedio del período significa algo o si hay que leer caso por caso.
    pct_del_periodo: float = 0.0
    indice: float | None = None
    pct_neg: float | None = None
    desde: date | None = None
    hasta: date | None = None


class PublicacionesDominantesResponse(BaseModel):
    """De qué se habló: las publicaciones que concentran la conversación.

    Existe porque en las seis caídas que revisó la auditoría de sept-2026, la
    explicación salió siempre del mismo lugar: qué publicación juntaba los
    comentarios. El caso testigo es Fiestas Patrias, donde 128 de 161 comentarios
    (79,5 %) venían de dos publicaciones del mismo sorteo.
    """

    items: list[PublicacionDominante] = []
    n_comentarios: int = 0
    n_publicaciones: int = 0
    # Proporción que junta la publicación MÁS grande. Por encima de ~40 % el
    # promedio del período describe a esa publicación, no a la comunidad.
    concentracion: float | None = None


class DestacadosResponse(BaseModel):
    """Lo que el Resumen muestra de un vistazo, en una sola llamada. Son tres
    cosas que NO están en ninguna otra pestaña, para no repetir."""

    palabras: list[PalabraDestacada] = []
    serie_mensual: list[MesSerie] = []
    emocion_cambio: EmocionCambio | None = None
    vocabulario_min: int = 10
    periodo_anterior: SintesisPeriodoSimple | None = None


# --------------------------------------------------------------------------- #
# Términos bajo vigilancia — el léxico de conflicto, contado aparte.
# --------------------------------------------------------------------------- #
class TerminoTema(BaseModel):
    tema: str
    etiqueta: str
    n: int = 0


class TerminoSemana(BaseModel):
    semana: date                     # lunes
    n: int = 0
    n_neg: int = 0


class TerminoEjemplo(BaseModel):
    """Ficha de un comentario que disparó la familia: solo etiquetas, SIN texto ni autor.

    El texto crudo solo sale por la curación (admin, auditada). Acá queda la ficha
    para dimensionar el caso: cuándo, con qué ánimo y en qué tema.
    """

    fecha: date
    sentimiento: str
    sentimiento_label: str
    emocion: str | None = None
    emocion_label: str | None = None
    tema: str | None = None
    tema_label: str | None = None


class TerminoFamilia(BaseModel):
    clave: str
    etiqueta: str
    n_menciones: int = 0
    # El HUMOR se separa, no se descarta: RoBERTuito detecta ironía mal y un
    # "jajaja paro" puede ser sarcasmo amargo. Sale del cálculo del índice y de
    # la detección de anomalías, pero se muestra.
    n_serio: int = 0
    n_humor: int = 0
    n_pos: int = 0
    n_neu: int = 0
    n_neg: int = 0
    indice: float | None = None      # de los SERIOS: con qué ánimo se habla de esto
    share_pct: float = 0.0
    temas: list[TerminoTema] = []    # dónde se está hablando de esto
    primera_mencion: date | None = None
    ultima_mencion: date | None = None
    n_anterior: int = 0
    delta_menciones_pct: float | None = None   # None = sin base previa
    es_nuevo: bool = False
    serie_semanal: list[TerminoSemana] = []
    ejemplos: list[TerminoEjemplo] = []


class TerminosGlobal(BaseModel):
    n_comentarios: int = 0
    n_con_termino: int = 0
    pct: float = 0.0
    n_humor: int = 0


class TerminosResponse(BaseModel):
    """Menciones del léxico crítico en el período.

    NO interviene en el índice canónico: la fórmula acordada con la DAI queda
    intacta y comparable con lo ya reportado.
    """

    hay_datos: bool = False
    periodo: SintesisPeriodoSimple | None = None
    global_: TerminosGlobal | None = Field(default=None, alias="global")
    familias: list[TerminoFamilia] = []
    periodo_anterior: SintesisPeriodoSimple | None = None

    model_config = {"populate_by_name": True}


class EventoItem(BaseModel):
    # `id` y `tipo_label` los necesita el ABM del panel (editar/borrar y mostrar el
    # nombre legible del tipo). Opcionales: el overlay del gráfico no los usa.
    id: int | None = None
    nombre: str
    tipo: str
    tipo_label: str | None = None
    fecha_inicio: date
    fecha_fin: date
    descripcion: str | None = None
    ambito: str | None = None
    # confirmado | estimado | planificado. NULL en eventos cargados a mano antes de
    # que existiera la columna; se lee como `estimado`, que es lo conservador.
    confianza: str | None = None


class EventosResponse(BaseModel):
    items: list[EventoItem] = []


class TipoEventoOpcion(BaseModel):
    tipo: str
    etiqueta: str


class TiposEventoResponse(BaseModel):
    items: list[TipoEventoOpcion] = []


class EventoRequest(BaseModel):
    """Alta/edición de una marca de contexto. `fecha_fin` vacía = evento de un día."""
    nombre: str
    tipo: str
    fecha_inicio: date
    fecha_fin: date | None = None
    descripcion: str | None = None
    ambito: str | None = None


class EliminarEventoResponse(BaseModel):
    eliminado: bool
    id: int


class AnomaliaItem(BaseModel):
    """Un PERÍODO que se apartó de su historia reciente, con el porqué.

    La unidad es la QUINCENA por defecto —el corpus tiene mediana de 5 comentarios
    diarios, y medido sobre los 8 episodios del calendario la quincena enciende en
    los 5 evaluables contra 4 de la semana—, así que `fecha` es el lunes del bloque
    y `fecha_fin` su último día. Configurable con
    `PERCEPCION_UNIDAD_DETECCION_SEMANAS`.

    `z_score` se conserva como alias de `z_indice` por compatibilidad del contrato
    anterior.

    ⚠️ Pydantic DESCARTA lo que no está declarado acá. Un campo que el repositorio
    devuelva y este modelo no liste no llega al frontend y no hay error en ningún
    lado: el tipo de TypeScript compila, el test unitario del repositorio pasa, y
    el dato simplemente no está. Ya ocurrió con `nivel_alerta` y `fecha_fin`.
    """

    fecha: date
    # Último día del bloque. Mostrar solo el lunes hace leer la alarma como si
    # fuera de ese día, cuando representa dos semanas.
    fecha_fin: date | None = None
    nivel: str
    dimension: str | None = None
    indice: float | None = None
    z_score: float | None = None
    # Por qué se marcó: "terminos" | "indice" | "negatividad". Sin esto el
    # directivo ve una alerta y no sabe qué mirar.
    motivos: list[str] = []
    severidad: float = 0.0           # 0..1, graduada: no todo lo marcado pesa igual
    z_indice: float | None = None
    z_pct_neg: float | None = None
    pct_neg: float | None = None
    n_comentarios: int = 0
    n_terminos: int = 0              # menciones críticas serias de la semana
    n_terminos_neg: int = 0          # de esas, las negativas (el discriminante)
    # Los DOS NIVELES. `severidad` dice cuánto se apartó el período; `nivel_alerta`
    # dice qué hacer con eso: "atencion" cubre (sube la negatividad, para MIRAR) y
    # "alerta" acierta (alguien nombra paro/toma/asamblea, para AVISAR). El ÍNDICE
    # no enciende ninguno — durante un conflicto recibe apoyo y reclamo en el mismo
    # post y el promedio los cancela.
    nivel_alerta: str | None = None
    # Horizonte MEDIDO del nivel, no una predicción de este período. Sin él, "hay
    # una alerta" no se puede accionar: lo que decide actuar es "suele avisar con
    # un mes".
    lead_esperado_dias: int | None = None
    lead_rango_dias: list[int] | None = None
    cobertura_medida: list[int] | None = None   # [tomados, evaluables]


class AnomaliasMedicion(BaseModel):
    """Rendimiento MEDIDO de la configuración activa, sobre los 4 años de historia."""

    detecta: int
    evaluables: int
    falsas_anio: float
    precision: float                 # 0..1
    lead_mediano: int                # días


class AnomaliasConfig(BaseModel):
    """Cómo está configurada la detección, y qué se midió con ESA configuración.

    Viaja con los datos porque `unidad_semanas` es ajustable por entorno y cambia
    lo que se ve. Sin declararla, dos personas con distinta configuración leen
    números distintos y ninguna sabe por qué.

    `medicion` es None cuando la unidad activa no tiene calibración propia (solo se
    midieron 1 y 2 semanas). En ese caso el panel dice que no hay medición, en vez
    de mostrar el rendimiento de una configuración que el lector no está mirando.
    """

    unidad_semanas: int
    baseline_semanas: int
    min_comentarios: int
    medicion: AnomaliasMedicion | None = None


class AnomaliasResponse(BaseModel):
    items: list[AnomaliaItem] = []
    config: AnomaliasConfig | None = None


class ComentarioReciente(BaseModel):
    """Ficha de un comentario que afecta la percepción: SOLO etiquetas, sin texto ni autor."""

    id: int
    fecha: date
    sentimiento: str                 # POS | NEU | NEG
    sentimiento_label: str
    neto: float                      # prob_pos − prob_neg, en [-1, 1]
    n_likes: int = 0
    tema: str | None = None
    tema_label: str | None = None
    emocion: str | None = None       # joy/anger/sadness/… del modelo
    emocion_label: str | None = None
    unidad: str | None = None        # facultad/departamento/campus de la cuenta
    cuenta: str | None = None        # nombre de la cuenta pública (no una persona)
    cuenta_tipo: str | None = None   # institucional | facultad | …
    impacto: float = 0.0             # |neto| · peso_likes
    subtema: int | None = None       # id en percepcion_subtema (agrupación local), si existe
    subtema_label: str | None = None  # etiqueta anonimizada del subtema


class ComentariosResponse(BaseModel):
    items: list[ComentarioReciente] = []


class TemaOpcion(BaseModel):
    tema: str
    etiqueta: str


class PublicacionCurar(BaseModel):
    id: int
    caption: str
    cuenta: str | None = None
    n_comentarios: int = 0
    n_otros: int = 0


class PublicacionesCurarResponse(BaseModel):
    items: list[PublicacionCurar] = []


class ComentarioCurar(BaseModel):
    id: int
    texto: str
    fecha: date
    sentimiento: str
    caption: str
    cuenta: str | None = None


class ComentariosCurarResponse(BaseModel):
    items: list[ComentarioCurar] = []


class TemaAsignable(BaseModel):
    tema: str
    etiqueta: str


class TemasAsignablesResponse(BaseModel):
    items: list[TemaAsignable] = []


class AsignarTemaRequest(BaseModel):
    tema: str


class CrearTemaRequest(BaseModel):
    etiqueta: str
    keywords: list[str] = []


class ComentarioScoring(BaseModel):
    id: int
    texto: str
    fecha: date
    sentimiento: str
    sentimiento_label: str
    emocion: str | None = None
    emocion_label: str | None = None
    tema: str | None = None
    # Confianza del clasificador de temas (matcher de keywords). Mediana del corpus
    # 0,45 y 89,5% por debajo de 0,7: verlo al revisar es lo que permite juzgar si
    # esa confianza significa algo.
    tema_confianza: float = 0.0
    cuenta: str | None = None
    # El post al que responde el comentario. Con mediana de 3 palabras en el corpus,
    # un comentario aislado no es clasificable: "no yapo" necesita saber a qué.
    caption: str = ""
    # Ventaja de la clase ganadora sobre la segunda: cuanto más chica, más dudó
    # el modelo. Es el criterio de orden por defecto de la cola de revisión.
    margen: float = 0.0
    prob_pos: float = 0.0
    prob_neu: float = 0.0
    prob_neg: float = 0.0
    # Por qué el comentario sigue en la cola (None = nunca se revisó).
    motivo_pendiente: str | None = None


class ConcentracionTema(BaseModel):
    tema: str
    etiqueta: str
    n: int
    # Gini de la PREVALENCIA del tema entre unidades. Viaja para poder auditarlo,
    # pero NO se muestra: «0,70» no le dice nada a quien tiene que decidir algo.
    # Lo que se muestra es `reparto` y la comparación top vs promedio.
    gini: float
    reparto: str
    concentrado: bool
    unidad_top: str
    prevalencia_top: float
    prevalencia_media: float
    veces_sobre_promedio: float | None = None
    unidades_con_presencia: int = 0


class ConcentracionResponse(BaseModel):
    """¿Cada tema es de una unidad o de toda la universidad?

    `cobertura_pct` NO es decoración: solo un tercio de los comentarios tiene
    facultad, así que esto describe la conversación DE LAS UNIDADES y hay que
    decirlo en pantalla."""
    hay_datos: bool = False
    motivo: str | None = None
    nivel: str = "facultad"
    items: list[ConcentracionTema] = []
    unidades: int = 0
    n_comentarios: int = 0
    cobertura_pct: float = 0.0
    minimo_por_unidad: int = 0
    fecha_desde: date | None = None
    fecha_hasta: date | None = None


class PosturaTemaAdverso(BaseModel):
    tema: str
    etiqueta: str
    n: int
    pct: float


class PosturaInstitucionalResponse(BaseModel):
    """Reparto favorable / sin postura / adverso. NO es el sentimiento: el
    sentimiento es el tono, la postura es el efecto para la institución."""
    hay_datos: bool = False
    n_comentarios: int = 0
    distribucion: list[PosturaTramo] = []
    # De qué temas viene lo adverso. Es la pregunta que sigue al titular.
    temas_adversos: list[PosturaTemaAdverso] = []
    fecha_desde: date | None = None
    fecha_hasta: date | None = None


class ComentariosScoringResponse(BaseModel):
    items: list[ComentarioScoring] = []
    orden: str = "duda"
    # Progreso de la revisión manual. Va en la respuesta porque sin verlo en
    # pantalla es imposible notar que la cola dejó de traer comentarios nuevos.
    revisados: int = 0
    pendientes: int = 0


# --------------------------------------------------------------------------- #
# Calidad del modelo (A1) — lo que el scoring acierta y lo que no.
# --------------------------------------------------------------------------- #
class CalidadCelda(BaseModel):
    """Una celda de la matriz: el modelo dijo X y el revisor dijo Y, N veces."""

    modelo: str
    modelo_label: str
    revisor: str
    revisor_label: str
    n: int
    acuerdo: bool = False


class CalidadMargen(BaseModel):
    """Cuánto se corrige según lo SEGURO que estaba el modelo. Corregir mucho en el
    bucket alto es la señal fuerte: mala calibración o revisor pasado de largo."""

    bucket: str
    n: int = 0
    cambios: int = 0


class CalidadSesgo(BaseModel):
    clase: str
    clase_label: str
    n: int = 0
    de: int = 0
    proporcion: float = 0.0
    alerta: bool = False


class CalidadResumen(BaseModel):
    n: int = 0
    confirmaciones: int = 0
    cambios: int = 0
    # None (no 0.0) cuando no hay confirmaciones: el acuerdo es DESCONOCIDO, no cero.
    acuerdo: float | None = None
    acuerdo_motivo: str | None = None
    kappa: float | None = None
    matriz: list[CalidadCelda] = []
    sesgo_direccional: CalidadSesgo | None = None
    por_margen: list[CalidadMargen] = []


class CalidadGrupo(CalidadResumen):
    clave: str


class CalidadEstimacion(CalidadResumen):
    """La ÚNICA lectura válida: solo revisiones humanas sobre muestra aleatoria.

    El resumen general del campo mezcla agente y humano, y colas dirigidas con
    aleatorias; sirve para auditar el registro, no para estimar la calidad.
    """

    suficiente: bool = False


class CalidadCampo(CalidadResumen):
    estimacion: CalidadEstimacion | None = None
    por_autor: list[CalidadGrupo] = []
    por_muestra: list[CalidadGrupo] = []
    con_snapshot: int = 0


class CalidadAviso(BaseModel):
    """Advertencia metodológica que emite el servicio, no la UI: si el número no se
    puede leer solo, su límite viaja pegado."""

    nivel: str  # "critico" | "atencion"
    titulo: str
    detalle: str


class CalidadResponse(BaseModel):
    total_comentarios: int = 0
    comentarios_revisados: int = 0
    cobertura: float = 0.0
    campos: dict[str, CalidadCampo] = {}
    avisos: list[CalidadAviso] = []


class PalabraImpacto(BaseModel):
    """Cuánto movió una palabra la conversación entre dos períodos.

    `impacto` = cuánto MÁS se parecerían los dos períodos si esa palabra no
    existiera. Alto = esa palabra es la responsable de que hayan cambiado.
    """

    texto: str
    impacto: float = 0.0
    n_actual: int = 0
    n_previo: int = 0
    delta: int = 0


class ImpactoPalabrasResponse(BaseModel):
    hay_datos: bool = False
    # Coseno entre los dos períodos. 1 = idénticos. Es el punto de partida contra
    # el cual se mide cuánto aporta cada palabra.
    similitud: float | None = None
    vocabulario: int = 0
    periodo_actual: list[date] | None = None
    periodo_previo: list[date] | None = None
    palabras: list[PalabraImpacto] = []
    motivo: str | None = None


class CorreccionItem(BaseModel):
    comentario_id: int
    campo: str
    valor_original: str | None = None
    valor_nuevo: str
    justificacion: str | None = None
    autor: str | None = None
    autor_tipo: str | None = None
    origen_muestra: str | None = None
    confirmado: bool | None = None


class CorreccionesResponse(BaseModel):
    items: list[CorreccionItem] = []


class OpcionValor(BaseModel):
    valor: str
    etiqueta: str


class OpcionesScoringResponse(BaseModel):
    sentimientos: list[OpcionValor] = []
    emociones: list[OpcionValor] = []
    # Postura hacia la institución. NO es el tono: «Paro?😍» es POS y adverso.
    posturas: list[OpcionValor] = []


class CorregirRequest(BaseModel):
    valor: str
    justificacion: str = ""
    # De qué cola salió el caso. Sin esto no se puede separar después lo anotado al
    # azar (sirve para medir) de lo anotado por duda (sirve para corregir).
    origen_muestra: str | None = None


class CorregirResponse(BaseModel):
    cambiado: bool = False
    hechos: int = 0


class AsignarTemaResponse(BaseModel):
    comentarios_actualizados: int = 0
    hechos: int = 0


class FiltrosResponse(BaseModel):
    sedes: list[str] = []
    facultades: list[str] = []
    departamentos: list[str] = []
    temas: list[TemaOpcion] = []
    fecha_min: date | None = None
    fecha_max: date | None = None
    dias_span: int = 0  # antigüedad del comentario más viejo (máx del slider de rango)


# --------------------------------------------------------------------------- #
# RESUMEN SEMANAL POR LLM
# --------------------------------------------------------------------------- #
class ResumenSemanalPeriodo(BaseModel):
    desde: date
    hasta: date


class ResumenSemanalAlcance(BaseModel):
    nivel: str
    dimension: str | None = None
    etiqueta: str


class VentanaShock(BaseModel):
    etiqueta: str
    desde: date
    hasta: date
    n: int = 0
    indice: float | None = None


class EpisodioShock(BaseModel):
    """Un shock y lo que le pasó al índice. Con su evidencia declarada."""

    nombre: str
    tipo: str
    desde: date
    hasta: date | None = None
    dias: int | None = None
    ambito: str | None = None
    confianza: str = "estimado"
    # Toma y paro de un mismo conflicto se cargan por separado en el calendario, pero
    # son UN shock: acá van fusionados y las facetas quedan listadas.
    componentes: list[str] = []
    ventanas: list[VentanaShock] = []
    indice_previo: float | None = None
    indice_durante: float | None = None
    caida: float | None = None
    # Misma comparacion con la MEZCLA DE CUENTAS FIJA. Entre la ventana previa y la
    # del conflicto cambia quien comenta, no solo lo que opina: en el paro grande,
    # dos tercios de la caida cruda eran composicion.
    caida_estandarizada: float | None = None
    composicion: float | None = None
    # Las tres lecturas de la ventana del conflicto. El PONDERADO es el principal;
    # el general (`indice_durante`) queda de referencia historica.
    indice_ponderado: float | None = None
    indice_critico: float | None = None
    n_adversos: int | None = None
    pct_adversos: float | None = None
    # suficiente | parcial | insuficiente
    evidencia: str = "insuficiente"
    recuperado_en_semanas: int | None = None
    # Por qué no hay número de recuperación. «No recuperó» y «no medible» son cosas
    # distintas: la primera es un hallazgo, la segunda es falta de datos.
    motivo_recuperacion: str | None = None


class ShockResponse(BaseModel):
    episodios: list[EpisodioShock] = []
    total: int = 0
    medibles: int = 0
    n_min_por_semana: int = 0
    semanas_sosten: int = 0
    # Solo con MÁS de un caso medible. Con uno, un "rango" es ese caso disfrazado.
    caida_rango: list[float] | None = None
    avisos: list[str] = []


class BaselineModelo(BaseModel):
    nombre: str
    descripcion: str
    mae: float
    rmse: float
    n_predicciones: int = 0
    # El modelo ya llegó al ruido del propio dato: no se le puede pedir más.
    indistinguible_del_techo: bool = False
    # Erra más que decir siempre el promedio histórico.
    peor_que_no_hacer_nada: bool = False


class BaselinesResponse(BaseModel):
    """La VARA que cualquier simulación tiene que superar para integrarse."""

    semanas_con_datos: int = 0
    evaluadas: int = 0
    n_min_semana: int = 0
    # Sobre QUÉ SERIE corrió el backtesting: "ponderada" (la del tablero, default) o
    # "canonica" (conteos crudos). Se declara porque los MAE de una y otra NO son
    # comparables entre sí: distinta escala, distinto ruido, distinto techo.
    serie: str = "ponderada"
    # Piso: el ruido de muestreo del índice. Ningún modelo puede bajar de ahí.
    error_irreducible: float | None = None
    # Referencia de "no hacer nada": el desvío de la propia serie.
    desvio_serie: float | None = None
    modelos: list[BaselineModelo] = []
    avisos: list[str] = []


class UnidadVolatilidad(BaseModel):
    """Volatilidad de una unidad con el ruido de muestreo DESCONTADO."""

    nombre: str
    semanas: int = 0
    n_mediana: int = 0
    indice_medio: float | None = None
    sd_observada: float = 0.0
    sd_ruido: float = 0.0
    # None = la variación NO supera al ruido. No significa estable: significa que no
    # se puede afirmar nada. Un 0.0 acá sería una mentira.
    volatilidad_real: float | None = None
    ratio: float | None = None
    evidencia_suficiente: bool = False


class VolatilidadResponse(BaseModel):
    nivel: str
    n_min_semana: int = 0
    min_semanas: int = 0
    unidades: list[UnidadVolatilidad] = []
    # Las que no llegan al mínimo. Se exponen para que quede claro que el ranking NO
    # cubre a toda la universidad.
    sin_evidencia: list[str] = []
    avisos: list[str] = []


class SemanaDisponible(BaseModel):
    semana: date                 # lunes
    n_comentarios: int = 0
    # False = ir ahí dispara una generación (tiene costo). La UI lo avisa antes.
    tiene_resumen: bool = False


class SemanasDisponiblesResponse(BaseModel):
    semanas: list[SemanaDisponible] = []


class ResumenSemanalResponse(BaseModel):
    """Resumen narrativo de una semana, con su trazabilidad de costo.

    `desde_cache`, `modelo` y `costo_usd` viajan al front A PROPÓSITO. Un texto
    escrito por un LLM tiene que decir cuándo se generó y cuánto costó: sin eso nadie
    puede auditar el gasto ni saber si lo que está leyendo refleja los datos de ahora.
    """

    hay_datos: bool = False
    texto: str | None = None
    periodo: ResumenSemanalPeriodo | None = None
    alcance: ResumenSemanalAlcance
    n_comentarios: int = 0
    indice: float | None = None
    # True = se sirvió el texto guardado, sin llamar al modelo (no se pagó nada).
    desde_cache: bool = False
    # True = hay datos más nuevos que este texto, pero no se pudo regenerar.
    desactualizado: bool = False
    # Números del texto que NO salen de los datos de la semana. Vacío = auditable.
    # Medido: los modelos inventan una cifra cada ~10 corridas pese a tenerlo
    # prohibido en el prompt, así que se VERIFICA en vez de confiar.
    cifras_dudosas: list[str] = []
    aviso: str | None = None
    modelo: str | None = None
    costo_usd: float | None = None
    generado_en: datetime | None = None


# --------------------------------------------------------------------------- #
# B · EFECTO DE LA COMUNICACION
# --------------------------------------------------------------------------- #
class CaracteristicaComunicacion(BaseModel):
    rasgo: str
    etiqueta: str
    n_con: int = 0
    n_sin: int = 0
    tasa_con: float = 0.0
    tasa_sin: float = 0.0
    efecto_crudo: float = 0.0
    margen: float = 0.0
    # El que vale: cada cuenta comparada CONSIGO MISMA. El crudo mide quien
    # publica tanto como como publica.
    efecto_intra: float | None = None
    cuentas_comparables: int = 0
    cuentas_a_favor: int = 0
    p_signos: float | None = None
    # Supera las DOS pruebas: margen de error y control intra-cuenta.
    solido: bool = False


class ComunicacionResponse(BaseModel):
    publicaciones: int = 0
    con_conversacion: int = 0
    tasa_base: float = 0.0
    min_por_lado: int = 0
    caracteristicas: list[CaracteristicaComunicacion] = []
    avisos: list[str] = []


class RasgoAplicado(BaseModel):
    rasgo: str
    etiqueta: str
    efecto: float | None = None
    motivo: str | None = None


class RasgoElegible(BaseModel):
    rasgo: str
    etiqueta: str
    solido: bool = False
    efecto_intra: float | None = None


class EnsayoResponse(BaseModel):
    """B · «¿esta publicación va a generar conversación?» — el ensayo.

    Es lo único que quedó vivo del proyecto de simulación: la pregunta A (anticipar
    el índice) se cerró con dos evidencias y sin camino de datos.
    """

    # None cuando no hay publicaciones: una probabilidad inventada sería peor que
    # ninguna.
    probabilidad: float | None = None
    # De dónde salió el número, y NO valen lo mismo:
    #   "observado" = la tasa real de las publicaciones con esa misma combinación.
    #                 Es un dato contado.
    #   "estimado"  = tasa base + efectos de los rasgos sólidos. Asume que no
    #                 interactúan, que es una suposición.
    #   "base"      = ningún rasgo movió el número.
    fuente: str = "base"
    margen: float = 0.0
    tasa_base: float = 0.0
    n_observado: int = 0
    publicaciones: int = 0
    aplicados: list[RasgoAplicado] = []
    # Rasgos elegidos que NO movieron el número porque su efecto no se distingue del
    # azar. Se devuelven en vez de desaparecer: que no sumen es información.
    ignorados: list[RasgoAplicado] = []
    rasgos: list[RasgoElegible] = []
    avisos: list[str] = []


# --------------------------------------------------------------------------- #
# SENAL DE CONFLICTO — el volumen adverso y su robustez
# --------------------------------------------------------------------------- #
class VentanaConflicto(BaseModel):
    n: int = 0
    indice: float | None = None
    n_adversos: int = 0
    pct_adversos: float | None = None


class ComparacionConflicto(BaseModel):
    dias_previos: int
    n_previo: int = 0
    pct_adversos_previo: float | None = None
    indice_previo: float | None = None
    delta_adversos: float | None = None
    delta_indice: float | None = None
    signo: str = "igual"


class ConflictoResponse(BaseModel):
    """Volumen adverso del periodo y si su variacion resiste el cambio de ventana.

    `consistente=False` NO significa que no pase nada: significa que el resultado
    depende de con que periodo se compare, y por eso no se afirma.
    """

    hay_datos: bool = False
    periodo: ResumenSemanalPeriodo | None = None
    actual: VentanaConflicto | None = None
    comparaciones: list[ComparacionConflicto] = []
    # sube | baja | igual. None cuando el barrido no da un signo estable.
    tendencia: str | None = None
    consistente: bool = False
    delta_tipico: float | None = None
    explicacion: str | None = None
    avisos: list[str] = []


class SubtemaItem(BaseModel):
    """Un subtema: etiqueta y términos anonimizados (umbrales anti-PII), nunca texto."""

    id: int
    etiqueta: str
    terminos: list[str] = []
    n_comentarios: int = 0


class SubtemasTema(BaseModel):
    tema: str
    tema_label: str | None = None
    subtemas: list[SubtemaItem] = []


class SubtemasResponse(BaseModel):
    generado_en: datetime | None = None
    modelo: str | None = None
    temas: list[SubtemasTema] = []
