"""Response models of the Neural API.

They are an allow-list: ``response_model`` drops every field not declared here, so a column added to a query can
never leak by accident. There is no RUT, name, teacher key or person-level row in any model. Nothing is hidden by size:
every group is served as stored, and a group of fewer than ``POCOS_CASOS`` people carries ``pocos_casos = True``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, model_validator

from app.services.neural.rules import pocos_casos


class ConPocosCasos(BaseModel):
    """A row (or block) about a group of people: ``pocos_casos`` is computed from its size, whatever the document carried."""

    _clave_n: ClassVar[str] = "n"
    pocos_casos: bool = False

    @model_validator(mode="before")
    @classmethod
    def _marcar(cls, datos: Any) -> Any:
        if isinstance(datos, dict):
            return {**datos, "pocos_casos": pocos_casos(datos.get(cls._clave_n))}
        return datos


# --------------------------------------------------------------------------- #
# Percentile statistics shared by the cohort and program series
# --------------------------------------------------------------------------- #
class EstadisticaComparacion(ConPocosCasos):
    _clave_n: ClassVar[str] = "n_episodios"
    n_episodios: int
    n_activos: int
    n_promedio: int
    creditos_p25: float | None = None
    creditos_p50: float | None = None
    creditos_p75: float | None = None
    promedio_p25: float | None = None
    promedio_p50: float | None = None
    promedio_p75: float | None = None


# --------------------------------------------------------------------------- #
# Programs and cohorts
# --------------------------------------------------------------------------- #
class ProgramaResumen(BaseModel):
    cod_programa: str
    nombre_programa: str | None = None
    n_episodios: int
    primera_cohorte: str | None = None
    ultima_cohorte: str | None = None


class CohorteResultado(ConPocosCasos):
    _clave_n: ClassVar[str] = "n_ingreso"
    cohorte: str
    n_ingreso: int
    duracion: int | None = None
    duracion_anios: int | None = None
    censurado_d: bool
    censurado_d1: bool
    censurado_d2: bool
    titulados_d: int | None = None
    titulados_d1: int | None = None
    titulados_d2: int | None = None
    censurado_retencion: bool
    n_retencion_obs: int | None = None
    n_retenidos: int | None = None


class CohorteSemestre(EstadisticaComparacion):
    cohorte: str
    semestre_k: int


class ProgramaSemestre(EstadisticaComparacion):
    semestre_k: int


class CohortesPrograma(BaseModel):
    cod_programa: str
    nombre_programa: str | None = None
    resultados: list[CohorteResultado]
    semestres_por_cohorte: list[CohorteSemestre]
    semestres_programa: list[ProgramaSemestre]
    notas: list[str]


# --------------------------------------------------------------------------- #
# Quality
# --------------------------------------------------------------------------- #
class CargaFuente(BaseModel):
    fuente: str
    carga_wh: datetime | None = None
    filas_origen: int | None = None
    filas_insertadas: int | None = None
    terminado_en: datetime | None = None
    estado: str


class ChequeoFallido(BaseModel):
    chequeo: str
    valor_esperado: str | None = None
    valor_obtenido: str | None = None
    explicacion: str | None = None


class ResumenAuditoria(BaseModel):
    total: int
    ok: int
    fallidos: list[ChequeoFallido]


class ConstruccionMart(BaseModel):
    mart: str
    filas: int
    construido_en: datetime
    periodo_maximo: str | None = None


class Calidad(BaseModel):
    cargas: list[CargaFuente]
    auditoria: ResumenAuditoria
    marts: list[ConstruccionMart]
    cobertura: list[str]


# --------------------------------------------------------------------------- #
# Transfers between programs (P61): aggregates only; every count is served, small ones marked «pocos casos»
# --------------------------------------------------------------------------- #
class TipoTraslado(ConPocosCasos):
    tipo: str
    etiqueta: str
    descripcion: str
    cuenta_abandono: bool
    n: int


class TrasladoAnio(ConPocosCasos):
    anio: int
    tipo: str
    n: int


class FlujoTraslado(ConPocosCasos):
    cod_origen: str
    nombre_origen: str | None = None
    cod_destino: str
    nombre_destino: str | None = None
    n: int
    tipo_principal: str | None = None


class BalancePrograma(BaseModel):
    cod_programa: str
    nombre_programa: str | None = None
    ganados_total: int
    perdidos_total: int
    neto_total: int
    ganados_sin_eleccion: int
    perdidos_sin_eleccion: int
    neto_sin_eleccion: int


class FiltrosTraslado(BaseModel):
    anio_desde: int | None = None
    anio_hasta: int | None = None
    tipo: str | None = None
    solo_abandono: bool = False


class RangoAnios(BaseModel):
    desde: int | None = None
    hasta: int | None = None


class ResumenTraslados(BaseModel):
    filtros: FiltrosTraslado
    anios_disponibles: RangoAnios
    total: int
    ambiguos_excluidos: int
    por_tipo: list[TipoTraslado]
    por_anio: list[TrasladoAnio]
    flujos: list[FlujoTraslado]
    balance: list[BalancePrograma]
    notas: list[str]


class TipoConteo(ConPocosCasos):
    tipo: str
    etiqueta: str
    n: int


class ProgramaContraparte(ConPocosCasos):
    cod_programa: str
    nombre_programa: str | None = None
    n: int


class BalanceAnio(BaseModel):
    anio: int
    ganados: int
    perdidos: int
    neto: int


class TrasladosPrograma(BaseModel):
    cod_programa: str
    nombre_programa: str | None = None
    filtros: FiltrosTraslado
    balance: BalancePrograma
    entradas_por_tipo: list[TipoConteo]
    salidas_por_tipo: list[TipoConteo]
    origenes: list[ProgramaContraparte]
    destinos: list[ProgramaContraparte]
    por_anio: list[BalanceAnio]
    notas: list[str]


# --------------------------------------------------------------------------- #
# Models: benchmark aggregates only (no individual prediction exists in the API)
# --------------------------------------------------------------------------- #
class MetricaModelo(BaseModel):
    valor: float | None = None
    ic_inf: float | None = None
    ic_sup: float | None = None


class ModeloResultado(BaseModel):
    tarea: str
    corte_k: int
    modelo: str
    nombre: str
    familia: str
    escalon: int
    escalon_nombre: str
    n_evaluacion: int | None = None
    metricas: dict[str, MetricaModelo]


class ComparacionModelos(BaseModel):
    tarea: str
    corte_k: int
    modelo_a: str
    modelo_b: str
    metrica: str
    delta: float | None = None
    ic_inf: float | None = None
    ic_sup: float | None = None
    veredicto: str


class ParametroModelo(BaseModel):
    tarea: str
    corte_k: int
    modelo: str
    clave: str
    valor_num: float | None = None
    valor_texto: str | None = None


class TitularModelos(BaseModel):
    tarea: str
    orden: int
    clave: str
    texto: str


class ResumenModelos(BaseModel):
    disponible: bool
    generado_en: datetime | None = None
    aviso: str
    modelos: list[ModeloResultado]
    comparaciones: list[ComparacionModelos]
    arquitectura: list[ParametroModelo]
    titulares: list[TitularModelos]
    notas: list[str]


class NodoMallaEjemplo(BaseModel):
    codigo: str
    nombre: str | None = None
    semestre: int
    creditos: float | None = None


class AristaMallaEjemplo(BaseModel):
    desde: str
    hacia: str


class MallaEjemplo(BaseModel):
    cod_programa: str | None = None
    nombre_programa: str | None = None
    catalogo: str | None = None
    semestre_max: int
    nodos: list[NodoMallaEjemplo]
    aristas: list[AristaMallaEjemplo]
    notas: list[str]


# --------------------------------------------------------------------------- #
# Models: per-task pages (T1-T6). Aggregates only: metrics, calibration deciles and group rates, never a person.
# --------------------------------------------------------------------------- #
class FichaTarea(BaseModel):
    tarea: str
    orden: int
    nombre: str
    pregunta: str
    poblacion: str
    evento: str
    estado: str
    estado_etiqueta: str
    veredicto_redes: str
    metrica_titular: str
    metrica_secundaria: str | None = None


class ModeloDestacado(BaseModel):
    modelo: str
    nombre: str
    metrica: MetricaModelo
    metrica_secundaria: MetricaModelo | None = None


class TarjetaTarea(BaseModel):
    tarea: str
    orden: int
    nombre: str
    pregunta: str
    evento: str
    estado: str
    estado_etiqueta: str
    veredicto_redes: str
    metrica: str
    metrica_secundaria: str | None = None
    variante: str
    corte_k: int
    etiqueta_vista: str
    concluyente: bool
    conservado: ModeloDestacado | None = None
    referencia: ModeloDestacado | None = None
    n_prueba: int | None = None
    tasa_prueba: float | None = None


class ResumenTareas(BaseModel):
    disponible: bool
    generado_en: datetime | None = None
    aviso: str
    tareas: list[TarjetaTarea]
    notas: list[str]


class NotaTarea(BaseModel):
    tipo: str
    orden: int
    texto: str


class VistaTarea(BaseModel):
    variante: str
    corte_k: int
    etiqueta: str
    principal: bool
    conservado_modelo: str | None = None
    referencia_modelo: str | None = None
    metrica_titular: str
    metrica_secundaria: str | None = None
    concluyente: bool
    pronostico_agregado: str
    nota: str | None = None


class ParticionTarea(BaseModel):
    variante: str
    corte_k: int
    particion: str
    n: int
    eventos: int | None = None
    tasa: float | None = None
    tasa_inf: float | None = None
    tasa_sup: float | None = None


class ModeloTarea(BaseModel):
    variante: str
    corte_k: int
    modelo: str
    nombre: str
    familia: str
    escalon: int
    escalon_nombre: str
    n_evaluacion: int | None = None
    conservado: bool
    metricas: dict[str, MetricaModelo]


class ComparacionTarea(BaseModel):
    variante: str
    corte_k: int
    modelo_a: str
    modelo_b: str
    metrica: str
    delta: float | None = None
    ic_inf: float | None = None
    ic_sup: float | None = None
    veredicto: str


class CalibracionTarea(ConPocosCasos):
    variante: str
    corte_k: int
    modelo: str
    decil: int
    n: int
    riesgo_medio: float | None = None
    tasa_observada: float | None = None


class DetalleTarea(BaseModel):
    tarea: FichaTarea
    aviso: str
    notas: list[NotaTarea]
    vistas: list[VistaTarea]
    particiones: list[ParticionTarea]
    modelos: list[ModeloTarea]
    comparaciones: list[ComparacionTarea]
    calibracion: list[CalibracionTarea]


class GrupoTarea(ConPocosCasos):
    """One group of a task view, as stored. The ``*_lo`` / ``*_hi`` pairs are its 95 % intervals; T6 rows add up the
    validation and test units and carry the expected risk of the kept model."""

    categoria: str
    grupo: str
    nombre: str
    facultad: str | None = None
    n: int
    eventos: int | None = None
    observada: float | None = None
    obs_inf: float | None = None
    obs_sup: float | None = None
    esperada: float | None = None
    esp_inf: float | None = None
    esp_sup: float | None = None
    referencia: float | None = None
    ap: float | None = None
    roc_auc: float | None = None
    ap_lo: float | None = None
    ap_hi: float | None = None
    auc_lo: float | None = None
    auc_hi: float | None = None
    tasa_lo: float | None = None
    tasa_hi: float | None = None
    esperado_lo: float | None = None
    esperado_hi: float | None = None


class ResumenGrupoTarea(BaseModel):
    categoria: str
    grupos_total: int | None = None
    mae_modelo: float | None = None
    mae_base: float | None = None
    spearman: float | None = None


class GruposTarea(BaseModel):
    tarea: str
    nivel: str
    variante: str
    corte_k: int
    evento: str
    pronostico_agregado: str
    grupos: list[GrupoTarea]
    resumen: list[ResumenGrupoTarea]
    notas: list[str]


# --------------------------------------------------------------------------- #
# Model shown with a conclusion (shared by the blocks of both views and by the cohorts of the projection)
# --------------------------------------------------------------------------- #
class ModeloVisible(BaseModel):
    """The kept model behind a block or a cohort: task, model, cut, partition and whether it is an expectation or a projection."""

    tarea: str
    tarea_nombre: str
    modelo: str
    modelo_nombre: str
    k: int
    corte: str
    particion: str
    tipo: str


def _modelo_o_nada(v: Any) -> ModeloVisible | None:
    """The label of a model, or ``None`` when ``v`` is not one: a bare code (documents exported before the labels existed) or a
    partial or malformed dict. It never raises: an unreadable label must not turn into a 500."""
    if isinstance(v, ModeloVisible):
        return v
    if isinstance(v, dict):
        try:
            return ModeloVisible.model_validate(v)
        except ValueError:
            return None
    return None


def _etiquetas_de(datos: dict) -> dict:
    """``modelo`` and ``modelos`` of a raw block, readable ones only, plus ``modelo_no_identificado``: True when the document
    carried a model that could not be read. The UI then shows no label at all (never «Dato observado», which is for blocks that
    genuinely have no model)."""
    bruto = datos.get("modelo")
    modelo = _modelo_o_nada(bruto)
    brutos = datos.get("modelos")
    modelos = [m for m in (_modelo_o_nada(x) for x in brutos) if m is not None] if isinstance(brutos, list) else None
    perdido = (bruto is not None and modelo is None) or (isinstance(brutos, list) and len(modelos or []) < len(brutos))
    return {**datos, "modelo": modelo, "modelos": modelos, "modelo_no_identificado": perdido}


class ConModelo(BaseModel):
    """A block with its model label. ``modelo`` is ``None`` for observed data (no model) and when ``modelos`` lists several."""

    modelo: ModeloVisible | None = None
    modelos: list[ModeloVisible] | None = None
    modelo_no_identificado: bool = False    # the document carried a model that cannot be read: no label, not «Dato observado»

    @model_validator(mode="before")
    @classmethod
    def _etiquetas(cls, datos: Any) -> Any:
        return _etiquetas_de(datos) if isinstance(datos, dict) else datos


def _mapa_modelos(datos: Any) -> Any:
    """``modelos`` of a view (block name -> label or list of labels): unreadable labels become ``None`` / are dropped."""
    if not isinstance(datos, dict) or not isinstance(datos.get("modelos"), dict):
        return datos
    limpio = {}
    for bloque, v in datos["modelos"].items():
        limpio[bloque] = [m for m in (_modelo_o_nada(x) for x in v) if m is not None] if isinstance(v, list) else _modelo_o_nada(v)
    return {**datos, "modelos": limpio}


class ProgramaFiltro(BaseModel):
    codigo: str
    nombre: str


class FacultadFiltro(BaseModel):
    """A filter of the cascade: «Toda la UCN» (no programs) or a faculty with the programs that can be picked under it."""

    facultad: str
    programas: list[ProgramaFiltro]


class ProgramaElegido(ProgramaFiltro):
    facultad: str


# --------------------------------------------------------------------------- #
# View "Lo que pasó" (historic results as numbers of students; aggregates, every cell served as stored)
# --------------------------------------------------------------------------- #
class HistSemestre(BaseModel):
    """One row of the by-semester series. Its percentages are shares of the whole cohort (``HistSemestres.n``), so the
    «pocos casos» mark is the parent's (``HistSemestres.pocos_casos``) and every row inherits it."""

    semestre: int
    dejan: int | None = None
    eliminados: int | None = None
    pct_dejan: float | None = None
    pct_eliminados: float | None = None


