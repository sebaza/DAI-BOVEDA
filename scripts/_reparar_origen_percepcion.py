"""Repara el `origen` perdido en percepcion_hecho_diario.

QUÉ PASÓ
--------
El worker distingue ingesta UCN (`origen='interno'`) de cuentas ajenas
(`'externo'`) y agrupa los hechos por (fecha, ORIGEN, campus, facultad, depto,
tema). La Torre tenía el modelo desactualizado: `curacion.reagregar()` hacía
`delete(H)` + reinsert SIN pasar `origen`, y como TODA corrección manual llama a
esa función, la columna quedó en NULL para la tabla entera.

Comprobado sobre la base real: `percepcion_cuenta.origen` conserva 'interno' en
sus 73 filas (la Torre no reagrega cuentas), mientras `percepcion_hecho_diario`
tiene las 894 en NULL. Las 376 correcciones manuales son del 05-07/08/2026.

El trabajo humano NO se perdió: sigue en `percepcion_correccion` (376 filas) y en
`percepcion_score` (329 marcados `correccion_manual`). Lo único perdido es
`origen`, y se recupera porque se DERIVA de la cuenta.

CÓMO REPARA
-----------
* Si todas las cuentas comparten un mismo origen, cada hecho es de ese origen sin
  ambigüedad → UPDATE quirúrgico, no se reconstruye nada.
* Si hay MEZCLA de orígenes, una fila de hecho puede agregar comentarios de
  cuentas de distinto origen y el UPDATE sería una adivinanza. En ese caso el
  script NO toca nada y pide reconstruir con `curacion.reagregar()`, que ya
  quedó arreglado y recompone el grano correcto desde comentario⋈score⋈cuenta.

Es DRY-RUN por defecto: sin `--aplicar` solo diagnostica y no escribe una coma.
Con `--aplicar` copia la base a backups/ antes de tocarla.

Uso:
    backend\\.venv\\Scripts\\python.exe scripts/_reparar_origen_percepcion.py [ruta.db]
    backend\\.venv\\Scripts\\python.exe scripts/_reparar_origen_percepcion.py --aplicar
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):          # Windows: la consola es cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB_POR_DEFECTO = (
    r"C:/Users/sezad/Documents/GitHub/Sentiment_Analisys_University/percepcion_real.db"
)
ORIGEN_INTERNO = "interno"


def _columnas(con, tabla: str) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info({tabla})")}


def _diagnostico(con) -> dict:
    cuentas = dict(
        con.execute("select coalesce(origen,'(NULL)'), count(*) "
                    "from percepcion_cuenta group by 1").fetchall()
    )
    hechos = dict(
        con.execute("select coalesce(origen,'(NULL)'), count(*) "
                    "from percepcion_hecho_diario group by 1").fetchall()
    )
    return {"cuentas": cuentas, "hechos": hechos}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aplicar = "--aplicar" in sys.argv
    ruta = args[0] if args else os.getenv("PERCEPCION_DB_VERIFICACION") or DB_POR_DEFECTO
    if not Path(ruta).exists():
        print(f"[X] No existe la base: {ruta}")
        return 2

    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    if "origen" not in _columnas(con, "percepcion_hecho_diario"):
        print("[X] La tabla de hechos no tiene la columna `origen`. Corré primero la "
              "migración del worker (migrar_origen_externo.py).")
        return 2

    d = _diagnostico(con)
    con.close()
    print(f"Base: {ruta}\n")
    print(f"  percepcion_cuenta.origen        -> {d['cuentas']}")
    print(f"  percepcion_hecho_diario.origen  -> {d['hechos']}")

    a_reparar = d["hechos"].get("(NULL)", 0)
    if a_reparar == 0:
        print("\n[OK] No hay filas con `origen` en NULL. Nada que reparar.")
        return 0

    origenes_reales = {o for o in d["cuentas"] if o != "(NULL)"}
    print(f"\n  Filas de hechos a reparar: {a_reparar}")

    if len(origenes_reales) > 1:
        print("\n[!] Hay MÁS DE UN origen entre las cuentas: "
              f"{sorted(origenes_reales)}.")
        print("    Una fila de hechos puede agregar comentarios de cuentas de distinto")
        print("    origen, así que un UPDATE plano sería una adivinanza. NO se tocó nada.")
        print("    Reconstruí con `curacion.reagregar()` (ya arreglado): recompone el")
        print("    grano (fecha, origen, campus, facultad, depto, tema) desde la fuente.")
        return 1

    destino = origenes_reales.pop() if origenes_reales else ORIGEN_INTERNO
    print(f"  Todas las cuentas son '{destino}' -> el origen de cada hecho es "
          f"'{destino}' sin ambigüedad.")

    if not aplicar:
        print("\n[DRY-RUN] No se escribió nada. Volvé a correr con --aplicar para reparar.")
        return 0

    respaldo = Path(ruta).parent / "backups" / (
        f"{Path(ruta).stem}_pre_reparar_origen_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    respaldo.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ruta, respaldo)
    print(f"\n  Respaldo: {respaldo}")

    escritura = sqlite3.connect(ruta)
    cur = escritura.execute(
        "update percepcion_hecho_diario set origen=? where origen is null", (destino,)
    )
    escritura.commit()
    n = cur.rowcount
    quedan = escritura.execute(
        "select count(*) from percepcion_hecho_diario where origen is null"
    ).fetchone()[0]
    escritura.close()
    print(f"  Filas reparadas: {n}")
    print(f"  Quedan en NULL:  {quedan}")
    return 0 if quedan == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
