"""Router del módulo DAI Neural — trayectorias estudiantiles (solo lectura, solo agregados).

Endpoints (prefijo /neural). ACCESO (Bóveda DAI): todo el router exige acceso al módulo ``neural`` (rol
``lector`` basta: no hay endpoints de datos de escritura) y, salvo /aceptacion, haber aceptado la versión
vigente de la declaración de confidencialidad (403 ``aceptacion_requerida``).

  GET  /aceptacion                      texto y versión vigentes, y si la persona ya los aceptó
  POST /aceptacion                      registra la aceptación de la versión vigente (409 si es otra versión)
  GET  /programas                       programas con episodios
  GET  /programa/{cod}/cohortes         resultados y series por cohorte
  GET  /traslados/resumen               traslados entre programas: tipos, flujos y balance (todos los flujos, con su cifra)
  GET  /traslados/programa/{cod}        balance de un programa: ganados, perdidos y neto, con y sin elección
  GET  /modelos/malla-ejemplo           ramos y prerrequisitos de una malla real (sin datos de personas)
  GET  /modelos/resumen                 métricas agregadas de los benchmarks y tamaños de las arquitecturas
  GET  /modelos/tareas                  una tarjeta por tarea T1-T6: pregunta, estado, modelo conservado y veredicto
  GET  /modelos/tarea/{t}               página de una tarea: vistas, particiones, escalera, calibración y notas
  GET  /modelos/tarea/{t}/grupos        esperado frente a observado por programa, facultad, sexo, vía o tipo de colegio
  GET  /historico                       «Histórico»: bajas por semestre, quién siguió, eliminados por año y alcance (filtro de facultad o programa)
  GET  /proyeccion                      «Proyecciones»: cuántos de los estudiantes actuales se espera que sigan, egresen o queden en el umbral
  GET  /calidad                         cargas, auditoría y notas de cobertura

Las respuestas son agregadas: no hay datos por persona ni listados de personas. No se expone ``docente_key``.
Nada se oculta por tamaño: cada grupo se sirve como está en los marts y los de menos de 10 personas llevan
``pocos_casos = true`` (una marca, no un filtro).
Diseño: ``Redes/docs/07_diseno_fase3.md``.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from fastapi.routing import APIRoute
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, ProgrammingError

from app.schemas import AuthUser
from app.services.neural import aceptacion, repository as repo, rules, schemas
from app.services.neural.config import NeuralNoConfigurado
from app.services.neural.db import get_neural_conn

MODULO = "neural"
logger = logging.getLogger("boveda")


class _RutaNeural(APIRoute):
    """Traduce fallas de configuración o de la base a 503 con mensajes fijos (sin valores ni SQL)."""

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except NeuralNoConfigurado as exc:
                raise HTTPException(503, str(exc)) from exc
            except ProgrammingError as exc:
                logger.error("Neural: consulta sin tablas disponibles (%s)", type(exc.orig).__name__)
                raise HTTPException(503, "Los datos de DAI Neural aún no están construidos (marts).") from exc
            except DBAPIError as exc:
                logger.error("Neural: base no disponible (%s)", type(exc.orig).__name__)
                raise HTTPException(503, "La base de DAI Neural no está disponible.") from exc
            except repo.NoEncontrado as exc:
                raise HTTPException(404, str(exc)) from exc

        return handler


# Dos routers bajo /neural: la aceptación solo exige acceso al módulo (es lo que desbloquea el resto); todo lo
# demás exige además la aceptación vigente. ``router`` es lo que monta la app.
router_aceptacion = APIRouter(prefix="/neural", dependencies=[Depends(aceptacion.exigir_modulo)])
router_datos = APIRouter(prefix="/neural", route_class=_RutaNeural, dependencies=[Depends(aceptacion.require_aceptacion)])
router = APIRouter()  # se rellena al final del archivo, cuando ya están declaradas todas las rutas


# --------------------------------------------------------------------------- #
# Confidentiality acceptance
# --------------------------------------------------------------------------- #


@router_aceptacion.get("/aceptacion", response_model=schemas.AceptacionEstado)
def estado_aceptacion(user: AuthUser = Depends(aceptacion.exigir_modulo)):
    return {"version": aceptacion.VERSION, "texto": aceptacion.TEXTO, "aceptada": aceptacion.esta_aceptada(user.email)}


@router_aceptacion.post("/aceptacion", status_code=204)
def aceptar(cuerpo: schemas.AceptacionCuerpo, user: AuthUser = Depends(aceptacion.exigir_modulo)):
    if cuerpo.version != aceptacion.VERSION:
        raise HTTPException(409, {"codigo": "version_desactualizada", "version": aceptacion.VERSION})
    aceptacion.registrar(user.email)
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Programs
# --------------------------------------------------------------------------- #


@router_datos.get("/programas", response_model=list[schemas.ProgramaResumen])
def listar_programas(conn: Connection = Depends(get_neural_conn)):
    return repo.programas(conn)


@router_datos.get("/programa/{cod}/cohortes", response_model=schemas.CohortesPrograma)
def cohortes_programa(cod: str = Path(pattern=r"^[A-Za-z0-9_.-]{1,20}$"), conn: Connection = Depends(get_neural_conn)):
    prog = repo.programa(conn, cod)
    return {
        "cod_programa": prog["cod_programa"], "nombre_programa": prog["nombre_programa"],
        "resultados": repo.cohortes_resultado(conn, cod),
        "semestres_por_cohorte": repo.cohortes_semestre(conn, cod),
        "semestres_programa": repo.programa_semestres(conn, cod),
        "notas": [
            "Cohorte = período de admisión del episodio. Las cohortes de menos de 10 personas se muestran con la marca «pocos casos».",
            "Titulación a la duración del plan (en años, la duración del catálogo viene en semestres) y a uno y dos "
            "años más; las ventanas aún no observadas completas son censuradas (sin valor), no cero.",
            "Retención al 1.er año: con estado de matrícula en el semestre 3, o titulado/egresado.",
        ],
    }


# --------------------------------------------------------------------------- #
# Transfers between programs (P61). Aggregates only: no row, no person key; every flow is served with its count.
# --------------------------------------------------------------------------- #


def _anio() -> int | None:
    return Query(default=None, ge=1990, le=2100, description="Año en que comienza el programa de destino")


_NOTAS_TRASLADOS = [
    "Un traslado es el paso de una persona desde un episodio de pregrado a otro programa de pregrado: el siguiente "
    "episodio de la persona, que comienza entre 0 y 2 semestres regulares después del último período del origen.",
    "Elección de especialidad (Ingeniería Civil Plan Común hacia una especialidad, o ingreso por la vía ES) "
    "no es una pérdida del programa de origen. Cambio de ciclo y continuación tras egreso tampoco.",
    "Cambio de carrera, cambio de sede y otros traslados cuentan como abandono del programa de origen.",
    "No se cuentan los programas de intercambio, los ingresos IN, PE e IE, los posgrados, las superposiciones de "
    "programas ni los reingresos al mismo programa. Las transiciones ambiguas (otro programa comienza en la misma "
    "ventana) quedan fuera.",
    "Los períodos se agrupan por el año en que comienza el programa de destino.",
]


def _filtros_traslado(anio_desde, anio_hasta, tipo, solo_abandono) -> dict:
    if tipo is not None and tipo not in rules.TIPOS_TRASLADO:
        raise HTTPException(422, "Tipo de traslado desconocido.")
    if anio_desde is not None and anio_hasta is not None and anio_desde > anio_hasta:
        raise HTTPException(422, "El año inicial no puede ser posterior al final.")
    return {"desde": anio_desde, "hasta": anio_hasta, "tipo": tipo, "solo_abandono": solo_abandono}


def _eco_filtros(f: dict) -> dict:
    return {"anio_desde": f["desde"], "anio_hasta": f["hasta"], "tipo": f["tipo"], "solo_abandono": f["solo_abandono"]}


def _balance(fila: dict) -> dict:
    b = rules.balance_programa(fila["ganados"], fila["ganados_eleccion"], fila["perdidos"], fila["perdidos_eleccion"])
    return {"cod_programa": fila["cod_programa"], "nombre_programa": fila["nombre_programa"], **b}


@router_datos.get("/traslados/resumen", response_model=schemas.ResumenTraslados)
def resumen_traslados(
    anio_desde: int | None = _anio(),
    anio_hasta: int | None = _anio(),
    tipo: str | None = Query(default=None, max_length=30),
    solo_abandono: bool = Query(default=False, description="Solo los traslados que cuentan como abandono del origen"),
    conn: Connection = Depends(get_neural_conn),
):
    f = _filtros_traslado(anio_desde, anio_hasta, tipo, solo_abandono)
    por_tipo_bruto = {r["tipo"]: r["n"] for r in repo.traslados_por_tipo(conn, **f)}
    por_tipo = [{"tipo": clave, "etiqueta": meta["etiqueta"], "descripcion": meta["descripcion"],
                 "cuenta_abandono": meta["cuenta_abandono"], "n": por_tipo_bruto.get(clave, 0)}
                for clave, meta in rules.TIPOS_TRASLADO.items()]
    flujos = sorted(repo.traslados_flujos(conn, **f), key=lambda r: (-r["n"], r["cod_origen"], r["cod_destino"]))
    balance = [_balance(r) for r in sorted(repo.traslados_balance(conn, **f), key=lambda r: r["ganados"] + r["perdidos"], reverse=True)]
    return {
        "filtros": _eco_filtros(f), "anios_disponibles": repo.traslados_rango(conn), "total": sum(por_tipo_bruto.values()),
        "ambiguos_excluidos": repo.traslados_ambiguos(conn, **f), "por_tipo": por_tipo,
        "por_anio": repo.traslados_por_anio(conn, **f), "flujos": flujos, "balance": balance,
        "notas": _NOTAS_TRASLADOS + ["Se muestran todos los flujos; los de menos de 10 personas llevan la marca «pocos casos»."],
    }


@router_datos.get("/traslados/programa/{cod_programa}", response_model=schemas.TrasladosPrograma)
def traslados_programa(
    cod_programa: str = Path(pattern=r"^[A-Za-z0-9_.-]{1,20}$"),
    anio_desde: int | None = _anio(),
    anio_hasta: int | None = _anio(),
    tipo: str | None = Query(default=None, max_length=30),
    solo_abandono: bool = Query(default=False),
    conn: Connection = Depends(get_neural_conn),
):
    f = _filtros_traslado(anio_desde, anio_hasta, tipo, solo_abandono)
    prog = repo.programa_basico(conn, cod_programa)
    fila = next((r for r in repo.traslados_balance(conn, **f) if r["cod_programa"] == cod_programa),
                {"cod_programa": cod_programa, "nombre_programa": prog["nombre_programa"], "ganados": 0,
                 "ganados_eleccion": 0, "perdidos": 0, "perdidos_eleccion": 0})
    balance = _balance({**fila, "nombre_programa": prog["nombre_programa"]})

    def por_tipo(lado: str) -> list[dict]:
        bruto = {r["tipo"]: r["n"] for r in repo.traslados_programa_tipos(conn, cod_programa, lado, **f)}
        return [{"tipo": k, "etiqueta": m["etiqueta"], "n": bruto.get(k, 0)} for k, m in rules.TIPOS_TRASLADO.items()]

    anios = [{"anio": r["anio"], "ganados": r["ganados"], "perdidos": r["perdidos"], "neto": r["ganados"] - r["perdidos"]}
             for r in repo.traslados_programa_anios(conn, cod_programa, **f)]
    return {
        "cod_programa": prog["cod_programa"], "nombre_programa": prog["nombre_programa"], "filtros": _eco_filtros(f),
        "balance": balance, "entradas_por_tipo": por_tipo("entrada"), "salidas_por_tipo": por_tipo("salida"),
        "origenes": repo.traslados_programa_contrapartes(conn, cod_programa, "origenes", **f),
        "destinos": repo.traslados_programa_contrapartes(conn, cod_programa, "destinos", **f), "por_anio": anios,
        "notas": _NOTAS_TRASLADOS[:3] + ["Se muestran todas las contrapartes; las de menos de 10 personas llevan la marca «pocos casos»."],
    }


# --------------------------------------------------------------------------- #
# Models: benchmark aggregates (T1, T2, T3). There is no individual prediction anywhere in this API.
# --------------------------------------------------------------------------- #
AVISO_PREDICCIONES = ("Las predicciones individuales no están habilitadas: requieren revisión institucional y "
                      "aprobación de uso. Esta vista muestra solo métricas agregadas de los benchmarks técnicos y "
                      "explicaciones de las arquitecturas.")


@router_datos.get("/modelos/resumen", response_model=schemas.ResumenModelos)
def resumen_modelos(conn: Connection = Depends(get_neural_conn)):
    """Métricas agregadas con intervalos, comparaciones pareadas, tamaños de las arquitecturas y conclusiones.
    Se leen de ``resumen_modelos*`` (exportadas desde los resultados de los benchmarks); nunca se sirven los archivos
    de resultados ni predicciones por persona."""
    construccion = repo.modelos_construccion(conn)
    notas = ["Conjunto de prueba (cohortes más recientes, nunca usadas para entrenar ni elegir). Intervalos del 95 % por bootstrap.",
             "Una diferencia se considera real solo si su intervalo no incluye el cero."]
    if construccion is None:
        return {"disponible": False, "generado_en": None, "aviso": AVISO_PREDICCIONES, "modelos": [],
                "comparaciones": [], "arquitectura": [], "titulares": [],
                "notas": notas + ["El resumen aún no se ha exportado (tools/exportar_resumen_modelos.py)."]}
    agrupados: dict[tuple, dict] = {}
    for r in repo.modelos_metricas(conn):
        clave = (r["tarea"], r["corte_k"], r["modelo"])
        m = agrupados.setdefault(clave, {
            "tarea": r["tarea"], "corte_k": r["corte_k"], "modelo": r["modelo"], "nombre": r["modelo_nombre"],
            "familia": r["familia"], "escalon": r["escalon"], "escalon_nombre": r["escalon_nombre"],
            "n_evaluacion": r["n_evaluacion"], "metricas": {}})
        m["metricas"][r["metrica"]] = {"valor": r["valor"], "ic_inf": r["ic_inf"], "ic_sup": r["ic_sup"]}
    return {
        "disponible": True, "generado_en": construccion["construido_en"], "aviso": AVISO_PREDICCIONES,
        "modelos": list(agrupados.values()), "comparaciones": repo.modelos_comparaciones(conn),
        "arquitectura": repo.modelos_arquitectura(conn), "titulares": repo.modelos_titulares(conn), "notas": notas,
    }


@router_datos.get("/modelos/malla-ejemplo", response_model=schemas.MallaEjemplo)
def malla_ejemplo(
    cod_programa: str | None = Query(default=None, pattern=r"^[A-Za-z0-9_.-]{1,20}$"),
    semestre_max: int = Query(default=4, ge=1, le=8),
    conn: Connection = Depends(get_neural_conn),
):
    """Ejemplo real para el diagrama del grafo curricular: ramos (código, nombre, semestre) y prerrequisitos de la
    malla oficial de un programa. Es información de la malla; no contiene datos de personas."""
    datos = repo.malla_ejemplo(conn, cod_programa, semestre_max)
    notas = ["Solo códigos, nombres, semestre y créditos de la malla oficial, y sus prerrequisitos. Sin datos de personas.",
             f"Se muestran los primeros {semestre_max} semestres."]
    if not datos["nodos"]:
        notas.append("No hay una malla oficial cargada para este programa.")
    return {**datos, "notas": notas}


# --------------------------------------------------------------------------- #
# Models: one page per task (T1-T6). Same rule as above: aggregates only, never a prediction about a person.
# --------------------------------------------------------------------------- #
_TAREA = Path(pattern=r"^t[1-6]$", description="Tarea del benchmark: t1 a t6")
_VARIANTE = Query(default=None, pattern=r"^[a-z0-9_]{1,20}$", description="Variante de evaluación (T5) u horizonte (T6)")
_CORTE_K = Query(default=None, ge=0, le=20, description="Corte k del benchmark")
_NOTAS_GRUPOS = [
    "Agregados por grupo: se muestran todos, también los de menos de 10 personas, que llevan la marca «pocos casos» "
    "(sus cifras varían mucho con una persona más o menos).",
    "Cada grupo trae su tasa observada y su riesgo esperado, con intervalos del 95 %, y las métricas del modelo (AP, ROC-AUC) cuando se pueden calcular.",
    "Los nombres de facultad vienen del diccionario institucional; nunca se muestra su código.",
]
_NOTA_GRUPOS_T6 = ("En T6 cada grupo suma las unidades de validación y de prueba, y el riesgo esperado es el del modelo conservado.")


def _metrica(fila: dict | None) -> dict:
    return {"valor": fila["valor"], "ic_inf": fila["ic_inf"], "ic_sup": fila["ic_sup"]} if fila else {}


def _destacado(modelo: str | None, metricas: dict[tuple, dict], tarea: str, vista: dict, nombres: dict[tuple, str]):
    if not modelo:
        return None
    clave = (tarea, vista["variante"], vista["corte_k"], modelo)
    titular = metricas.get(clave + (vista["metrica_titular"],))
    if titular is None:
        return None
    secundaria = metricas.get(clave + (vista["metrica_secundaria"],)) if vista["metrica_secundaria"] else None
    return {"modelo": modelo, "nombre": nombres.get(clave, modelo), "metrica": _metrica(titular),
            "metrica_secundaria": _metrica(secundaria) if secundaria else None}


@router_datos.get("/modelos/tareas", response_model=schemas.ResumenTareas)
def resumen_tareas(conn: Connection = Depends(get_neural_conn)):
    """Una tarjeta por tarea (T1 a T6): pregunta, estado, modelo conservado con su métrica de prueba frente a la
    referencia y el veredicto sobre las redes. Se lee de ``resumen_tarea*``; nunca el archivo de resultados."""
    construccion = repo.modelos_construccion(conn)
    fichas = repo.tareas_fichas(conn)
    notas = ["Conjunto de prueba (cohortes más recientes, nunca usadas para entrenar ni elegir). Intervalos del 95 % por bootstrap."]
    if not fichas:
        return {"disponible": False, "generado_en": None, "aviso": AVISO_PREDICCIONES, "tareas": [],
                "notas": notas + ["El resumen por tarea aún no se ha exportado (tools/exportar_resumen_modelos.py)."]}
    vistas = {v["tarea"]: v for v in repo.tareas_vistas(conn) if v["principal"]}
    filas = repo.tareas_metricas(conn, metricas=None)
    metricas = {(m["tarea"], m["variante"], m["corte_k"], m["modelo"], m["metrica"]): m for m in filas}
    nombres = {(m["tarea"], m["variante"], m["corte_k"], m["modelo"]): m["modelo_nombre"] for m in filas}
    pruebas = {(p["tarea"], p["variante"], p["corte_k"]): p for p in repo.tareas_particiones(conn) if p["particion"] == "test"}
    tarjetas = []
    for f in fichas:
        v = vistas.get(f["tarea"])
        if v is None:
            continue
        prueba = pruebas.get((f["tarea"], v["variante"], v["corte_k"]))
        tarjetas.append({
            "tarea": f["tarea"], "orden": f["orden"], "nombre": f["nombre"], "pregunta": f["pregunta"], "evento": f["evento"],
            "estado": f["estado"], "estado_etiqueta": f["estado_etiqueta"], "veredicto_redes": f["veredicto_redes"],
            "metrica": v["metrica_titular"], "metrica_secundaria": v["metrica_secundaria"], "variante": v["variante"],
            "corte_k": v["corte_k"], "etiqueta_vista": v["etiqueta"], "concluyente": v["concluyente"],
            "conservado": _destacado(v["conservado_modelo"], metricas, f["tarea"], v, nombres),
            "referencia": _destacado(v["referencia_modelo"], metricas, f["tarea"], v, nombres),
            "n_prueba": prueba["n"] if prueba else None, "tasa_prueba": prueba["tasa"] if prueba else None,
        })
    return {"disponible": True, "generado_en": construccion["construido_en"] if construccion else None,
            "aviso": AVISO_PREDICCIONES, "tareas": tarjetas, "notas": notas}


@router_datos.get("/modelos/tarea/{tarea}", response_model=schemas.DetalleTarea)
def detalle_tarea(tarea: str = _TAREA, conn: Connection = Depends(get_neural_conn)):
    """Página de una tarea: pregunta y población, vistas (corte, variante), tamaño de cada partición, escalera de
    ablación con intervalos, diferencias pareadas, calibración y notas de datos. Todo agregado."""
    ficha = repo.tarea_ficha(conn, tarea)
    agrupados: dict[tuple, dict] = {}
    for r in repo.tareas_metricas(conn, tarea):
        clave = (r["variante"], r["corte_k"], r["modelo"])
        m = agrupados.setdefault(clave, {
            "variante": r["variante"], "corte_k": r["corte_k"], "modelo": r["modelo"], "nombre": r["modelo_nombre"],
            "familia": r["familia"], "escalon": r["escalon"], "escalon_nombre": r["escalon_nombre"],
            "n_evaluacion": r["n_evaluacion"], "conservado": r["conservado"], "metricas": {}})
        m["metricas"][r["metrica"]] = {"valor": r["valor"], "ic_inf": r["ic_inf"], "ic_sup": r["ic_sup"]}
    return {
        "tarea": ficha, "aviso": AVISO_PREDICCIONES, "notas": repo.tarea_notas(conn, tarea),
        "vistas": repo.tareas_vistas(conn, tarea), "particiones": repo.tareas_particiones(conn, tarea),
        "modelos": list(agrupados.values()), "comparaciones": repo.tarea_comparaciones(conn, tarea),
        "calibracion": repo.tarea_calibracion(conn, tarea),
    }


@router_datos.get("/modelos/tarea/{tarea}/grupos", response_model=schemas.GruposTarea)
def grupos_tarea(
    tarea: str = _TAREA,
    nivel: str = Query(pattern=r"^(programa|facultad|nivel_postgrado|sexo|via|tipo_colegio)$", description="Nivel de agregación"),
    variante: str | None = _VARIANTE,
    corte: int | None = _CORTE_K,
    conn: Connection = Depends(get_neural_conn),
):
    """Esperado frente a observado por grupo (programa, facultad, sexo, vía de ingreso o tipo de colegio), como están en el mart:
    todos los grupos, con sus intervalos, y ``pocos_casos`` en los de menos de 10 personas. Sin ``variante`` ni ``corte`` se usa
    la vista principal de la tarea."""
    ficha = repo.tarea_ficha(conn, tarea)
    vistas = repo.tareas_vistas(conn, tarea)
    if variante is None or corte is None:
        base = next((v for v in vistas if v["principal"]), None)
        if base is None:
            raise repo.NoEncontrado("Esa tarea aún no tiene resultados exportados.")
        variante = base["variante"] if variante is None else variante
        corte = base["corte_k"] if corte is None else corte
    vista = next((v for v in vistas if v["variante"] == variante and v["corte_k"] == corte), None)
    if vista is None:
        raise repo.NoEncontrado("Esa combinación de variante y corte no existe para la tarea.")
    return {"tarea": tarea, "nivel": nivel, "variante": variante, "corte_k": corte, "evento": ficha["evento"],
            "pronostico_agregado": vista["pronostico_agregado"], "grupos": repo.tarea_grupos(conn, tarea, nivel, variante, corte),
            "resumen": repo.tarea_grupos_resumen(conn, tarea, nivel, variante, corte),
            "notas": _NOTAS_GRUPOS + ([_NOTA_GRUPOS_T6] if tarea == "t6" else [])}


# --------------------------------------------------------------------------- #
# View "Lo que pasó": historic results as numbers of students (aggregates, every cell as stored)
# --------------------------------------------------------------------------- #
_UCN = "Toda la UCN"


def _bloque(contenido):
    """A stored block as it is, or nothing when the document is not an object."""
    return contenido if isinstance(contenido, dict) else None


def _jerarquia(meta: dict) -> list[dict]:
    """The filters as a cascade: «Toda la UCN» first, then every faculty with its programs (code and name)."""
    filtros = [f for f in meta.get("filtros") or [] if isinstance(f, str)]
    por_fac: dict[str, list[dict]] = {f: [] for f in filtros}
    for p in meta.get("programas") or []:
        if isinstance(p, dict) and p.get("facultad") in por_fac:
            por_fac[p["facultad"]].append({"codigo": p["codigo"], "nombre": p["nombre"]})
    return [{"facultad": f, "programas": por_fac[f]} for f in filtros]


def _elegir_filtro(meta: dict, facultad: str | None, programa: str | None, vista: str) -> tuple[str, dict | None]:
    """The key of the documents to serve and, for a program, its entry in the list. 404 when it is not in the view's lists."""
    if programa is not None:
        for p in meta.get("programas") or []:
            if isinstance(p, dict) and p.get("codigo") == programa:
                return programa, {"codigo": p["codigo"], "nombre": p["nombre"], "facultad": p["facultad"]}
        raise repo.NoEncontrado(f"Ese programa no está disponible en {vista}.")
    filtro = facultad or _UCN
    if filtro not in meta.get("filtros", []):
        raise repo.NoEncontrado(f"Esa facultad no está disponible en {vista}.")
    return filtro, None