class HistSemestres(ConModelo, ConPocosCasos):
    n: int
    bajas: int | None = None
    bajas_primer_anio: int | None = None
    pct_bajas_primer_anio: float | None = None
    pct_bajas: float | None = None
    filas: list[HistSemestre]


class HistSiguieron(ConModelo, ConPocosCasos):
    n: int
    siguieron: int
    esperados: float
    pct_siguieron: float
    pct_esperado: float
    diferencia: float


class HistPuntoFacultad(ConPocosCasos):
    facultad: str
    n: int
    pct_siguieron: float
    pct_esperado: float


class HistAnio(ConPocosCasos):
    anio: int
    n: int
    eliminados: int
    tasa: float
    parcial: bool
    esperados: float | None = None
    tasa_esperada: float | None = None


class HistClave(BaseModel):
    anio: int
    eliminados: int


class HistTotalAnio(BaseModel):
    anio: int
    eliminados: int


class HistCausal(BaseModel):
    grupo: str
    etiqueta: str
    n: int | None = None
    pct: float | None = None


class HistCausales(BaseModel):
    total: int
    filas: list[HistCausal]


class HistEliminados(ConModelo):
    totales: list[HistTotalAnio] = []
    anios: list[HistAnio]
    anio_reglamento: int
    clave: HistClave | None = None
    causales: HistCausales | None = None


