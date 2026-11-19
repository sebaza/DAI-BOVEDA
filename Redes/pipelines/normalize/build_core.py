"""Build ``neural_core`` (silver) from ``neural_stg`` (bronze).

* Rules live in the pure functions of ``pipelines.normalize``; SQL is used only for plain
  projections/aggregations (persona minima, catalog dictionaries, sections, de-duplicated bridges).
* Every run is one transaction: each selected entity is truncated and rebuilt, or nothing changes.
* The core schema, stg schema and meta schema are parameters so the integration test can run the same
  code against ``neural_test`` without touching the real schemas.
* Output is counts only; person keys never reach the console.

CLI: ``python -m pipelines.normalize.build_core [--only persona,catalogo,...]``
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from ..migrate import ALLOWED_SCHEMAS
from .admission import Via, derive_postulacion, parse_scores
from .assignment import assign_episode
from .catalog import (
    classify_prereq_edge, classify_programa, codigo_asignatura, dedupe_prereq, detect_hito,
)
from .core_helpers import (
    choose_malla_row, parse_date_text, parse_decimal_text, parse_int_text, parse_semestre,
    resolve_sexo, tipo_renuncia,
)
from .grades import classify_historia, classify_inscripcion, flag_duplicate_renuncias, flag_replaced_same_period
from .models import EstadoRow
from .postgrado import nivel_postgrado
from .timeline import EpisodioDerivado, EpisodioKey, build_timeline

BATCH = 50_000
ITERSIZE = 20_000
HITO_VERSION = "regex_nombre_v1"

# Build order and dependencies (rebuilding a parent rebuilds what references it).
STEPS: Tuple[str, ...] = (
    "persona", "catalogo", "facultad", "postulacion", "episodio", "intento", "inscripcion", "seccion", "titulacion", "postgrado",
)
DEPENDENTS: Dict[str, Tuple[str, ...]] = {
    "persona": ("episodio", "intento", "inscripcion", "titulacion", "postgrado"),
    "episodio": ("intento", "titulacion"),
}
# Core tables (truncate order irrelevant: TRUNCATE ... CASCADE inside one statement).
STEP_TABLES: Dict[str, Tuple[str, ...]] = {
    "persona": ("persona",),
    "facultad": ("facultad",),
    "catalogo": ("programa", "programa_catalogo", "asignatura_malla", "prerrequisito", "hito_formativo"),
    "postulacion": ("postulacion_via", "postulacion"),
    "episodio": ("episodio_programa", "evento_estado"),
    "intento": ("intento_asignatura",),
    "inscripcion": ("inscripcion_asignatura", "inscripcion_equivalencia"),
    "seccion": ("seccion", "seccion_docente"),
    "titulacion": ("titulacion",),
    "postgrado": ("matricula_postgrado", "programa_postgrado", "estado_postgrado"),
}


def expand_steps(only: Optional[Sequence[str]]) -> List[str]:
    """Selected steps plus everything that depends on them, in build order."""
    wanted = set(STEPS if not only else only)
    unknown = wanted - set(STEPS)
    if unknown:
        raise ValueError(f"unknown step(s): {sorted(unknown)}; valid: {list(STEPS)}")
    changed = True
    while changed:
        changed = False
        for step in list(wanted):
            for dep in DEPENDENTS.get(step, ()):
                if dep not in wanted:
                    wanted.add(dep)
                    changed = True
    return [s for s in STEPS if s in wanted]


# ---- context and I/O helpers ------------------------------------------------------------------
class Ctx:
    def __init__(self, conn, stg: str, core: str, meta: str, corte: date, out: Callable[[str], None] = print):
        for schema in (stg, core, meta):
            if schema not in ALLOWED_SCHEMAS:
                raise ValueError(f"schema {schema!r} is not one of {ALLOWED_SCHEMAS}")
        self.conn, self.stg, self.core, self.meta, self.corte, self.out = conn, stg, core, meta, corte, out
        self.counts: Dict[str, int] = {}
        self.notes: Dict[str, int] = {}

    def s(self, name: str) -> str:
        return f"{self.stg}.{name}"

    def c(self, name: str) -> str:
        return f"{self.core}.{name}"

    def m(self, name: str) -> str:
        return f"{self.meta}.{name}"

    def note(self, key: str, value: int) -> None:
        self.notes[key] = value

    def rows(self, sql: str, params: Sequence = ()) -> list:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def execute(self, sql: str, params: Sequence = ()) -> int:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def stream(self, sql: str, params: Sequence = (), name: str = "bc") -> Iterator[tuple]:
        with self.conn.cursor(name=name) as cur:
            cur.itersize = ITERSIZE
            cur.execute(sql, params)
            yield from cur

    def copy(self, table: str, columns: Sequence[str], rows: Iterable[tuple]) -> int:
        """COPY in batches so a server-side cursor can keep feeding ``rows`` between batches."""
        cols = ", ".join(columns)
        total = 0
        buf: list = []

        def flush() -> None:
            if not buf:
                return
            with self.conn.cursor() as cur:
                with cur.copy(f"COPY {self.c(table)} ({cols}) FROM STDIN") as cp:
                    for r in buf:
                        cp.write_row(r)
            buf.clear()

        for row in rows:
            buf.append(row)
            total += 1
            if len(buf) >= BATCH:
                flush()
        flush()
        self.counts[table] = total
        return total


def _truncate(ctx: Ctx, tables: Sequence[str]) -> None:
    ctx.execute("TRUNCATE " + ", ".join(ctx.c(t) for t in tables) + " RESTART IDENTITY CASCADE")


# ---- persona ----------------------------------------------------------------------------------
def build_persona(ctx: Ctx) -> None:
    _truncate(ctx, STEP_TABLES["persona"])
    people: Dict[str, dict] = {}

    def person(key: str) -> dict:
        return people.setdefault(key, {"est": None, "his": None, "ins": None, "sexo": defaultdict(list)})

    for key, first, sexos in ctx.rows(
        f"SELECT persona_key, min(periodo), array_agg(DISTINCT sexo) FILTER (WHERE btrim(sexo) <> '') "
        f"FROM {ctx.s('ban_estados_academicos')} GROUP BY persona_key"
    ):
        p = person(key)
        p["est"] = first
        p["sexo"]["estados"] = sexos or []
    for key, first in ctx.rows(f"SELECT persona_key, min(periodo) FROM {ctx.s('ban_historia_notas')} GROUP BY persona_key"):
        person(key)["his"] = first
    for key, first in ctx.rows(f"SELECT persona_key, min(periodo) FROM {ctx.s('ban_inscripciones')} GROUP BY persona_key"):
        person(key)["ins"] = first
    for (key,) in ctx.rows(f"SELECT DISTINCT persona_key FROM {ctx.s('banner_titulados')}"):
        person(key)
    for (key,) in ctx.rows(f"SELECT DISTINCT persona_key FROM {ctx.s('banner_estudiantes_postgrado')}"):
        person(key)
    # Applicants who never appear elsewhere are not persons of the trajectory; admission only adds sex.
    for key, sexos in ctx.rows(
        f"SELECT persona_key, array_agg(DISTINCT sexo) FILTER (WHERE btrim(sexo) <> '') "
        f"FROM {ctx.s('banner_admision')} WHERE persona_key IS NOT NULL GROUP BY persona_key"
    ):
        if key in people:
            people[key]["sexo"]["admision"] = sexos or []

    def rows() -> Iterator[tuple]:
        conflicts = 0
        for key in sorted(people):
            p = people[key]
            sexo, conflicto = resolve_sexo(p["sexo"])
            conflicts += conflicto
            yield (key, sexo, conflicto, p["est"], p["his"], p["ins"])
        ctx.note("persona_sexo_conflicto", conflicts)

    ctx.copy("persona", ("persona_key", "sexo", "sexo_conflicto", "primer_periodo_estados",
                         "primer_periodo_historia", "primer_periodo_inscripcion"), rows())


# ---- catalog dictionaries ---------------------------------------------------------------------
def _codigo_parts(code: str) -> Tuple[str, str]:
    if "-" in code:
        m, c = code.split("-", 1)
        return m, c
    return code[:4], code[4:]


def build_facultad(ctx: Ctx) -> None:
    """P76: dictionary of the ``programa_d.facultad`` ids; the name is ``nombre_unidad`` (common.facultad_d).
    A step of its own: it touches no table that the long analytical queries read."""
    _truncate(ctx, STEP_TABLES["facultad"])
    ctx.execute(
        f"INSERT INTO {ctx.c('facultad')} (facultad_id, cod_unidad_organica, nombre_facultad, nombre_vigente, "
        f"nivel_jerarquico, cod_sede) "
        f"SELECT DISTINCT ON (id) id, cod_unidad_organica, nombre_unidad, nombre_vigente, nivel_jerarquico, cod_sede "
        f"FROM {ctx.s('facultad_d')} WHERE id IS NOT NULL AND nombre_unidad IS NOT NULL "
        f"ORDER BY id, stg_id DESC")
    ctx.counts["facultad"] = ctx.rows(f"SELECT count(*) FROM {ctx.c('facultad')}")[0][0]


def build_catalogo(ctx: Ctx) -> None:
    _truncate(ctx, STEP_TABLES["catalogo"])
    # programa
    prog = ctx.rows(
        f"SELECT id, cod_banner, programa_predecesor, valid_program, id_nivel, nombre_programa, "
        f"area_conocimiento, facultad, sede, cod_demre FROM {ctx.s('programa_d')} ORDER BY id")
    ids = {r[0] for r in prog}
    n_pred_missing = 0

    def prog_rows() -> Iterator[tuple]:
        nonlocal n_pred_missing
        for (pid, cod, pred, valid, nivel, nombre, area, fac, sede, demre) in prog:
            flags = classify_programa(bool(valid), pred, ids)
            n_pred_missing += flags.predecesor_inexistente
            yield (cod, pid, bool(valid), pred, flags.predecesor_inexistente, nombre, nivel, area, fac, sede, demre)

    ctx.copy("programa", ("cod_programa", "programa_d_id", "valid_program", "programa_predecesor",
                          "predecesor_inexistente", "nombre_programa", "id_nivel", "area_conocimiento",
                          "facultad", "sede", "cod_demre"), prog_rows())
    ctx.note("programa_predecesor_inexistente", n_pred_missing)
    ctx.note("programa_sin_nombre_de_facultad", ctx.rows(
        f"SELECT count(*) FROM {ctx.c('programa')} p WHERE p.facultad IS NOT NULL AND NOT EXISTS ("
        f"SELECT 1 FROM {ctx.c('facultad')} f WHERE f.facultad_id = p.facultad)")[0][0])

    # programa_catalogo: every (programa, catalogo) seen in the catalog or in the official malla
    ctx.execute(
        f"INSERT INTO {ctx.c('programa_catalogo')} (cod_programa, catalogo, duracion) "
        f"SELECT cod, cat, max(dur) FROM ("
        f"  SELECT cod_carrera AS cod, catalogo AS cat, duracion AS dur FROM {ctx.s('banner_catalogos')} "
        f"  WHERE cod_carrera IS NOT NULL AND catalogo IS NOT NULL "
        f"  UNION ALL SELECT malla_program_code, malla_ctlg, NULL::integer FROM {ctx.s('ban_malla_programa')} "
        f"  WHERE malla_program_code IS NOT NULL AND malla_ctlg IS NOT NULL) x GROUP BY cod, cat")
    ctx.counts["programa_catalogo"] = ctx.rows(f"SELECT count(*) FROM {ctx.c('programa_catalogo')}")[0][0]

    # asignatura_malla (official curriculum, P17) with duplicate handling
    groups: Dict[Tuple[str, str, str], list] = defaultdict(list)
    for (code, ctlg, mc, sem, form, cred, nombre, area, depto, depto_desc) in ctx.rows(
        f"SELECT malla_program_code, malla_ctlg, malla_materiacurso, malla_semestre, malla_formacion, "
        f"malla_creditaje, malla_asignatura, malla_area, malla_depto, malla_depto_desc "
        f"FROM {ctx.s('ban_malla_programa')} "
        f"WHERE malla_program_code IS NOT NULL AND malla_ctlg IS NOT NULL AND malla_materiacurso IS NOT NULL"
    ):
        groups[(code, ctlg, mc)].append({"semestre": sem, "creditos": cred, "formacion": form, "nombre": nombre,
                                         "area": area, "depto": depto, "depto_desc": depto_desc})
    n_conflict = 0
    malla_index: Dict[Tuple[str, str], set] = defaultdict(set)   # (programa, catalogo) -> codigos
    codes_by_program: Dict[str, set] = defaultdict(set)          # programa -> codigos in any catalogo
    hitos: List[tuple] = []

    def malla_rows() -> Iterator[tuple]:
        nonlocal n_conflict
        for (prog_code, ctlg, mc) in sorted(groups):
            row, conflict, n = choose_malla_row(groups[(prog_code, ctlg, mc)])
            n_conflict += conflict
            malla_index[(prog_code, ctlg)].add(mc)
            codes_by_program[prog_code].add(mc)
            m, c = _codigo_parts(mc)
            formato = codigo_asignatura(m, c).formato
            hito = detect_hito(row["nombre"])
            if hito:
                hitos.append((prog_code, ctlg, mc, hito.tipo_hito, hito.metodo, hito.validado, HITO_VERSION))
            yield (prog_code, ctlg, mc, formato, parse_semestre(row["semestre"]), row["semestre"],
                   parse_decimal_text(row["creditos"]), row["formacion"], row["nombre"], row["area"],
                   row["depto"], row["depto_desc"], n, conflict)

    ctx.copy("asignatura_malla", ("cod_programa", "catalogo", "codigo_asignatura", "formato_codigo", "semestre",
                                  "semestre_texto", "creditos", "formacion", "nombre_asignatura", "area", "depto",
                                  "depto_desc", "filas_origen", "atributos_conflicto"), malla_rows())
    ctx.note("asignatura_malla_con_conflicto", n_conflict)
    ctx.copy("hito_formativo", ("cod_programa", "catalogo", "codigo_asignatura", "tipo_hito", "metodo", "validado",
                                "version"), iter(hitos))

    # prerrequisito: requisito -> asignatura (P46); no edge is dropped, only classified
    id_to_cod = {r[0]: r[1] for r in prog}
    raw = ctx.rows(f"SELECT cod_programa, catalogo, codigo_asignatura, codigo_asignatura_repreq "
                   f"FROM {ctx.s('malla_programa_prereq')}")
    mapped = []
    unmapped = 0
    for cod, ctlg, asig, req in raw:
        try:
            cod_banner = id_to_cod[int(cod)]
        except (KeyError, ValueError, TypeError):
            cod_banner = f"id:{cod}"
            unmapped += 1
        mapped.append((cod_banner, ctlg, asig, req))
    ctx.note("prereq_programa_sin_mapeo", unmapped)

    programs_of_code: Dict[str, set] = defaultdict(set)
    for prog_code, codes in codes_by_program.items():
        for code in codes:
            programs_of_code[code].add(prog_code)

    class _InOtherProgram:
        """Membership test: the code belongs to the malla of some program other than ``prog``."""

        def __init__(self, prog: str):
            self.prog = prog

        def __contains__(self, code: str) -> bool:
            return bool(programs_of_code.get(code, set()) - {self.prog})

    def prereq_rows() -> Iterator[tuple]:
        edges = sorted(dedupe_prereq(mapped),
                       key=lambda e: (e.cod_programa, e.catalogo, e.codigo_requisito, e.codigo_asignatura))
        for edge in edges:
            same = malla_index.get((edge.cod_programa, edge.catalogo), set())
            other_cat = codes_by_program.get(edge.cod_programa, set())
            other_prog = _InOtherProgram(edge.cod_programa)
            clasif = classify_prereq_edge(edge, same, other_cat, other_prog)
            yield (edge.cod_programa, edge.catalogo, edge.codigo_requisito, edge.codigo_asignatura, edge.filas_origen,
                   edge.codigo_asignatura in same, edge.codigo_requisito in same,
                   edge.codigo_requisito in other_prog, clasif)

    ctx.copy("prerrequisito", ("cod_programa", "catalogo", "codigo_requisito", "codigo_asignatura", "filas_origen",
                               "asig_en_malla", "req_en_malla", "req_en_otro_programa", "clasificacion"),
             prereq_rows())


# ---- admission ----------------------------------------------------------------------------------
_SCORE_FIELDS = ("puntaje_leng", "puntaje_mat", "puntaje_ciencias", "puntaje_historia", "puntaje_nem",
                 "puntaje_ranking", "notas_em", "promedio_lm", "ponderado", "ponderado_normalizado")


def build_postulacion(ctx: Ctx) -> None:
    _truncate(ctx, STEP_TABLES["postulacion"])
    tipo = dict(ctx.rows(f"SELECT cod_admision, tipo_qualitas FROM {ctx.m('dic_tipo_admision')}"))
    cols = ("year_admision, persona_key, cod_carrera, cod_admision, id_sede, pref_demre, preferencia, matricula, "
            "fecha_matricula, tipo_colegio, depend_colegio, region_colegio, comuna_colegio, cod_comuna, carga_id, "
            + ", ".join(_SCORE_FIELDS))
    groups: Dict[Tuple[str, str, str], List[Via]] = defaultdict(list)
    skipped = {"sin_persona": 0, "sin_clave": 0, "fecha_sin_parsear": 0}

    def via_rows() -> Iterator[tuple]:
        for r in ctx.stream(f"SELECT {cols} FROM {ctx.s('banner_admision')}", name="bc_adm"):
            (year, pkey, carr, adm, sede, pref, preferencia, mat, fmat, tcol, dcol, rcol, ccol, cod_com, carga) = r[:15]
            scores, ok = parse_scores(dict(zip(_SCORE_FIELDS, r[15:])))
            if pkey is None:
                skipped["sin_persona"] += 1
                continue
            if year is None or carr is None:
                skipped["sin_clave"] += 1
                continue
            fecha = parse_date_text(fmat)
            if fmat and fecha is None:
                skipped["fecha_sin_parsear"] += 1
            mat_n = mat.strip().upper() if mat and mat.strip().upper() in ("Y", "N") else None
            groups[(year, pkey, carr)].append(Via((adm or "NN").strip() or "NN", mat_n or "", tipo.get((adm or "").strip())))
            yield (year, pkey, carr, adm, sede, pref, preferencia, mat_n, fecha,
                   *(scores[f] for f in _SCORE_FIELDS), ok, tcol, dcol, rcol, ccol, cod_com, carga)

    ctx.copy("postulacion_via", ("year_admision", "persona_key", "cod_carrera", "cod_admision", "id_sede",
                                 "pref_demre", "preferencia", "matricula", "fecha_matricula", *_SCORE_FIELDS,
                                 "puntaje_parse_ok", "tipo_colegio", "depend_colegio", "region_colegio",
                                 "comuna_colegio", "cod_comuna", "carga_id"), via_rows())
    for k, v in skipped.items():
        ctx.note(f"postulacion_via_{k}", v)

    def post_rows() -> Iterator[tuple]:
        for (year, pkey, carr) in sorted(groups):
            p = derive_postulacion(groups[(year, pkey, carr)])
            mat = p.matricula_elegida if p.matricula_elegida in ("Y", "N") else None
            yield (year, pkey, carr, p.cod_admision_elegida, mat, p.alguna_via_matriculo, p.n_vias)

    ctx.copy("postulacion", ("year_admision", "persona_key", "cod_carrera", "cod_admision_elegida",
                             "matricula_elegida", "alguna_via_matriculo", "n_vias"), post_rows())


# ---- trajectory ---------------------------------------------------------------------------------
def _estado_cursor(ctx: Ctx, name: str):
    """Per-person groups of EstadoRow plus the extra stg attributes, ordered by person."""
    sql = (f"SELECT persona_key, sorlcur, periodo, cod_programa, cod_estado, cod_admision, periodo_admision, "
           f"catalogo, fecha_estado, plan_estudios, cod_causal, carga_id FROM {ctx.s('ban_estados_academicos')} "
           f"ORDER BY persona_key, periodo, sorlcur")
    current: Optional[str] = None
    rows: List[EstadoRow] = []
    extras: Dict[int, tuple] = {}
    for (pk, sorl, per, prog, est, adm, padm, cat, fecha, plan, causal, carga) in ctx.stream(sql, name=name):
        if pk != current:
            if current is not None:
                yield current, rows, extras
            current, rows, extras = pk, [], {}
        s = int(sorl)
        rows.append(EstadoRow(s, per, prog, est, adm, padm, cat, fecha.date() if fecha else None))
        extras[s] = (plan, causal, fecha, carga)
    if current is not None:
        yield current, rows, extras


def build_episodio(ctx: Ctx) -> None:
    _truncate(ctx, STEP_TABLES["episodio"])
    if not ctx.rows(f"SELECT 1 FROM {ctx.c('persona')} LIMIT 1"):
        raise RuntimeError("persona is empty: build it first (step 'persona')")

    # pass 1: episodes
    def ep_rows() -> Iterator[tuple]:
        for pk, rows, _extras in _estado_cursor(ctx, "bc_ep1"):
            tl = build_timeline(rows, ctx.corte)
            for ep in tl.episodes:
                yield (pk, ep.key.cod_programa, ep.key.cod_admision, ep.key.periodo_admision,
                       ep.cod_admision_imputado, ep.primer_periodo, ep.ultimo_periodo, ep.n_tramos, ep.n_estados,
                       ep.no_contiguo, ep.catalogo_inicial, ep.catalogo_final, ep.ultimo_estado_clase)

    ctx.copy("episodio_programa", ("persona_key", "cod_programa", "cod_admision", "periodo_admision",
                                   "cod_admision_imputado", "primer_periodo", "ultimo_periodo", "n_tramos",
                                   "n_estados", "no_contiguo", "catalogo_inicial", "catalogo_final",
                                   "ultimo_estado_clase"), ep_rows())
    ids = {(pk, prog, adm, padm): eid for eid, pk, prog, adm, padm in ctx.rows(
        f"SELECT episodio_id, persona_key, cod_programa, cod_admision, periodo_admision FROM {ctx.c('episodio_programa')}")}

    # pass 2: events with the episode id
    def ev_rows() -> Iterator[tuple]:
        for pk, rows, extras in _estado_cursor(ctx, "bc_ep2"):
            tl = build_timeline(rows, ctx.corte)
            for ev in tl.events:
                e = ev.estado
                plan, causal, fecha_orig, carga = extras[e.sorlcur]
                eid = None
                if ev.episodio_key is not None:
                    k = ev.episodio_key
                    eid = ids[(pk, k.cod_programa, k.cod_admision, k.periodo_admision)]
                f = ev.fecha
                yield (pk, e.sorlcur, eid, e.periodo, ev.orden_canonico, ev.tramo_n, e.cod_programa, e.cod_admision,
                       e.periodo_admision, e.catalogo, plan, ev.info.cod_estado, ev.info.sin_codigo, ev.info.conocido,
                       causal, fecha_orig, f.fecha_min, f.fecha_max, f.fecha_aproximada, f.sin_intervalo,
                       f.intervalo_invertido, f.fecha_marcador, ev.es_correccion_sistema, carga)

    ctx.copy("evento_estado", ("persona_key", "sorlcur", "episodio_id", "periodo", "orden_canonico", "tramo_n",
                               "cod_programa", "cod_admision", "periodo_admision", "catalogo", "plan_estudios",
                               "cod_estado", "sin_codigo", "estado_conocido", "cod_causal", "fecha_estado_original",
                               "fecha_min", "fecha_max", "fecha_aproximada", "sin_intervalo", "intervalo_invertido",
                               "fecha_marcador", "es_correccion_sistema", "carga_id"), ev_rows())


def _load_episodes(ctx: Ctx) -> Tuple[Dict[str, List[EpisodioDerivado]], Dict[Tuple[str, EpisodioKey], int]]:
    by_person: Dict[str, List[EpisodioDerivado]] = defaultdict(list)
    ids: Dict[Tuple[str, EpisodioKey], int] = {}
    for eid, pk, prog, adm, padm, first, last in ctx.rows(
        f"SELECT episodio_id, persona_key, cod_programa, cod_admision, periodo_admision, primer_periodo, "
        f"ultimo_periodo FROM {ctx.c('episodio_programa')} ORDER BY episodio_id"
    ):
        key = EpisodioKey(prog, adm, padm)
        by_person[pk].append(EpisodioDerivado(key, len(by_person[pk]) + 1, first, last))
        ids[(pk, key)] = eid
    if not ids:
        raise RuntimeError("episodio_programa is empty: build the step 'episodio' first")
    return by_person, ids


def _oportunidad(raw: Optional[str]) -> Optional[int]:
    return parse_int_text(raw)


def build_intento(ctx: Ctx) -> None:
    _truncate(ctx, STEP_TABLES["intento"])
    by_person, ids = _load_episodes(ctx)
    sql = (f"SELECT periodo, persona_key, cod_carrera, catalogo, materia, curso, oportunidad, nrc, titulo, nota, "
           f"creditos, comentario, carga_id FROM {ctx.s('ban_historia_notas')}")
    stats = {"candidato_1": 0, "candidato_0": 0, "candidato_2_mas": 0}

    def rows() -> Iterator[tuple]:
        for (periodo, pk, carrera, cat, materia, curso, opor, nrc, titulo, nota, cred, coment, carga) in ctx.stream(
            sql, name="bc_int"
        ):
            res = classify_historia(nota, coment, opor)
            cod = codigo_asignatura(materia, curso)
            asg = assign_episode(periodo, carrera, by_person.get(pk, ()))
            eid = ids[(pk, asg.episodio_key)] if asg.episodio_key is not None else None
            stats["candidato_1" if eid is not None else ("candidato_2_mas" if asg.episodio_ambiguo else "candidato_0")] += 1
            yield (periodo, pk, carrera, cat, materia or "", curso or "", _oportunidad(opor), nrc, eid,
                   asg.sin_episodio, asg.episodio_ambiguo, cod.codigo, cod.formato, titulo, nota, res.nota_parse,
                   res.nota_numerica, res.nota_es_heredada, res.resultado_tipo, res.aprobado_curricular,
                   res.es_intento_evaluado, cred, res.comentario_codigo, res.fuente_resultado, carga)

    ctx.copy("intento_asignatura",
             ("periodo", "persona_key", "cod_carrera", "catalogo", "materia", "curso", "oportunidad", "nrc",
              "episodio_id", "sin_episodio", "episodio_ambiguo", "codigo_asignatura", "formato_codigo", "titulo",
              "nota_texto", "nota_parse", "nota_numerica", "nota_es_heredada", "resultado_tipo",
              "aprobado_curricular", "es_intento_evaluado", "creditos", "comentario_codigo", "fuente_resultado",
              "carga_id"), rows())
    for k, v in stats.items():
        ctx.note(f"intento_{k}", v)
    _marcar_reemplazadas(ctx)


def _marcar_reemplazadas(ctx: Ctx) -> None:
    """P54 (DAI, 13-11-2026): in every (persona, periodo, asignatura) with several EVALUATED rows the result is the row with
    the highest ``oportunidad`` (tie: most recent load, then latest row). The earlier rows stay in core, flagged, and leave
    the evaluated attempts; their pass/fail is removed so no downstream count can use them. The rule is the pure
    ``flag_replaced_same_period``; SQL only finds the candidate groups."""
    rows = ctx.rows(
        f"SELECT i.intento_id, i.persona_key, i.periodo, i.codigo_asignatura, i.oportunidad, i.carga_id "
        f"FROM {ctx.c('intento_asignatura')} i JOIN ("
        f"  SELECT persona_key, periodo, codigo_asignatura FROM {ctx.c('intento_asignatura')} "
        f"  WHERE es_intento_evaluado GROUP BY 1, 2, 3 HAVING count(*) > 1) g "
        f"ON g.persona_key = i.persona_key AND g.periodo = i.periodo AND g.codigo_asignatura = i.codigo_asignatura "
        f"WHERE i.es_intento_evaluado ORDER BY i.intento_id")
    flags = flag_replaced_same_period([((r[1], r[2], r[3]), r[4], r[5], r[0]) for r in rows])
    ids = [r[0] for r, f in zip(rows, flags) if f]
    ctx.note("intento_grupos_con_varias_filas_evaluadas", len({(r[1], r[2], r[3]) for r in rows}))
    ctx.note("intento_reemplazados_mismo_periodo", len(ids))
    for i in range(0, len(ids), 10_000):
        ctx.execute(
            f"UPDATE {ctx.c('intento_asignatura')} SET reemplazada_mismo_periodo = true, es_intento_evaluado = false, "
            f"aprobado_curricular = NULL WHERE intento_id = ANY(%s)", (ids[i:i + 10_000],))


# ---- inscriptions -------------------------------------------------------------------------------
def build_inscripcion(ctx: Ctx) -> None:
    _truncate(ctx, STEP_TABLES["inscripcion"])
    groups: Dict[tuple, list] = defaultdict(list)
    for r in ctx.rows(
        f"SELECT periodo, persona_key, nrc, materia_curso_inscrito, estado, titulo_inscrito, aprobacion, nota, "
        f"oportunidad, materia_curso_catalogo, titulo_catalogo, catalogo_malla, nivel, carga_id "
        f"FROM {ctx.s('ban_inscripciones')} ORDER BY stg_id"
    ):
        groups[(r[0], r[1], r[2], r[3], r[4])].append(r)

    # estado_conflicto: same (periodo, persona, nrc, materia) with more than one estado
    estados_por_curso: Dict[tuple, set] = defaultdict(set)
    for (periodo, pk, nrc, materia, estado) in groups:
        estados_por_curso[(periodo, pk, nrc, materia)].add(estado)

    keys = sorted(groups, key=lambda k: tuple("" if v is None else str(v) for v in k))
    classified: Dict[tuple, tuple] = {}
    inconsistent = 0
    for k in keys:
        rows = groups[k]
        results = {(classify_inscripcion(r[7], r[6], r[4]).resultado_tipo,) for r in rows}
        if len(results) > 1:
            inconsistent += 1
        classified[k] = classify_inscripcion(rows[0][7], rows[0][6], rows[0][4])
    ctx.note("inscripcion_grupos_con_resultado_inconsistente", inconsistent)

    renuncias = flag_duplicate_renuncias(
        [(k[1], k[0], k[3], classified[k].resultado_tipo) for k in keys])

    def parent_rows() -> Iterator[tuple]:
        for k, rep in zip(keys, renuncias):
            periodo, pk, nrc, materia, estado = k
            rows = groups[k]
            first = rows[0]
            res = classified[k]
            oports = {parse_int_text(None if r[8] is None else str(r[8])) for r in rows}
            oport = next(iter(oports)) if len(oports) == 1 else None
            equivs = {(r[9], r[11], parse_int_text(None if r[8] is None else str(r[8]))) for r in rows}
            yield (periodo, pk, nrc, materia, first[5], estado, first[6], oport, len(oports) > 1, first[7],
                   res.nota_parse, res.nota_numerica, res.nota_es_heredada, res.resultado_tipo,
                   res.aprobado_curricular, res.es_intento_evaluado, res.aprobacion_discrepa,
                   res.resultado_tipo == "renuncia", tipo_renuncia(estado), bool(rep),
                   res.resultado_tipo == "convalidacion", res.resultado_tipo == "en_curso",
                   len(estados_por_curso[(periodo, pk, nrc, materia)]) > 1, len(equivs), first[13])

    ctx.copy("inscripcion_asignatura",
             ("periodo", "persona_key", "nrc", "materia_curso_inscrito", "titulo_inscrito", "estado", "aprobacion",
              "oportunidad", "oportunidad_conflicto", "nota_texto", "nota_parse", "nota_numerica",
              "nota_es_heredada", "resultado_tipo", "aprobado_curricular", "es_intento_evaluado",
              "aprobacion_discrepa", "es_renuncia", "tipo_renuncia", "renuncia_repetida", "es_convalidacion",
              "en_curso", "estado_conflicto", "n_equivalencias", "carga_id"), parent_rows())

    parent_ids = {(p, pk, nrc, mat, est): iid for iid, p, pk, nrc, mat, est in ctx.rows(
        f"SELECT inscripcion_id, periodo, persona_key, nrc, materia_curso_inscrito, estado "
        f"FROM {ctx.c('inscripcion_asignatura')}")}

    def child_rows() -> Iterator[tuple]:
        for k in keys:
            counts: Dict[tuple, list] = {}
            for r in groups[k]:
                oport = parse_int_text(None if r[8] is None else str(r[8]))
                ek = (r[9], r[11], oport)
                if ek not in counts:
                    counts[ek] = [r[10], r[12], 0]
                counts[ek][2] += 1
            for (mc_cat, cat_malla, oport), (titulo_cat, nivel, n) in counts.items():
                yield (parent_ids[k], mc_cat or "", titulo_cat, cat_malla, nivel, oport, n)

    ctx.copy("inscripcion_equivalencia",
             ("inscripcion_id", "materia_curso_catalogo", "titulo_catalogo", "catalogo_malla", "nivel",
              "oportunidad", "filas_origen"), child_rows())


# ---- sections and teachers ------------------------------------------------------------------------
def build_seccion(ctx: Ctx) -> None:
    _truncate(ctx, STEP_TABLES["seccion"])
    ctx.note("seccion_nrc_vacio", ctx.rows(
        f"SELECT count(*) FROM {ctx.s('ban_oferta_academica')} WHERE nrc IS NULL OR btrim(nrc) = ''")[0][0])
    ctx.execute(
        f"INSERT INTO {ctx.c('seccion')} (periodo, nrc, paralelo, carrera, sede, departamento, cod_asignatura, "
        f"asignatura, tipo_clase, cupo, utilizado) "
        f"SELECT DISTINCT ON (periodo, nrc) periodo, nrc, paralelo, carrera, sede, departamento, cod_asignatura, "
        f"asignatura, tipo_clase, cupo, utilizado FROM {ctx.s('ban_oferta_academica')} "
        f"WHERE periodo IS NOT NULL AND nrc IS NOT NULL AND btrim(nrc) <> '' "
        f"ORDER BY periodo, nrc, paralelo, carrera, sede, departamento, cod_asignatura, asignatura, tipo_clase, "
        f"cupo, utilizado")
    ctx.counts["seccion"] = ctx.rows(f"SELECT count(*) FROM {ctx.c('seccion')}")[0][0]
    ctx.note("seccion_con_atributos_distintos", ctx.rows(
        f"SELECT count(*) FROM (SELECT 1 FROM {ctx.s('ban_oferta_academica')} "
        f"WHERE periodo IS NOT NULL AND nrc IS NOT NULL AND btrim(nrc) <> '' GROUP BY periodo, nrc "
        f"HAVING count(DISTINCT (paralelo, carrera, sede, departamento, cod_asignatura, asignatura, tipo_clase, "
        f"cupo, utilizado)) > 1) x")[0][0])
    ctx.execute(
        f"INSERT INTO {ctx.c('seccion_docente')} (periodo, nrc, docente_key, tipo_profesor) "
        f"SELECT periodo, nrc, docente_key, min(tipo_profesor) FROM {ctx.s('ban_oferta_academica')} "
        f"WHERE periodo IS NOT NULL AND nrc IS NOT NULL AND btrim(nrc) <> '' AND docente_key IS NOT NULL "
        f"GROUP BY periodo, nrc, docente_key")
    ctx.counts["seccion_docente"] = ctx.rows(f"SELECT count(*) FROM {ctx.c('seccion_docente')}")[0][0]


# ---- outcomes -------------------------------------------------------------------------------------
def build_titulacion(ctx: Ctx) -> None:
    _truncate(ctx, STEP_TABLES["titulacion"])
    by_person, ids = _load_episodes(ctx)
    ambiguous = 0
    seen: set = set()
    duplicates = 0

    def rows() -> Iterator[tuple]:
        nonlocal ambiguous, duplicates
        for r in ctx.stream(
            f"SELECT persona_key, codigo_carrera, catalogo, fecha_titulacion, codigo_sies, year_ingreso, "
            f"semestre_ingreso, duracion, year_titulacion, semestres_suspendidos, semestres_suspendidos_old, "
            f"tipo_admision, carga_id FROM {ctx.s('banner_titulados')} ORDER BY stg_id", name="bc_tit"
        ):
            pk, carrera = r[0], r[1]
            nk = (pk, carrera, r[2], r[3])
            if nk in seen:      # exact repeat of the natural key (verified identical in the source): kept once
                duplicates += 1
                continue
            seen.add(nk)
            cands = [e for e in by_person.get(pk, ()) if e.key.cod_programa == carrera]
            eid = ids[(pk, cands[0].key)] if len(cands) == 1 else None   # never choose between episodes
            if len(cands) > 1:
                ambiguous += 1
            yield (pk, carrera, r[2], r[3], eid, *r[4:])

    ctx.copy("titulacion", ("persona_key", "codigo_carrera", "catalogo", "fecha_titulacion", "episodio_id",
                            "codigo_sies", "year_ingreso", "semestre_ingreso", "duracion", "year_titulacion",
                            "semestres_suspendidos", "semestres_suspendidos_old", "tipo_admision", "carga_id"),
             rows())
    ctx.note("titulacion_episodio_ambiguo", ambiguous)
    ctx.note("titulacion_filas_repetidas_en_clave", duplicates)


def build_postgrado(ctx: Ctx) -> None:
    _truncate(ctx, STEP_TABLES["postgrado"])
    ctx.execute(
        f"INSERT INTO {ctx.c('matricula_postgrado')} (persona_key, cod_programa, periodo, cod_estado, estado, "
        f"estado_matricula, periodo_admision, cod_admision, tipo_admision, catalogo, carga_id) "
        f"SELECT DISTINCT ON (persona_key, cod_programa, periodo) persona_key, cod_programa, periodo, cod_estado, "
        f"estado, estado_matricula, periodo_admision, cod_admision, tipo_admision, catalogo, carga_id "
        f"FROM {ctx.s('banner_estudiantes_postgrado')} WHERE cod_programa IS NOT NULL AND periodo IS NOT NULL "
        f"ORDER BY persona_key, cod_programa, periodo, fecha_estado DESC NULLS LAST, stg_id")
    ctx.counts["matricula_postgrado"] = ctx.rows(f"SELECT count(*) FROM {ctx.c('matricula_postgrado')}")[0][0]
    ctx.note("postgrado_filas_stg_sin_representar", ctx.rows(
        f"SELECT count(*) FROM {ctx.s('banner_estudiantes_postgrado')}")[0][0] - ctx.counts["matricula_postgrado"])
    _build_estados_postgrado(ctx)


def _build_estados_postgrado(ctx: Ctx) -> None:
    """P77: states and programs of postgrado from ``ban_estados_academicos_pos`` (names and level of every program)."""
    ctx.execute(
        f"INSERT INTO {ctx.c('estado_postgrado')} (persona_key, sorlcur, periodo, cod_programa, cod_estado, nombre_estado, "
        f"fecha_estado, cod_admision, periodo_admision, catalogo, carga_id) "
        f"SELECT persona_key, sorlcur, periodo, cod_programa, cod_estado, nombre_estado, fecha_estado, cod_admision, "
        f"periodo_admision, catalogo, carga_id FROM {ctx.s('ban_estados_academicos_pos')} WHERE periodo IS NOT NULL")
    ctx.counts["estado_postgrado"] = ctx.rows(f"SELECT count(*) FROM {ctx.c('estado_postgrado')}")[0][0]
    niveles = {cod: n for cod, n in ctx.rows(
        f"SELECT cod_banner, id_nivel FROM {ctx.s('programa_d')} WHERE cod_banner IS NOT NULL")}

    def rows() -> Iterator[tuple]:
        for cod, banner, estandar, first, last, n in ctx.rows(
            f"SELECT cod_programa, max(nombre_banner), max(nombre_estandar), min(periodo), max(periodo), count(*) "
            f"FROM {ctx.s('ban_estados_academicos_pos')} WHERE cod_programa IS NOT NULL AND periodo IS NOT NULL "
            f"GROUP BY cod_programa ORDER BY cod_programa"
        ):
            yield (cod, banner, estandar, nivel_postgrado(estandar, banner), niveles.get(cod), first, last, n)

    ctx.copy("programa_postgrado", ("cod_programa", "nombre_banner", "nombre_estandar", "nivel_derivado",
                                    "id_nivel_diccionario", "primer_periodo", "ultimo_periodo", "filas"), rows())
    ctx.note("postgrado_programas_sin_nombre_estandar", ctx.rows(
        f"SELECT count(*) FROM {ctx.c('programa_postgrado')} WHERE nombre_estandar IS NULL")[0][0])


BUILDERS: Dict[str, Callable[[Ctx], None]] = {
    "persona": build_persona, "catalogo": build_catalogo, "facultad": build_facultad, "postulacion": build_postulacion,
    "episodio": build_episodio, "intento": build_intento, "inscripcion": build_inscripcion,
    "seccion": build_seccion, "titulacion": build_titulacion, "postgrado": build_postgrado,
}


# ---- orchestration --------------------------------------------------------------------------------
def default_corte(conn, meta: str = "neural_meta") -> date:
    """Extraction cutoff = date of the Warehouse load of the states (RA04)."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT timestamp_carga_wh FROM {meta}.carga_extraccion "
                    f"WHERE fuente = 'ban_estados_academicos' AND estado = 'ok' ORDER BY carga_id DESC LIMIT 1")
        row = cur.fetchone()
    if row is None or row[0] is None:
        raise RuntimeError("no 'ok' extraction of ban_estados_academicos: pass the cutoff explicitly")
    return datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).date()


