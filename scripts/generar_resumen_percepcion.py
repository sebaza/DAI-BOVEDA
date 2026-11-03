"""Genera el RESUMEN SEMANAL de Percepción después de una ingesta (Bóveda local).

QUÉ HACE
--------
Llama a `resumen_llm.generar_tras_ingesta` sobre las últimas `--semanas` semanas con datos
(nivel universidad). Para cada una compara la huella de sus insumos con la guardada: si los datos
no cambiaron, devuelve el resumen en caché y NO llama al modelo (costo 0). Solo paga por las
semanas cuyos datos cambiaron con la ingesta. `--forzar` paga de nuevo aunque nada haya cambiado
(solo para cuando cambia el prompt).

Se corre DESPUÉS de sincronizar y agrupar subtemas, y ANTES de publicar en el almacén: la tabla
`percepcion_resumen_semanal` viaja en la publicación y el sitio público solo la lee.

CONEXIÓN Y CLAVES
-----------------
Usa las URLs de Percepción y la clave del modelo (`ANTHROPIC_API_KEY` u `OPENAI_API_KEY`) de
`backend/.env`. Imprime solo semanas, conteos, costo y avisos; nunca el texto del resumen.

Uso:
    backend\\.venv\\Scripts\\python.exe -I scripts\\generar_resumen_percepcion.py --semanas 2
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BACKEND = RAIZ / "backend"
if str(BACKEND) not in sys.path:      # `python -I` no agrega el cwd
    sys.path.insert(0, str(BACKEND))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Genera el resumen semanal de Percepción tras una ingesta.")
    ap.add_argument("--semanas", type=int, default=2,
                    help="semanas hacia atrás desde la última con datos (1..12, por defecto 2)")
    ap.add_argument("--forzar", action="store_true",
                    help="vuelve a pagar aunque los datos no hayan cambiado (solo si cambió el prompt)")
    args = ap.parse_args(argv)
    if not 1 <= args.semanas <= 12:
        print("--semanas debe estar entre 1 y 12.", file=sys.stderr)
        return 2

    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:
            pass

    from app.services.percepcion import resumen_llm

    try:
        r = resumen_llm.generar_tras_ingesta(semanas=args.semanas, forzar=args.forzar)
    except Exception as e:  # noqa: BLE001 - el mensaje del driver puede traer la URL
        print(f"No se pudo generar ({type(e).__name__}).", file=sys.stderr)
        return 1

    if r.get("status") != "ok":
        print(f"Sin cambios: {r.get('reason', r.get('status'))}")
        return 0
    for s in r["semanas"]:
        estado = "generado" if s["regenerado"] else ("sin datos" if not s["hay_datos"] else "en caché")
        costo = f" US$ {s['costo_usd']:.4f}" if s["regenerado"] and s["costo_usd"] else ""
        print(f"  semana {s['semana']}: {estado}, {s['n_comentarios']} comentarios{costo}")
        if s["aviso"]:
            print(f"    aviso: {s['aviso']}")
    print(f"Resúmenes generados: {r['generados']} · costo total US$ {r['costo_usd_total']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