class HistPuntoCurva(BaseModel):
    apoyados: float
    alcanzados: float


class HistAlcance(ConModelo, ConPocosCasos):
    n: int
    eventos: int
    fraccion_apoyo: float
    apoyados: int
    alcanzados: int
    pct_alcanzado: float
    de_cada_10: float
    al_azar_de_cada_10: float
    curva: list[HistPuntoCurva]


class HistPerfilFila(ConPocosCasos):
    grupo: str
    etiqueta: str
    n: int
    pct_siguieron: float | None = None
    pct_esperado: float | None = None


class HistPerfilDimension(BaseModel):
    dimension: str
    filas: list[HistPerfilFila]


class HistPerfil(ConModelo, ConPocosCasos):
    n: int
    nota_asociacion: bool
    dimensiones: list[HistPerfilDimension]


class HistPrimerSemestreFila(ConPocosCasos):
    reprobaciones: str
    n: int
    pct_siguieron: float | None = None


class HistPrimerSemestre(ConModelo, ConPocosCasos):
    n: int
    nota_asociacion: bool
    filas: list[HistPrimerSemestreFila]


class HistRamoFila(BaseModel):
    codigo: str
    nombre: str
    depto: str | None = None
    intentos: int
    reprobados: int
    tasa: float
    lo: float | None = None
    hi: float | None = None