def build(conn, stg_schema: str = "neural_stg", core_schema: str = "neural_core", meta_schema: str = "neural_meta",
          corte: Optional[date] = None, only: Optional[Sequence[str]] = None,
          out: Callable[[str], None] = print) -> Ctx:
    steps = expand_steps(only)
    if only and set(steps) != set(only):
        out(f"dependents added: {[s for s in steps if s not in set(only)]}")
    original_autocommit = conn.autocommit
    conn.autocommit = False
    try:
        ctx = Ctx(conn, stg_schema, core_schema, meta_schema, corte or default_corte(conn, meta_schema), out)
        for step in steps:
            t0 = time.perf_counter()
            BUILDERS[step](ctx)
            out(f"{step:12} {time.perf_counter() - t0:7.1f}s")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = original_autocommit
    return ctx


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build neural_core from neural_stg (full, transactional rebuild).")
    parser.add_argument("--only", help="comma-separated steps; valid: " + ", ".join(STEPS) +
                                       " (dependents are rebuilt automatically)")
    args = parser.parse_args(argv)
    only = [s.strip() for s in args.only.split(",") if s.strip()] if args.only else None
    from ..common.db import dev_connection

    try:
        with dev_connection() as conn:
            ctx = build(conn, only=only)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for table, n in ctx.counts.items():
        print(f"core.{table:26} {n:>10}")
    for key, n in ctx.notes.items():
        print(f"nota {key:50} {n:>10}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