_PROGRAMA = Query(default=None, pattern=r"^[A-Za-z0-9_.-]{1,20}$", description="Código de programa; no se combina con facultad")


_BLOQUES_HISTORICO = ["semestres", "siguieron", "eliminados", "alcance", "perfil_ingreso", "primer_semestre", "ramos_reprobados",
                      "ramos_esperado", "cuellos_botella", "semestre_malla", "causales_programa"]
_NOTAS_HISTORICO = [
    "Se muestran todos los grupos y celdas; los de menos de 10 personas llevan la marca «pocos casos». No hay listas ni datos por estudiante.",
    "Los esperados vienen de los modelos conservados, evaluados sobre cohortes que no se usaron para entrenarlos.",
]


@router_datos.get("/historico", response_model=schemas.HistoricoVista)
def historico(facultad: str | None = Query(default=None, max_length=120, description="Facultad; sin valor, toda la UCN"),
              programa: str | None = _PROGRAMA, conn: Connection = Depends(get_neural_conn)):
    """Bloques de resultados ya ocurridos, contados en estudiantes: en qué semestre se pierden, cuántos siguieron,
    cuántos fueron eliminados cada año, qué habría alcanzado el apoyo guiado por el modelo y los bloques por tema. Se lee de
    ``vista_historica`` tal como está (un documento antiguo, con celdas nulas o filas «otros», también se sirve).
    ``facultad`` o ``programa`` (no ambos); un programa conocido sin un bloque devuelve ese bloque vacío."""
    if facultad is not None and programa is not None:
        raise HTTPException(status_code=422, detail="Indique una facultad o un programa, no ambos.")
    filas = repo.historico(conn, programa or facultad)
    meta = filas.get(("meta", _UCN))
    if not isinstance(meta, dict):
        return {"disponible": False, "filtro": programa or facultad or _UCN, "filtros": [_UCN], "cohortes": {}, "por_facultad": [],
                "aviso": AVISO_PREDICCIONES,
                "notas": _NOTAS_HISTORICO + ["La vista aún no se ha exportado (tools/exportar_resumen_modelos.py)."]}
    filtro, elegido = _elegir_filtro(meta, facultad, programa, "la vista")
    por_facultad = filas.get(("por_facultad", _UCN))
    vista = {b: _bloque(filas.get((b, filtro))) for b in _BLOQUES_HISTORICO}
    return {
        "disponible": True, "filtro": filtro, "programa": elegido, "filtros": meta["filtros"], "jerarquia": _jerarquia(meta),
        "modelos": meta.get("modelos") or {}, "cohortes": meta.get("cohortes") or {},
        "periodo_causales_desde": meta.get("periodo_causales_desde"),
        "modelo_t1": meta.get("modelo_t1"), "modelo_t5": meta.get("modelo_t5"),
        **vista,
        "por_facultad": por_facultad if isinstance(por_facultad, list) else [],
        "tiempo_egreso": _bloque(filas.get(("tiempo_egreso", filtro))),
        "senales": rules.campos_senales(filas.get(("senales", _UCN))),             # they describe the model, not a population:
        "esperar_semestre": rules.campos_esperar(filas.get(("esperar_semestre", _UCN))),   # the UCN content under any filter
        "aviso": AVISO_PREDICCIONES, "notas": _NOTAS_HISTORICO,
    }