class HistRamos(ConModelo):
    desde: str
    hasta: str
    por_tasa: list[HistRamoFila]
    por_volumen: list[HistRamoFila]


class HistEsperadoCifras(BaseModel):
    intentos: int
    observados: int
    esperados: float
    diferencia: float
    lo: float
    hi: float


class HistEsperadoRamo(HistEsperadoCifras):
    codigo: str
    nombre: str


class HistEsperadoDepto(HistEsperadoCifras):
    depto: str
    depto_desc: str


class HistEsperadoVentana(BaseModel):
    desde: str
    hasta: str
    ramos: list[HistEsperadoRamo]
    deptos: list[HistEsperadoDepto]


class HistEsperado(ConModelo):
    ventanas: dict[str, HistEsperadoVentana]


class HistCuelloFila(BaseModel):
    codigo: str
    nombre: str
    reprobados: int
    dependientes: int
    impacto: int


class HistCuellos(ConModelo):
    filas: list[HistCuelloFila]


class HistSemestreMallaFila(BaseModel):
    semestre: int
    intentos: int
    reprobados: int | None = None
    tasa: float | None = None


class HistSemestreMalla(ConModelo):
    filas: list[HistSemestreMallaFila]


class HistCausalPrograma(BaseModel):
    grupo: str
    etiqueta: str
    n: int


