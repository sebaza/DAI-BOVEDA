"""Extraction specs: one entry per Warehouse view feeding a ``neural_stg`` table.

Only the columns declared here are ever selected. Personal columns are refused by
``assert_safe_columns`` before any query is built. The RUT (student or teacher) is
replaced by an HMAC key row by row; the raw value never leaves this module.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from ..common.pseudo import docente_key, persona_key

# ---- privacy guard ----------------------------------------------------------------------------
_FORBIDDEN_EXACT = frozenset({
    "nombre", "nombre1", "nombre2", "nombres", "apellidos", "ap_paterno", "ap_materno",
    "apellido_paterno", "apellido_materno", "nombre_social", "nombre_prof", "nombre_estud",
    "correo", "correo_ucn", "correo_personal", "telefono_fijo", "telefono_celular", "fijo", "celular",
    "fecha_nacimiento", "edad", "pasaporte", "colegio", "cod_colegio", "profesor", "etnia",
    "nacionalidad", "comuna", "cod_ciudad", "ciudad", "provincia_colegio", "primer_nombre",
    "segundo_nombre", "dv", "id_persona",
})
_FORBIDDEN_PREFIX = ("direccion", "domicilio", "telefono", "correo", "apellido")


def is_forbidden_column(name: str) -> bool:
    low = name.strip().lower()
    return low in _FORBIDDEN_EXACT or low.startswith(_FORBIDDEN_PREFIX)


# ---- specs ------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Col:
    wh: str                      # column name in the Warehouse view
    stg: str                     # column name in the staging table
    key: Optional[str] = None    # 'persona' | 'docente' when the value is a RUT to be keyed
    required: bool = False       # a NULL key drops the row (counted as skipped)


@dataclass(frozen=True)
class TsMode:
    kind: str                    # 'cargas' | 'full' | 'none'
    table: Optional[str] = None  # banner.<x>_cargas or banner.<x>_full


TS_NONE = TsMode("none")


def ts_cargas(table: str) -> TsMode:
    return TsMode("cargas", table)


def ts_full(table: str) -> TsMode:
    return TsMode("full", table)


@dataclass(frozen=True)
class Source:
    fuente: str
    view: str
    stg_table: Optional[str]
    columns: Tuple[Col, ...]
    ts: TsMode
    sql: Optional[str] = None    # aggregating SELECT (read-only GROUP BY) whose output columns are named as ``Col.wh``

    @property
    def select_sql(self) -> str:
        if self.sql is not None:
            return self.sql
        return "SELECT " + ", ".join(c.wh for c in self.columns) + " FROM " + self.view

    @property
    def sql_sha256(self) -> str:
        return hashlib.sha256(self.select_sql.encode("utf-8")).hexdigest()

    @property
    def stg_columns(self) -> Tuple[str, ...]:
        return tuple(c.stg for c in self.columns)


def assert_safe_columns(source: Source) -> None:
    bad = [c.wh for c in source.columns if is_forbidden_column(c.wh)]
    if bad:
        raise ValueError(f"{source.fuente}: personal columns are not extractable: {bad}")


def should_skip(existing_ok: bool, force: bool) -> bool:
    """A source already loaded for the same Warehouse load is a no-op unless forced."""
    return existing_ok and not force


def _c(wh: str) -> Col:
    return Col(wh, wh)


def _p(required: bool = True) -> Col:
    return Col("rut", "persona_key", "persona", required)


def _cols(*names: str) -> Tuple[Col, ...]:
    return tuple(_c(n) for n in names)


# Load history of the benefits (DAI 16-11-2026, P90/P91/P93): the 10 M rows of ``banner_beneficios_full`` (68 loads) are compressed
# in the Warehouse SELECT (read-only GROUP BY, no correlated subquery) to one row per (year, person, program, code, coverage):
# first / last load in which it appears, number of loads, presence in the last load and the amounts at the first and last load.
_SQL_CARGAS = (
    "SELECT periodo, rut, cod_carrera, codigo, cobertura, "
    "min(timestamp_carga) AS first_ts, max(timestamp_carga) AS last_ts, count(DISTINCT timestamp_carga) AS n_loads, "
    "(max(timestamp_carga) = (SELECT max(timestamp_carga) FROM banner.banner_beneficios_full)) AS presente_ultima_carga, "
    "(array_agg(benef_sem1 ORDER BY timestamp_carga ASC))[1] AS sem1_primera, "
    "(array_agg(benef_sem2 ORDER BY timestamp_carga ASC))[1] AS sem2_primera, "
    "(array_agg(benef_sem1 ORDER BY timestamp_carga DESC))[1] AS sem1_ultima, "
    "(array_agg(benef_sem2 ORDER BY timestamp_carga DESC))[1] AS sem2_ultima "
    "FROM banner.banner_beneficios_full GROUP BY periodo, rut, cod_carrera, codigo, cobertura")
_SQL_CARGAS_CAL = ("SELECT timestamp_carga, periodo, count(*) AS filas FROM banner.banner_beneficios_full "
                   "GROUP BY timestamp_carga, periodo")

SOURCES: Tuple[Source, ...] = (
    Source("ban_estados_academicos", "banner.ban_estados_academicos", "ban_estados_academicos",
           (_p(), *_cols("sorlcur", "periodo", "plan_estudios", "catalogo", "cod_admision", "admision",
                         "periodo_admision", "cod_programa", "cod_estado", "nombre_estado", "fecha_estado",
                         "cod_causal", "causal", "sexo")),
           ts_cargas("banner.ban_estados_academicos_cargas")),
    Source("ban_historia_notas", "banner.ban_historia_notas", "ban_historia_notas",
           (_p(), *_cols("periodo", "cod_carrera", "catalogo", "plan_estudio", "materia", "curso", "titulo",
                         "nota", "creditos", "oportunidad", "nrc", "comentario", "cod_depto", "nom_depto")),
           ts_cargas("banner.ban_historia_notas_cargas")),
    Source("ban_inscripciones", "banner.ban_inscripciones", "ban_inscripciones",
           (_p(), *_cols("nivel", "catalogo_malla", "materia_curso_catalogo", "titulo_catalogo",
                         "materia_curso_inscrito", "titulo_inscrito", "nrc", "nota", "aprobacion",
                         "oportunidad", "estado", "periodo")),
           ts_full("banner.ban_inscripciones_full")),
    Source("ban_oferta_academica", "banner.ban_oferta_academica", "ban_oferta_academica",
           (*_cols("periodo", "nrc", "paralelo", "carrera", "sede", "departamento", "cod_asignatura",
                   "asignatura", "tipo_clase", "cupo", "utilizado"),
            Col("rut_profesor", "docente_key", "docente"), _c("tipo_profesor")),
           ts_full("banner.ban_oferta_academica_full")),
    Source("banner_admision", "banner.banner_admision", "banner_admision",
           (_p(required=False),
            *_cols("year_admision", "cod_carrera", "id_sede", "cod_demre", "pref_demre", "preferencia",
                   "cod_admision", "desc_admision", "matricula", "fecha_matricula", "tipo_colegio",
                   "depend_colegio", "region_colegio", "comuna_colegio", "cod_comuna", "sexo",
                   "puntaje_leng", "puntaje_mat", "puntaje_ciencias", "puntaje_historia", "puntaje_nem",
                   "puntaje_ranking", "notas_em", "promedio_lm", "ponderado", "ponderado_normalizado")),
           ts_full("banner.banner_admision_full")),
    Source("banner_matricula", "banner.banner_matricula", "banner_matricula",
           (_p(), *_cols("year", "cod_carrera", "catalogo", "year_admision", "periodo_admision",
                         "cod_admision", "tipo_admision", "fecha_estado", "sede", "facultad")),
           TS_NONE),
    Source("banner_titulados", "banner.banner_titulados", "banner_titulados",
           (_p(), *_cols("codigo_carrera", "codigo_sies", "catalogo", "sede", "year_ingreso",
                         "semestre_ingreso", "duracion", "year_titulacion", "fecha_titulacion",
                         "semestres_suspendidos", "semestres_suspendidos_old", "tipo_admision")),
           ts_full("banner.banner_titulados_full")),
    Source("banner_estudiantes_postgrado", "banner.banner_estudiantes_postgrado", "banner_estudiantes_postgrado",
           (_p(), *_cols("cod_programa", "periodo", "cod_estado", "estado", "fecha_estado", "estado_matricula",
                         "periodo_admision", "cod_admision", "tipo_admision", "catalogo", "codigo_sies")),
           ts_full("banner.banner_estudiantes_postgrado_full")),
    # P77: postgrado states with program names (the same shape as ban_estados_academicos). Person name, nationality and sex are
    # not selected. The load marker is the full table of loads of the same view.
    Source("ban_estados_academicos_pos", "banner.ban_estados_academicos_pos", "ban_estados_academicos_pos",
           (_p(), *_cols("sorlcur", "periodo", "plan_estudios", "catalogo", "cod_admision", "admision",
                         "periodo_admision", "cod_programa", "nombre_banner", "nombre_estandar", "cod_estado",
                         "nombre_estado", "fecha_estado")),
           ts_full("banner.ban_estados_academicos_pos_full")),
    Source("ban_malla_programa", "banner.ban_malla_programa", "ban_malla_programa",
           _cols("malla_program_code", "malla_ctlg", "malla_materiacurso", "malla_semestre", "malla_formacion",
                 "malla_creditaje", "malla_asignatura", "malla_area", "malla_depto", "malla_depto_desc"),
           ts_full("banner.ban_malla_programa_full")),
    Source("malla_programa_prereq", "banner.malla_programa_prereq", "malla_programa_prereq",
           _cols("cod_programa", "catalogo", "codigo_asignatura", "codigo_asignatura_repreq"),
           ts_full("banner.malla_programa_prereq_full")),
    Source("malla_programa", "banner.malla_programa", "malla_programa",
           _cols("cod_programa", "catalogo", "codigo_asignatura", "nombre_asignatura", "creditos", "nivel"),
           ts_full("banner.malla_programa_full")),
    Source("banner_catalogos", "banner.banner_catalogos", "banner_catalogos",
           _cols("cod_carrera", "catalogo", "duracion"),
           ts_full("banner.banner_catalogos_full")),
    # Benefits (DAI, 16-11-2026): one row per (year, person, program, benefit, coverage); `periodo` is the YEAR. The program name
    # (`carrera`) is redundant with `cod_carrera` and is not extracted.
    Source("banner_beneficios", "banner.banner_beneficios", "banner_beneficios",
           (*_cols("periodo"), _p(), *_cols("id_sede", "cod_carrera", "financiamiento", "cobertura", "codigo", "beneficio",
                                            "benef_sem1", "benef_sem2", "total")),
           ts_full("banner.banner_beneficios_full")),
    Source("banner_beneficios_cargas", "banner.banner_beneficios_full", "banner_beneficios_cargas",
           (*_cols("periodo"), _p(), *_cols("cod_carrera", "codigo", "cobertura", "first_ts", "last_ts", "n_loads",
                                            "presente_ultima_carga", "sem1_primera", "sem2_primera", "sem1_ultima",
                                            "sem2_ultima")),
           ts_full("banner.banner_beneficios_full"), _SQL_CARGAS),
    Source("banner_beneficios_cargas_cal", "banner.banner_beneficios_full", "banner_beneficios_cargas_cal",
           _cols("timestamp_carga", "periodo", "filas"), ts_full("banner.banner_beneficios_full"), _SQL_CARGAS_CAL),
    Source("programa_d", "common.programa_d", "programa_d",
           _cols("id", "cod_banner", "programa_predecesor", "valid_program", "id_nivel", "nombre_programa",
                 "area_conocimiento", "facultad", "sede", "cod_demre"),
           TS_NONE),
    # P76: faculty names. ``programa_d.facultad`` is the id of this dictionary (``nom_depto`` exists only in the grade history).
    Source("facultad_d", "common.facultad_d", "facultad_d",
           _cols("id", "cod_unidad_organica", "nombre_unidad", "nivel_jerarquico", "cod_sede", "nombre_vigente"),
           TS_NONE),
)

# Seeded dictionary: verified against the Warehouse instead of copied (neural_meta.dic_tipo_admision).
TIPO_ADMISION_VIEW = "banner.ban_tipo_admision"
TIPO_ADMISION_SQL = f"SELECT cod_admision, admision, tipo_qualitas, tipo_cna FROM {TIPO_ADMISION_VIEW}"
TIPO_ADMISION_FUENTE = "ban_tipo_admision"

_BY_NAME: Dict[str, Source] = {s.fuente: s for s in SOURCES}


def by_name(fuente: str) -> Source:
    return _BY_NAME[fuente]


def all_fuentes() -> Tuple[str, ...]:
    return tuple(s.fuente for s in SOURCES) + (TIPO_ADMISION_FUENTE,)


# ---- row transformation -----------------------------------------------------------------------
class RowTransformer:
    """Raw Warehouse row -> staging row, with RUT replaced by its HMAC key."""

    def __init__(self, source: Source, secret: str):
        if not secret:
            raise ValueError("HMAC secret must not be empty")
        assert_safe_columns(source)
        self._secret = secret
        self._key_positions = [(i, c) for i, c in enumerate(source.columns) if c.key]
        self._cache: Dict[Tuple[str, str], Optional[str]] = {}
        self.skipped = 0

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def _key(self, kind: str, raw) -> Optional[str]:
        if raw is None:
            return None
        ck = (kind, raw)
        if ck in self._cache:
            return self._cache[ck]
        fn = persona_key if kind == "persona" else docente_key
        val = fn(str(raw), self._secret)
        self._cache[ck] = val
        return val

    def __call__(self, row: tuple) -> Optional[tuple]:
        if not self._key_positions:
            return row
        out = list(row)
        for i, col in self._key_positions:
            key = self._key(col.key, row[i])
            if key is None and col.required:
                self.skipped += 1
                return None
            out[i] = key
        return tuple(out)