# --------------------------------------------------------------------------- #
# Tab "Lo que viene": projection of the current students (always a range, always with its cut date)
# --------------------------------------------------------------------------- #
_NOTAS_PROYECCION = [
    "Se muestran todos los grupos y celdas; los de menos de 10 personas llevan la marca «pocos casos». No hay listas ni datos por estudiante.",
    "Cada proyección es un rango, no un número exacto, y indica la fecha de corte de los datos (nada posterior al cierre de ese período).",
    "La eliminación proyectada es orientativa: el reglamento de 2025 (Art. 46) cambió las reglas y los modelos se entrenaron con "
    "años anteriores; además, desde el 2.º semestre de 2024 las eliminaciones se registran con atraso (subregistro), así que lo esperado puede quedar lejos de lo que ocurra.",
]


@router_datos.get("/proyeccion", response_model=schemas.ProyeccionVista)
def proyeccion(facultad: str | None = Query(default=None, max_length=120, description="Facultad; sin valor, toda la UCN"),
               programa: str | None = _PROGRAMA, conn: Connection = Depends(get_neural_conn)):
    """Lo que viene: cuántos estudiantes actuales se espera que continúen, sean eliminados o egresen, siempre como rango y con la
    fecha de corte, más a cuántos les falta poco para el umbral del Art. 46. Se lee de ``vista_proyeccion`` tal como está.
    ``facultad`` o ``programa`` (no ambos); un programa conocido sin un bloque devuelve ese bloque vacío."""
    if facultad is not None and programa is not None:
        raise HTTPException(status_code=422, detail="Indique una facultad o un programa, no ambos.")
    filas = repo.proyeccion(conn, programa or facultad)
    meta = filas.get(("meta", _UCN))
    if not isinstance(meta, dict):
        return {"disponible": False, "filtro": programa or facultad or _UCN, "filtros": [_UCN], "aviso": AVISO_PREDICCIONES,
                "notas": _NOTAS_PROYECCION + ["La proyección aún no se ha exportado (tools/exportar_resumen_modelos.py)."]}
    filtro, elegido = _elegir_filtro(meta, facultad, programa, "la proyección")
    sin = (meta.get("sin_proyeccion") or {}).get("n")
    return {
        "disponible": True, "filtro": filtro, "programa": elegido, "filtros": meta["filtros"], "jerarquia": _jerarquia(meta),
        "modelos": meta.get("modelos") or {}, "corte": meta.get("corte"),
        "sin_proyeccion": {"n": sin} if sin is not None else None,
        **{b: _bloque(filas.get((b, filtro))) for b in ("continuidad", "eliminacion", "egreso", "umbral")},
        "aviso": AVISO_PREDICCIONES, "notas": _NOTAS_PROYECCION,
    }