class HistProgramaCausales(ConPocosCasos):
    _clave_n: ClassVar[str] = "total"
    cod_programa: str | None = None
    programa: str
    total: int
    causales: list[HistCausalPrograma] | None = None


class HistCausalesPrograma(ConModelo):
    desde: str
    hasta: str
    nivel: str
    filas: list[HistProgramaCausales]


class HistTiempoFila(ConPocosCasos):
    cod_programa: str
    programa: str
    n: int
    duracion_nominal_sem: int
    pct_a_tiempo: float | None = None
    pct_mas_1: float | None = None
    pct_mas_2: float | None = None


class HistTiempo(ConModelo):
    regla_duracion: str
    filas: list[HistTiempoFila]


class HistSenal(BaseModel):
    familia: str
    etiqueta: str
    peso_pct: float
    caida_ap: float


class HistSenalesTarea(BaseModel):
    tarea: str
    k: int
    modelo: str
    n_muestra: int
    senales: list[HistSenal]


class HistSenales(ConModelo):
    aplica_a_poblacion: bool = False       # the signals describe the model, not the population picked in the filter
    tareas: list[HistSenalesTarea]


class HistEsperarComparacion(BaseModel):
    tarea: str
    k_antes: int
    k_despues: int
    de_cada_10_antes: float | None = None
    de_cada_10_despues: float | None = None


class HistEsperar(ConModelo):
    aplica_a_poblacion: bool = False       # the comparison describes the model, not the population picked in the filter
    comparaciones: list[HistEsperarComparacion]
    nota_poblaciones: bool


class HistoricoVista(BaseModel):
    disponible: bool
    filtro: str                                # the key served: «Toda la UCN», a faculty or a program code
    programa: ProgramaElegido | None = None    # set when the filter is a program
    filtros: list[str]                         # «Toda la UCN» and the faculties (unchanged)
    jerarquia: list[FacultadFiltro] = []       # the same filters as a cascade: faculties with their programs
    modelos: dict[str, ModeloVisible | list[ModeloVisible] | None] = {}   # model of every block, also of those that are lists

    @model_validator(mode="before")
    @classmethod
    def _modelos_legibles(cls, datos: Any) -> Any:
        return _mapa_modelos(datos)

    cohortes: dict[str, list[int] | None]
    periodo_causales_desde: str | None = None
    modelo_t1: str | None = None
    modelo_t5: str | None = None
    semestres: HistSemestres | None = None
    siguieron: HistSiguieron | None = None
    por_facultad: list[HistPuntoFacultad]
    eliminados: HistEliminados | None = None
    alcance: HistAlcance | None = None
    perfil_ingreso: HistPerfil | None = None
    primer_semestre: HistPrimerSemestre | None = None
    ramos_reprobados: HistRamos | None = None
    ramos_esperado: HistEsperado | None = None
    cuellos_botella: HistCuellos | None = None
    semestre_malla: HistSemestreMalla | None = None
    causales_programa: HistCausalesPrograma | None = None
    tiempo_egreso: HistTiempo | None = None
    senales: HistSenales | None = None
    esperar_semestre: HistEsperar | None = None
    aviso: str
    notas: list[str]


