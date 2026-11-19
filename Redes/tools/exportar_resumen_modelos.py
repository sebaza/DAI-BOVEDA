"""Export the aggregate benchmark results of the models into ``neural_mart.resumen_modelos*`` (migration 016) and the
per-task summary T1-T6 into ``neural_mart.resumen_tarea*`` (migration 023).

    python tools/exportar_resumen_modelos.py [--artefactos DIR]

Reads ``artefactos/resultados_t{1,2,3,45,6}.json`` and, if present, ``resultados_t1_beneficios.json`` and ``resultados_t1_beneficios_cargas.json`` (both gitignored, optional), ``grupos_todos.json`` (model figures of every group, any size, with their 95 % intervals; REQUIRED: the run stops with a clear error if it is missing or holds another model than the registry's kept one), ``vista_historica.json`` (view "Lo que pasó", optional), ``vista_proyeccion.json`` (tab "Lo que viene", optional), the layer sizes of the model code and the program and
faculty names of ``neural_core``, and replaces the content of the summary tables (each set in one transaction).
Aggregates only: no prediction, no person key; every group is published, whatever its size. Prints counts, never values.
Needs the ``DEV_*`` environment variables of the localhost database.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from pipelines.marts import resumen_modelos as RM  # noqa: E402
from pipelines.marts import resumen_tareas as RT  # noqa: E402
from pipelines.marts import vista_historica as VH  # noqa: E402
from pipelines.marts import vista_proyeccion as VPR  # noqa: E402


def cargar(artefactos: Path, ids=(1, 2, 3)):
    return [json.loads((artefactos / f"resultados_t{i}.json").read_text(encoding="utf-8")) for i in ids]


def cargar_beneficios(artefactos: Path, nombre: str = "resultados_t1_beneficios.json"):
    """``resultados_t1_beneficios.json`` (T1 ablation with benefits, 16-11-2026) or ``None`` when it was not produced."""
    ruta = artefactos / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


# (task, cut, kept model) of the registry ``evaluation.modelos_conservados.CLAVES`` -> block of ``grupos_todos.json``
BLOQUE_DE_CLAVE = {("t1", 1, "cb_acad"): ("t1", "base"), ("t1", 1, "cb_ben_pit"): ("t1", "beneficios_corte"),
                   ("t1", 2, "lr_acad"): ("t1", "base"), ("t2", 0, "cb_c_nuevas"): ("t2", "base"),
                   ("t3", 0, "dt_lr_adm"): ("t3", "base"), ("t3", 2, "nn_gru"): ("t3", "base"), ("t3", 4, "nn_gru"): ("t3", "base"),
                   ("t5", 2, "gru_adm"): ("t5", "actual"), ("t5", 4, "gru_agg"): ("t5", "actual")}


def cargar_grupos_todos(artefactos: Path):
    """``grupos_todos.json`` (every group of the kept models, ``evaluation/grupos_todos.py``). It is required: without it the
    summaries would silently fall back to the benchmark's size-filtered tables, so a missing file stops the export."""
    doc = cargar_beneficios(artefactos, "grupos_todos.json")
    if doc is None:
        raise FileNotFoundError(f"{artefactos / 'grupos_todos.json'} is missing: generate it with `python -m evaluation.grupos_todos` "
                                "before exporting")
    return doc


def validar_grupos_todos(doc) -> None:
    """Every kept model of the registry must have its block, and the block must be of that model (else ``ValueError``)."""
    from evaluation.modelos_conservados import CLAVES

    if set(BLOQUE_DE_CLAVE) != set(CLAVES):
        raise RuntimeError("the registry of kept models changed: update BLOQUE_DE_CLAVE")
    for (tarea, k, modelo), (_, variante) in BLOQUE_DE_CLAVE.items():
        blk = ((((doc.get("tareas") or {}).get(tarea)) or {}).get(variante) or {}).get(str(k)) or {}
        if not blk.get("dimensiones"):
            raise ValueError(f"grupos_todos.json has no block {tarea}/{variante}/k={k} (kept model {modelo}): regenerate it with "
                             "`python -m evaluation.grupos_todos`")
        if blk.get("modelo") != modelo:
            raise ValueError(f"grupos_todos.json holds {blk.get('modelo')!r} for {tarea}/{variante}/k={k} but the registry keeps "
                             f"{modelo!r}: regenerate it with `python -m evaluation.grupos_todos`")


def diccionario_programas(conn):
    """``cod_programa -> (program name, faculty name)`` from ``neural_core`` (faculty names, never codes: D82)."""
    from evaluation.facultades import cargar_programas

    d = cargar_programas(conn)
    return {str(cod): (r["nombre_programa"], r["facultad_nombre"]) for cod, r in d.iterrows()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artefactos", type=Path, default=RAIZ / "artefactos")
    args = parser.parse_args(argv)
    try:
        from pipelines.common.db import dev_connection

        resumen = RM.construir(*cargar(args.artefactos))
        resumen["info"] += RM.arquitectura_desde_codigo()
        t1, t2, t3 = cargar(args.artefactos)
        t45, t6 = cargar(args.artefactos, ("45", 6))
        grupos_todos = cargar_grupos_todos(args.artefactos)
        validar_grupos_todos(grupos_todos)
        with dev_connection() as conn:
            cuentas = RM.escribir(conn, resumen)
            tareas = RT.construir(t1, t2, t3, t45, t6, diccionario_programas(conn), cargar_beneficios(args.artefactos),
                                 cargar_beneficios(args.artefactos, "resultados_t1_beneficios_cargas.json"),
                                 grupos_todos)
            cuentas.update(RT.escribir(conn, tareas))
            vista = cargar_beneficios(args.artefactos, "vista_historica.json")
            if vista is not None:                       # optional: view "Lo que pasó" (migration 029)
                cuentas.update(VH.escribir(conn, vista))
            proyeccion = cargar_beneficios(args.artefactos, "vista_proyeccion.json")
            if proyeccion is not None:                  # optional: tab "Lo que viene" (migration 032)
                cuentas.update(VPR.escribir(conn, proyeccion))
    except Exception as exc:  # no secrets in these messages
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for tabla, n in cuentas.items():
        print(f"{tabla:28}{n:>8,} filas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
