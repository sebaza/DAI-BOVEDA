"""Carga el calendario académico UCN del JSON versionado a la base de Percepción.

POR QUÉ HACE FALTA ESTE SCRIPT
------------------------------
`backend/app/data/percepcion_calendario_ucn.json` es la FUENTE del calendario y
está versionado, pero **nadie lo carga automáticamente**: `calendario.cargar()`
existe desde hace tiempo y no la llamaba ningún endpoint ni el arranque de la app.
Consecuencia real, encontrada al mirar el panel: el archivo declaraba 109 eventos
y la base tenía 102 — los 7 agregados en la auditoría de septiembre 2026 (la
paralización de abril-mayo que faltaba y las 6 marcas de duelo) estaban escritos
y sin efecto.

No se carga al arranque a propósito: la app arranca en Cloud Run con escala a
cero y no corresponde escribir en la base del worker en cada arranque en frío.

QUÉ HACE, Y QUÉ NO
------------------
`calendario.cargar()` es IDEMPOTENTE — la clave natural es (nombre, fecha_inicio)—
así que correrlo dos veces no duplica nada. Actualiza los eventos que cambiaron y
RETIRA los que ya no están en el archivo... pero **solo los que tienen
`fuente='calendario_ucn'`**: los eventos cargados a mano desde el panel llevan
`fuente` NULL y nunca se tocan. Sin ese filtro, recargar el calendario borraría
trabajo de otra persona.

Uso:
    backend\\.venv\\Scripts\\python.exe scripts/_cargar_calendario_percepcion.py            # dry-run
    backend\\.venv\\Scripts\\python.exe scripts/_cargar_calendario_percepcion.py --aplicar
    backend\\.venv\\Scripts\\python.exe scripts/_cargar_calendario_percepcion.py --aplicar --no-sincronizar

Sin `--aplicar` no escribe nada: informa qué haría. Es el mismo patrón que
`_reparar_origen_percepcion.py`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.services.percepcion import calendario  # noqa: E402
from app.services.percepcion.db import PercepcionWriteSessionLocal, percepcion_write_engine  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aplicar", action="store_true",
                    help="escribir de verdad (sin esto es dry-run)")
    ap.add_argument("--no-sincronizar", action="store_true",
                    help="no retirar los eventos que ya no están en el archivo")
    args = ap.parse_args()

    print(f"Base: {percepcion_write_engine.url}")
    print(f"Archivo: {calendario._ruta()}")
    if not calendario._ruta().exists():
        print("[ERROR] no se encuentra el JSON del calendario.")
        return 2

    db = PercepcionWriteSessionLocal()
    try:
        antes = calendario.cargar(db, dry_run=True,
                                  sincronizar=not args.no_sincronizar)
        print(f"\nEn el archivo: {antes['en_archivo']} eventos "
              f"({antes['disruptivos']} disruptivos)")
        print(f"  por confianza: " + ", ".join(
            f"{k}={v}" for k, v in antes["por_confianza"].items()))
        print(f"\nContra la base:")
        print(f"  nuevos       {antes['nuevos']}")
        print(f"  actualizados {antes['actualizados']}")
        print(f"  retirados    {antes['retirados']}")
        print(f"  sin cambios  {antes['sin_cambios']}")

        if not (antes["nuevos"] or antes["actualizados"] or antes["retirados"]):
            print("\nLa base ya está al día. No hay nada que hacer.")
            return 0

        if not args.aplicar:
            print("\n(dry-run — nada se escribió). Repetí con --aplicar para hacerlo.")
            return 0

        r = calendario.cargar(db, sincronizar=not args.no_sincronizar)
        print(f"\nAPLICADO: +{r['nuevos']} nuevos, {r['actualizados']} actualizados, "
              f"{r['retirados']} retirados.")

        # Control: se relee para confirmar que quedó lo que se esperaba.
        control = calendario.cargar(db, dry_run=True,
                                    sincronizar=not args.no_sincronizar)
        ok = not (control["nuevos"] or control["actualizados"] or control["retirados"])
        print(f"Control: {'OK — la base coincide con el archivo' if ok else 'DIFIERE, revisar'}")
        disr = calendario.episodios_disruptivos(db)
        duelo = calendario.episodios_duelo(db)
        print(f"  episodios disruptivos en la base: {len(disr)}")
        print(f"  marcas de duelo en la base:       {len(duelo)}")
        return 0 if ok else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