# --------------------------------------------------------------------------- #
# Tab "Lo que viene" (projection of the current students up to the close of the cut period; always a range)
# --------------------------------------------------------------------------- #
class ProyRango(BaseModel):
    esperados: float
    lo: float
    hi: float


class ProyHito(ProyRango):
    desde: str
    hasta: str


class ProyCohorte(ProyRango, ConPocosCasos):
    """One entry of ``por_cohorte``: a cohort. A document exported before the suppression was lifted may still carry an
    «otros» entry whose model, cut and horizon are ``None``; it is served as it is."""

    @model_validator(mode="before")
    @classmethod
    def _etiqueta(cls, datos: Any) -> Any:
        return _etiquetas_de({**datos, "modelos": None}) if isinstance(datos, dict) else datos

    cohorte: int | str
    k: int | None = None
    modelo: ModeloVisible | None = None
    modelo_no_identificado: bool = False
    corte: str | None = None
    horizonte: str | None = None
    horizonte_desde: str | None = None
    n: int
    sin_historial_beneficios: int | None = None


class ProyCohorteEgreso(ConPocosCasos):
    @model_validator(mode="before")
    @classmethod
    def _etiqueta(cls, datos: Any) -> Any:
        return _etiquetas_de({**datos, "modelos": None}) if isinstance(datos, dict) else datos

    cohorte: int | str
    k: int | None = None
    modelo: ModeloVisible | None = None
    modelo_no_identificado: bool = False
    corte: str | None = None
    horizonte: str | None = None
    n: int
    nominal: ProyHito | None = None
    nominal_mas_2: ProyHito | None = None


class ProyContinuidad(ConModelo, ProyRango, ConPocosCasos):
    n: int
    por_cohorte: list[ProyCohorte]


class ProyEliminacion(ConModelo, ProyRango, ConPocosCasos):
    n: int
    por_cohorte: list[ProyCohorte]
    observados_hasta_hoy: int | None = None
    periodo_observado: str
    orientativo: bool


class ProyEgreso(ConModelo, ConPocosCasos):
    n: int
    regla: str
    nominal: ProyHito | None = None
    nominal_mas_2: ProyHito | None = None
    ya_pasado_nominal: int | None = None
    ya_pasado_nominal_mas_2: int | None = None
    horizonte_truncado: int | None = None
    por_cohorte: list[ProyCohorteEgreso]


class ProyUmbral(ConModelo, ConPocosCasos):
    """The four Art. 46 categories, always present in a current document (``None`` only in a stale one)."""

    n: int
    en_umbral: int | None = None
    a_1: int | None = None
    a_2: int | None = None
    lejos: int | None = None
    nota_p58: bool


class ProySinProyeccion(BaseModel):
    n: int


class ProyeccionVista(BaseModel):
    disponible: bool
    filtro: str                                # the key served: «Toda la UCN», a faculty or a program code
    programa: ProgramaElegido | None = None    # set when the filter is a program
    filtros: list[str]                         # «Toda la UCN» and the faculties (unchanged)
    jerarquia: list[FacultadFiltro] = []       # the same filters as a cascade: faculties with their programs
    modelos: dict[str, ModeloVisible | list[ModeloVisible] | None] = {}

    @model_validator(mode="before")
    @classmethod
    def _modelos_legibles(cls, datos: Any) -> Any:
        return _mapa_modelos(datos)

    corte: str | None = None
    sin_proyeccion: ProySinProyeccion | None = None
    continuidad: ProyContinuidad | None = None
    eliminacion: ProyEliminacion | None = None
    egreso: ProyEgreso | None = None
    umbral: ProyUmbral | None = None
    aviso: str
    notas: list[str]


class AceptacionEstado(BaseModel):
    """Current confidentiality text, its version and whether the caller already accepted it."""

    version: str
    texto: str
    aceptada: bool


class AceptacionCuerpo(BaseModel):
    version: str
