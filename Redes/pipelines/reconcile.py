"""Gate 2 reconciliation: stg vs Warehouse, privacy invariants and core vs the discovery evidence.

Writes ``neural_meta.auditoria_resultado`` (one row per check) and prints a table. Only counts are
read or printed; no row, key or RUT ever appears in the output. A mismatch is recorded with its
explanation, never forced to pass.

CLI: ``python -m pipelines.reconcile [--markdown PATH] [--no-warehouse]``
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from .extract import sources as S

RUT_LIKE = "^[0-9]{7,8}-?[0-9Kk]$"
HEX64 = "^[0-9a-f]{64}$"

# r3#R13: evaluated grades linked to a section, per year (count, percent)
R13 = {2016: (89591, 90.4), 2017: (91630, 69.7), 2018: (92196, 82.3), 2019: (89649, 95.7), 2020: (93575, 96.9),
       2021: (98451, 96.4), 2022: (90948, 81.9), 2023: (95710, 71.3), 2024: (98553, 93.6), 2025: (105166, 95.5),
       2026: (59074, 77.9)}


@dataclass
class Check:
    chequeo: str
    esperado: str
    obtenido: str
    ok: bool
    explicacion: str
    fuente: str = "ban_estados_academicos"   # which extraction run the result is attached to


# Known causes of expected differences, filled from observation (see docs/06_reconciliacion_gate2.md).
EXPLANATIONS: Dict[str, str] = {}


def _fmt(v) -> str:
    return f"{v:,}".replace(",", ".") if isinstance(v, int) and not isinstance(v, bool) else str(v)


class Reconciler:
    def __init__(self, dev, wh=None):
        self.dev, self.wh = dev, wh
        self.checks: List[Check] = []
        self.timings: Dict[str, float] = {}

    # ---- helpers -----------------------------------------------------------------------------------
    def val(self, sql: str, params: Sequence = ()):
        with self.dev.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        return None if row is None else row[0]

    def rows(self, sql: str, params: Sequence = ()):
        with self.dev.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def add(self, chequeo: str, esperado, obtenido, ok: Optional[bool] = None, why: str = "",
            fuente: str = "ban_estados_academicos") -> Check:
        good = (esperado == obtenido) if ok is None else ok
        if good:
            expl = why or "coincide"
        else:
            expl = why or EXPLANATIONS.get(chequeo, "sin explicación registrada")
        c = Check(chequeo, _fmt(esperado), _fmt(obtenido), bool(good), expl, fuente)
        self.checks.append(c)
        return c

    def timed(self, name: str, fn: Callable[[], None]) -> None:
        t0 = time.perf_counter()
        fn()
        self.timings[name] = time.perf_counter() - t0

    # ---- A. staging == Warehouse ---------------------------------------------------------------------
    def check_sources(self) -> None:
        for src in S.SOURCES:
            stg = self.val(f"SELECT count(*) FROM neural_stg.{src.stg_table}")
            if self.wh is not None:
                with self.wh.cursor() as cur:
                    cur.execute(f"SELECT count(*) FROM {src.view}")
                    origin = int(cur.fetchone()[0])
                self.wh.rollback()
                what = "recuento en vivo de la vista"
            else:
                origin = self.val("SELECT filas_origen FROM neural_meta.carga_extraccion WHERE fuente = %s "
                                  "AND estado = 'ok' ORDER BY carga_id DESC LIMIT 1", (src.fuente,))
                what = "filas_origen registrado en la extracción"
            self.add(f"stg:{src.fuente}", origin, stg, why=what if origin == stg else "", fuente=src.fuente)

    # ---- B. privacy ----------------------------------------------------------------------------------
    def check_privacy(self) -> None:
        key_cols = self.rows(
            "SELECT table_schema, table_name, column_name FROM information_schema.columns "
            "WHERE table_schema IN ('neural_stg', 'neural_core') AND column_name IN ('persona_key', 'docente_key') "
            "ORDER BY 1, 2, 3")
        bad_total, scanned = 0, 0
        for schema, table, col in key_cols:
            n = self.val(f"SELECT count(*) FROM {schema}.{table} WHERE {col} IS NOT NULL AND {col} !~ '{HEX64}'")
            bad_total += n
            scanned += 1
            if n:
                self.add(f"llave:{schema}.{table}.{col}", 0, n, why="formato distinto de HMAC-SHA256 hex")
        self.add("llaves_no_hex64", 0, bad_total, why=f"{scanned} columnas persona_key/docente_key revisadas")

        text_cols: Dict[tuple, List[str]] = {}
        for schema, table, col in self.rows(
            "SELECT table_schema, table_name, column_name FROM information_schema.columns "
            "WHERE table_schema IN ('neural_stg', 'neural_core') AND data_type = 'text' "
            "AND column_name NOT IN ('persona_key', 'docente_key') ORDER BY 1, 2, ordinal_position"
        ):
            text_cols.setdefault((schema, table), []).append(col)
        total, per_table = 0, []
        for (schema, table), cols in text_cols.items():
            exprs = ", ".join(f"count(*) FILTER (WHERE {c} ~ '{RUT_LIKE}')" for c in cols)
            counts = self.rows(f"SELECT {exprs} FROM {schema}.{table}")[0]
            n = sum(counts)
            total += n
            if n:
                hit = [c for c, k in zip(cols, counts) if k]
                per_table.append(f"{schema}.{table}({','.join(hit)})")
        self.add("rut_like_en_columnas_texto", 0, total,
                 why=f"{sum(len(c) for c in text_cols.values())} columnas de texto en {len(text_cols)} tablas"
                     + (f"; con coincidencias: {'; '.join(per_table)}" if per_table else ""))

    # ---- C. core vs evidence -------------------------------------------------------------------------
    def check_core(self) -> None:
        v = self.val
        add = self.add
        add("core:evento_estado", 735_932, v("SELECT count(*) FROM neural_core.evento_estado"),
            fuente="ban_estados_academicos")
        add("core:evento_estado = stg", v("SELECT count(*) FROM neural_stg.ban_estados_academicos"),
            v("SELECT count(*) FROM neural_core.evento_estado"))
        add("core:episodio_programa", 57_561, v("SELECT count(*) FROM neural_core.episodio_programa"))
        add("core:persona con estados", 49_582,
            v("SELECT count(*) FROM neural_core.persona WHERE primer_periodo_estados IS NOT NULL"))
        add("core:personas con estados = stg", v("SELECT count(DISTINCT persona_key) FROM neural_stg.ban_estados_academicos"),
            v("SELECT count(*) FROM neural_core.persona WHERE primer_periodo_estados IS NOT NULL"))
        add("core:persona total", "informativo",
            v("SELECT count(*) FROM neural_core.persona"), ok=True,
            why="unión de estados, historia, inscripciones, titulados y postgrado")
        add("core:intento_asignatura", 2_670_731, v("SELECT count(*) FROM neural_core.intento_asignatura"),
            fuente="ban_historia_notas")
        add("core:intentos DPA", 129_258, v("SELECT count(*) FROM neural_core.intento_asignatura WHERE nota_parse = 'dpa'"),
            fuente="ban_historia_notas")
        add("core:intentos nota 4,0", 196_982,
            v("SELECT count(*) FROM neural_core.intento_asignatura WHERE nota_parse = 'numeric' AND nota_numerica = 4.0"),
            fuente="ban_historia_notas")
        add("core:intento con 1 episodio candidato", 1_860_553,
            v("SELECT count(*) FROM neural_core.intento_asignatura WHERE episodio_id IS NOT NULL"), fuente="ban_historia_notas")
        add("core:intento con 0 candidatos", 801_181,
            v("SELECT count(*) FROM neural_core.intento_asignatura WHERE sin_episodio"), fuente="ban_historia_notas")
        add("core:intento con 2+ candidatos", 8_997,
            v("SELECT count(*) FROM neural_core.intento_asignatura WHERE episodio_ambiguo"), fuente="ban_historia_notas")
        add("core:intento sin pérdida ni multiplicación", v("SELECT count(*) FROM neural_stg.ban_historia_notas"),
            v("SELECT count(*) FROM neural_core.intento_asignatura"), fuente="ban_historia_notas")

        add("core:estados con cod_admision NULL", 12,
            v("SELECT count(*) FROM neural_core.evento_estado WHERE cod_admision IS NULL OR btrim(cod_admision) = ''"))
        add("core:fecha_estado NULL", 159_885,
            v("SELECT count(*) FROM neural_core.evento_estado WHERE fecha_estado_original IS NULL"))
        add("core:fecha_estado futura (marcador)", 21,
            v("SELECT count(*) FROM neural_core.evento_estado WHERE fecha_marcador"))
        base = "FROM neural_core.evento_estado WHERE fecha_estado_original IS NULL"
        why_order = ("r3#R12 se midió en orden sorlcur; el orden canónico (periodo, sorlcur) y el vecino más cercano "
                     "cambian la clasificación (ver chequeos 'R12 paridad' y 'R12 ventana ilimitada, orden canónico')")
        both = v(f"SELECT count(*) {base} AND fecha_min IS NOT NULL AND fecha_max IS NOT NULL")
        inverted = v(f"SELECT count(*) {base} AND intervalo_invertido")
        add("core:NULL con fecha a ambos lados (incluye invertidos)", 110_733, both + inverted, why=why_order)
        add("core:NULL solo con fecha anterior", 8_967,
            v(f"SELECT count(*) {base} AND fecha_min IS NOT NULL AND fecha_max IS NULL"), why=why_order)
        add("core:NULL solo con fecha posterior", 38_927,
            v(f"SELECT count(*) {base} AND fecha_min IS NULL AND fecha_max IS NOT NULL AND NOT sin_intervalo"), why=why_order)
        add("core:NULL sin vecinos", 1_258, v(f"SELECT count(*) {base} AND sin_intervalo AND NOT intervalo_invertido"))
        add("core:NULL con intervalo invertido", 5_068, inverted,
            why="R12 compara el máximo anterior con el mínimo posterior en orden sorlcur; aquí vecino más cercano en "
                "orden canónico (los descensos de fecha bajan al ordenar por período, r3#R05)")
        # Same data, R12's own method (sorlcur order, unbounded window): must reproduce r3#R12 exactly.
        par = self._r12("sorlcur")
        for name, exp, got in zip(("ambos lados", "solo anterior", "solo posterior", "sin vecinos", "invertido"),
                                  (110_733, 8_967, 38_927, 1_258, 5_068), par):
            add(f"core:R12 paridad (orden sorlcur) {name}", exp, got)
        can = self._r12("orden_canonico")
        for name, got in zip(("ambos lados", "solo anterior", "solo posterior", "sin vecinos", "invertido"), can):
            add(f"core:R12 ventana ilimitada, orden canónico: {name}", "informativo", got, ok=True,
                why="mismo método de R12 aplicado al orden (periodo, sorlcur)")

        add("core:postulacion_via", 111_733, v("SELECT count(*) FROM neural_core.postulacion_via"), fuente="banner_admision")
        add("core:postulacion", 107_036, v("SELECT count(*) FROM neural_core.postulacion"), fuente="banner_admision")
        for col, exp in (("region_colegio", 7_352), ("comuna_colegio", 7_352), ("cod_comuna", 9_060)):
            add(f"core:R37 {col} vacío", exp,
                v(f"SELECT count(*) FROM neural_core.postulacion_via WHERE {col} IS NULL OR btrim({col}) = ''"),
                fuente="banner_admision")
        add("core:postulacion_via con puntaje no parseable", "informativo",
            v("SELECT count(*) FROM neural_core.postulacion_via WHERE NOT puntaje_parse_ok"), ok=True,
            why="textos de puntaje que no son número; el valor queda NULL con bandera", fuente="banner_admision")

        add("core:inscripcion (filas con estado)", 194_080,
            v("SELECT count(*) FROM neural_core.inscripcion_asignatura"), fuente="ban_inscripciones")
        add("core:inscripcion grano sin estado", 194_072,
            v("SELECT count(*) FROM (SELECT 1 FROM neural_core.inscripcion_asignatura "
              "GROUP BY periodo, persona_key, nrc, materia_curso_inscrito) x"), fuente="ban_inscripciones")
        add("core:inscripcion_equivalencia suma filas_origen = stg", v("SELECT count(*) FROM neural_stg.ban_inscripciones"),
            v("SELECT coalesce(sum(filas_origen), 0) FROM neural_core.inscripcion_equivalencia"), fuente="ban_inscripciones")
        add("core:inscripcion con estado_conflicto (grupos)", 8,
            v("SELECT count(*) FROM (SELECT 1 FROM neural_core.inscripcion_asignatura WHERE estado_conflicto "
              "GROUP BY periodo, persona_key, nrc, materia_curso_inscrito) x"), fuente="ban_inscripciones")

        add("core:personas tituladas", 19_589, v("SELECT count(DISTINCT persona_key) FROM neural_core.titulacion"),
            fuente="banner_titulados")
        add("core:titulacion filas = stg menos repetidas en clave",
            v("SELECT count(*) FROM (SELECT 1 FROM neural_stg.banner_titulados "
              "GROUP BY persona_key, codigo_carrera, catalogo, fecha_titulacion) x"),
            v("SELECT count(*) FROM neural_core.titulacion"), fuente="banner_titulados")
        add("core:estado U sin registro de titulado (P42)", 825,
            v("SELECT count(DISTINCT persona_key) FROM neural_core.evento_estado e WHERE cod_estado = 'U' "
              "AND NOT EXISTS (SELECT 1 FROM neural_core.titulacion t WHERE t.persona_key = e.persona_key)"),
            fuente="banner_titulados")
        add("core:personas con estado U", 18_959,
            v("SELECT count(DISTINCT persona_key) FROM neural_core.evento_estado WHERE cod_estado = 'U'"),
            fuente="banner_titulados")

        add("core:seccion (periodo, nrc)", 65_074, v("SELECT count(*) FROM neural_core.seccion"), fuente="ban_oferta_academica")
        add("core:secciones con más de un docente", 9_341,
            v("SELECT count(*) FROM (SELECT 1 FROM neural_core.seccion_docente GROUP BY periodo, nrc "
              "HAVING count(*) > 1) x"), fuente="ban_oferta_academica")

        add("core:programa", 185, v("SELECT count(*) FROM neural_core.programa"), fuente="programa_d")
        add("core:programa válidos", 170, v("SELECT count(*) FROM neural_core.programa WHERE valid_program"), fuente="programa_d")
        add("core:programa con predecesor", 15,
            v("SELECT count(*) FROM neural_core.programa WHERE programa_predecesor IS NOT NULL"), fuente="programa_d")
        add("core:predecesor inexistente", 1, v("SELECT count(*) FROM neural_core.programa WHERE predecesor_inexistente"),
            fuente="programa_d")
        add("core:asignatura_malla (programa, catálogo, asignatura)", 29_614,
            v("SELECT count(*) FROM neural_core.asignatura_malla"), fuente="ban_malla_programa")
        add("core:asignatura_malla sin pérdida (suma filas_origen = stg)", v("SELECT count(*) FROM neural_stg.ban_malla_programa"),
            v("SELECT coalesce(sum(filas_origen), 0) FROM neural_core.asignatura_malla"), fuente="ban_malla_programa")
        add("core:programa-catálogo de la malla oficial", 284,
            v("SELECT count(*) FROM (SELECT 1 FROM neural_core.asignatura_malla GROUP BY cod_programa, catalogo) x"),
            fuente="ban_malla_programa")
        add("core:prerrequisito aristas distintas", 31_996, v("SELECT count(*) FROM neural_core.prerrequisito"),
            fuente="malla_programa_prereq")
        add("core:prerrequisito suma filas_origen = stg", v("SELECT count(*) FROM neural_stg.malla_programa_prereq"),
            v("SELECT coalesce(sum(filas_origen), 0) FROM neural_core.prerrequisito"), fuente="malla_programa_prereq")
        add("core:prerrequisito asignatura en malla oficial (J24)", 28_859,
            v("SELECT count(*) FROM neural_core.prerrequisito WHERE asig_en_malla"), fuente="malla_programa_prereq")
        add("core:prerrequisito requisito en malla oficial (J25)", 12_175,
            v("SELECT count(*) FROM neural_core.prerrequisito WHERE req_en_malla"), fuente="malla_programa_prereq")
        # r3#R19 four-way classification, reproduced on the legacy malla_programa kept in stg (extraction parity)
        legacy = self.rows(
            "WITH e AS (SELECT DISTINCT cod_programa::bigint AS prog, catalogo, codigo_asignatura AS asig, "
            "codigo_asignatura_repreq AS req FROM neural_stg.malla_programa_prereq), "
            "m AS (SELECT DISTINCT cod_programa, catalogo, codigo_asignatura AS asig FROM neural_stg.malla_programa), "
            "mp AS (SELECT DISTINCT cod_programa, codigo_asignatura AS asig FROM neural_stg.malla_programa), "
            "ma AS (SELECT DISTINCT codigo_asignatura AS asig FROM neural_stg.malla_programa) "
            "SELECT count(*) FILTER (WHERE m2.asig IS NOT NULL), "
            "count(*) FILTER (WHERE m2.asig IS NULL AND p2.asig IS NOT NULL), "
            "count(*) FILTER (WHERE p2.asig IS NULL AND a2.asig IS NOT NULL), "
            "count(*) FILTER (WHERE a2.asig IS NULL) "
            "FROM e LEFT JOIN m m2 ON m2.cod_programa = e.prog AND m2.catalogo = e.catalogo AND m2.asig = e.req "
            "LEFT JOIN mp p2 ON p2.cod_programa = e.prog AND p2.asig = e.req LEFT JOIN ma a2 ON a2.asig = e.req")[0]
        add("stg:R19 requisito misma malla (legacy)", 12_255, legacy[0], fuente="malla_programa")
        add("stg:R19 requisito otro catálogo (legacy)", 986, legacy[1], fuente="malla_programa")
        add("stg:R19 requisito otro programa (legacy)", 17_448, legacy[2], fuente="malla_programa")
        add("stg:R19 requisito en ninguna malla (legacy)", 1_307, legacy[3], fuente="malla_programa")

        # r4#R35: grade rows vs official malla (same program+catalog / same program / any program / none)
        cov = self.rows(
            "WITH i AS (SELECT cod_carrera, catalogo, codigo_asignatura FROM neural_core.intento_asignatura), "
            "mm AS (SELECT DISTINCT cod_programa, catalogo, codigo_asignatura FROM neural_core.asignatura_malla), "
            "mp AS (SELECT DISTINCT cod_programa, codigo_asignatura FROM neural_core.asignatura_malla), "
            "ma AS (SELECT DISTINCT codigo_asignatura FROM neural_core.asignatura_malla) "
            "SELECT count(*) FILTER (WHERE mm.codigo_asignatura IS NOT NULL), "
            "count(*) FILTER (WHERE mm.codigo_asignatura IS NULL AND mp.codigo_asignatura IS NOT NULL), "
            "count(*) FILTER (WHERE mp.codigo_asignatura IS NULL AND ma.codigo_asignatura IS NOT NULL), "
            "count(*) FILTER (WHERE ma.codigo_asignatura IS NULL) FROM i "
            "LEFT JOIN mm ON mm.cod_programa = i.cod_carrera AND mm.catalogo = i.catalogo AND mm.codigo_asignatura = i.codigo_asignatura "
            "LEFT JOIN mp ON mp.cod_programa = i.cod_carrera AND mp.codigo_asignatura = i.codigo_asignatura "
            "LEFT JOIN ma ON ma.codigo_asignatura = i.codigo_asignatura")[0]
        for name, exp, got in (("mismo programa y catálogo", 2_065_392, cov[0]), ("otro catálogo del programa", 55_227, cov[1]),
                               ("otro programa", 125_823, cov[2]), ("ninguna malla", 424_289, cov[3])):
            add(f"core:R35 historia en malla ({name})", exp, got, fuente="ban_historia_notas")

        # r3#R13: coverage of evaluated grades by the academic offer, per year
        by_year = {int(y): (ev, vinc) for y, ev, vinc in self.rows(
            "SELECT left(i.periodo, 4), count(*) FILTER (WHERE upper(btrim(i.nota_texto)) <> 'DPA'), "
            "count(*) FILTER (WHERE upper(btrim(i.nota_texto)) <> 'DPA' AND s.nrc IS NOT NULL) "
            "FROM neural_core.intento_asignatura i LEFT JOIN neural_core.seccion s ON s.periodo = i.periodo AND s.nrc = i.nrc "
            "WHERE i.nrc IS NOT NULL AND btrim(i.nrc) <> '' GROUP BY 1")}
        for year, (exp_n, exp_pct) in R13.items():
            ev, vinc = by_year.get(year, (0, 0))
            pct = round(100.0 * vinc / ev, 1) if ev else 0.0
            self.add(f"core:R13 evaluadas vinculadas a oferta {year}", f"{exp_n} ({exp_pct}%)", f"{vinc} ({pct}%)",
                     fuente="ban_oferta_academica")

    def _r12(self, order_col: str):
        return self.rows(
            "WITH s AS (SELECT fecha_estado_original AS f, "
            f"max(fecha_estado_original) OVER (PARTITION BY persona_key ORDER BY {order_col} "
            "ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS a, "
            f"min(fecha_estado_original) OVER (PARTITION BY persona_key ORDER BY {order_col} "
            "ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING) AS d FROM neural_core.evento_estado) "
            "SELECT count(*) FILTER (WHERE a IS NOT NULL AND d IS NOT NULL), "
            "count(*) FILTER (WHERE a IS NOT NULL AND d IS NULL), count(*) FILTER (WHERE a IS NULL AND d IS NOT NULL), "
            "count(*) FILTER (WHERE a IS NULL AND d IS NULL), count(*) FILTER (WHERE a > d) FROM s WHERE f IS NULL")[0]

    # ---- persistence and report ------------------------------------------------------------------------
    def persist(self) -> None:
        carga = {fuente: self.val("SELECT carga_id FROM neural_meta.carga_extraccion WHERE fuente = %s AND estado = 'ok' "
                                  "ORDER BY carga_id DESC LIMIT 1", (fuente,)) for fuente in {c.fuente for c in self.checks}}
        with self.dev.cursor() as cur:
            for c in self.checks:
                cid = carga[c.fuente]
                if cid is None:
                    continue
                cur.execute(
                    "INSERT INTO neural_meta.auditoria_resultado (carga_id, chequeo, valor_esperado, valor_obtenido, ok, explicacion) "
                    "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (carga_id, chequeo) DO UPDATE SET "
                    "valor_esperado = EXCLUDED.valor_esperado, valor_obtenido = EXCLUDED.valor_obtenido, ok = EXCLUDED.ok, "
                    "explicacion = EXCLUDED.explicacion, medido_en = now()", (cid, c.chequeo, c.esperado, c.obtenido, c.ok, c.explicacion))
        self.dev.commit()

    def run(self) -> List[Check]:
        self.timed("fuentes", self.check_sources)
        self.timed("privacidad", self.check_privacy)
        self.timed("core", self.check_core)
        self.persist()
        return self.checks


def render(checks: Sequence[Check], width: int = 70) -> str:
    lines = [f"{'chequeo':62} {'esperado':>22} {'obtenido':>22} ok  explicación"]
    for c in checks:
        lines.append(f"{c.chequeo[:62]:62} {c.esperado[:22]:>22} {c.obtenido[:22]:>22} {'sí ' if c.ok else 'NO '} "
                     f"{c.explicacion[:width]}")
    return "\n".join(lines)


def render_markdown(checks: Sequence[Check]) -> str:
    out = ["| Chequeo | Esperado | Obtenido | OK | Explicación |", "|---|---|---|---|---|"]
    for c in checks:
        out.append(f"| `{c.chequeo}` | {c.esperado} | {c.obtenido} | {'sí' if c.ok else '**no**'} | {c.explicacion} |")
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Gate 2 reconciliation (counts only).")
    parser.add_argument("--markdown", help="also write the table as markdown to this path")
    parser.add_argument("--no-warehouse", action="store_true", help="use recorded filas_origen instead of live counts")
    args = parser.parse_args(argv)
    from .common.db import dev_connection, warehouse_connection

    try:
        with dev_connection() as dev:
            if args.no_warehouse:
                rec = Reconciler(dev)
                checks = rec.run()
            else:
                with warehouse_connection(statement_timeout_ms=600_000) as wh:
                    rec = Reconciler(dev, wh)
                    checks = rec.run()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(render(checks))
    bad = [c for c in checks if not c.ok]
    print(f"\n{len(checks)} chequeos; {len(checks) - len(bad)} ok; {len(bad)} con diferencia")
    print("tiempos: " + ", ".join(f"{k}={v:.1f}s" for k, v in rec.timings.items()))
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(render_markdown(checks) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