# --------------------------------------------------------------------------- #
# Quality
# --------------------------------------------------------------------------- #
_COBERTURA = [
    "La oferta académica (secciones) existe desde 2016; antes no hay sección vinculada.",
    "Las inscripciones (ramos en curso, renuncias) cubren desde 2025 (período 202510).",
    "Las notas anteriores a 2008 no tienen estados académicos asociados; esos intentos quedan sin episodio.",
    "Las convalidaciones (DPA, CONVA, CONV/*) se tratan como avance, nunca como intento evaluado.",
    "La malla oficial no cubre todos los episodios; un episodio sin malla no tiene nodos.",
    "Este módulo no ofrece vistas a nivel de profesores.",
]


@router_datos.get("/calidad", response_model=schemas.Calidad)
def calidad(conn: Connection = Depends(get_neural_conn)):
    chequeos = repo.auditoria(conn)
    fallidos = [c for c in chequeos if not c["ok"]]
    return {
        "cargas": repo.cargas(conn),
        "auditoria": {"total": len(chequeos), "ok": len(chequeos) - len(fallidos), "fallidos": fallidos},
        "marts": repo.construccion_marts(conn),
        "cobertura": _COBERTURA,
    }


# include_router copia las rutas ya declaradas: debe ir después de todas.
router.include_router(router_aceptacion)
router.include_router(router_datos)
