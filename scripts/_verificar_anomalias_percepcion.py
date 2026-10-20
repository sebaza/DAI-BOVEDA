"""Calibración de la detección de anomalías de Percepción contra datos REALES.

Corre la detección semanal sobre la base del worker y la contrasta con los
eventos institucionales cargados en `percepcion_evento`. Sirve para responder la
única pregunta que importa: ¿el Termómetro marca el paro, y sin inundar de
falsos positivos?

Antes de este trabajo la respuesta era NO: sobre la serie trailing el |z| máximo
en toda la ventana del paro 2026 era 1.98 contra un umbral de 2.5 → cero
anomalías, mientras las 3 que sí marcaba en 4 años caían fuera de todo evento.

Es de SOLO LECTURA (abre la base con `mode=ro`): no toca los datos del worker.

Uso:
    backend\\.venv\\Scripts\\python.exe scripts/_verificar_anomalias_percepcion.py [ruta.db]

Sin argumento usa PERCEPCION_DB_VERIFICACION o la ruta por defecto del worker.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
if hasattr(sys.stdout, "reconfigure"):          # Windows: la consola es cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import create_engine, select                       # noqa: E402
from sqlalchemy.orm import sessionmaker                            # noqa: E402

from app.services.percepcion import repository as R                # noqa: E402
from app.services.percepcion.models import PercepcionEvento as E   # noqa: E402

DB_POR_DEFECTO = (
    r"C:/Users/sezad/Documents/GitHub/Sentiment_Analisys_University/percepcion_real.db"
)

# Criterios de aceptación. Sin un número fijado de antemano, "mejoró" es una
# opinión.
#
# El denominador es el HISTÓRICO COMPLETO, no el año del evento. El primer
# criterio que se escribió medía el ruido sobre 2026 y daba 20% — pero 2026 es el
# año DEL PARO: un año con conflicto TIENE que tener más semanas marcadas, o el
# detector no sirve para nada. Medir ahí es contarse las señales verdaderas como
# ruido. Sobre las 125 semanas del corpus da 4.8%.
MAX_PCT_SEMANAS_MARCADAS = 15.0
# Ventana en la que una semana marcada se considera EXPLICADA por un evento: la
# antesala (donde vive la señal temprana) y el cierre (la conversación no se
# apaga el día que termina el paro).
SEMANAS_ANTESALA = 8
SEMANAS_CIERRE = 2


def _abrir(ruta: str):
    if not Path(ruta).exists():
        print(f"[X] No existe la base: {ruta}")
        sys.exit(2)
    engine = create_engine(f"sqlite:///file:{ruta}?mode=ro&uri=true")
    return sessionmaker(bind=engine, future=True)()


def main() -> int:
    ruta = (
        sys.argv[1] if len(sys.argv) > 1
        else os.getenv("PERCEPCION_DB_VERIFICACION") or DB_POR_DEFECTO
    )
    db = _abrir(ruta)
    print(f"Base: {ruta}\n")

    eventos = db.execute(select(E).order_by(E.fecha_inicio)).scalars().all()
    if not eventos:
        print("[!] No hay eventos cargados: sin referencia contra la cual medir.")
    for e in eventos:
        print(f"Evento: {e.nombre} [{e.tipo}] {e.fecha_inicio} -> {e.fecha_fin or e.fecha_inicio}")

    # "Todo" el histórico, sin filtro dimensional: es la vista por defecto.
    serie = R._deteccion_semanal(db, 36500, None, None, None, None, 1.0)
    if not serie:
        print("[X] La detección no devolvió serie.")
        return 2

    marcadas = [p for p in serie if p["es_anomalia"]]
    con_severidad = [p for p in serie if p["severidad"] > 0]
    print(f"\nSemanas con datos: {len(serie)}")
    print(f"Semanas marcadas:  {len(marcadas)} ({100 * len(marcadas) / len(serie):.1f}%)")
    print(f"Semanas con severidad > 0: {len(con_severidad)}")

    print("\n--- SEMANAS MARCADAS ---")
    print("semana      sev   idx    z_idx  %neg  z_neg  n    term  motivos")
    for p in sorted(marcadas, key=lambda x: x["semana"]):
        idx = f"{p['indice']:5.1f}" if p["indice"] is not None else "    -"
        zi = f"{p['z_indice']:6.2f}" if p["z_indice"] is not None else "     -"
        pn = f"{p['pct_neg']:5.1f}" if p["pct_neg"] is not None else "    -"
        zn = f"{p['z_pct_neg']:6.2f}" if p["z_pct_neg"] is not None else "     -"
        print(f"{p['semana']}  {p['severidad']:.2f}  {idx} {zi} {pn} {zn}  "
              f"{p['n']:4d}  {p['n_terminos_neg']}/{p['n_terminos']}   "
              f"{','.join(p['motivos'])}")

    # ---- Contraste contra cada evento cargado ----
    print("\n--- CONTRASTE CONTRA LOS EVENTOS ---")
    por_semana = {p["semana"]: p for p in serie}
    ok_evento = True
    for e in eventos:
        fin = e.fecha_fin or e.fecha_inicio
        semanas_evento = sorted({
            R._lunes(e.fecha_inicio + timedelta(days=d))
            for d in range((fin - e.fecha_inicio).days + 1)
        })
        dentro = [por_semana[s] for s in semanas_evento if s in por_semana]
        marc = [p for p in dentro if p["es_anomalia"]]
        sev = [p for p in dentro if p["severidad"] > 0]
        estado = "OK " if marc else "X  "
        if not marc:
            ok_evento = False
        print(f"  [{estado}] {e.nombre}: {len(marc)} de {len(dentro)} semanas marcadas, "
              f"{len(sev)} con severidad > 0")
        for p in dentro:
            marca = "***" if p["es_anomalia"] else "   "
            print(f"        {p['semana']} {marca} sev={p['severidad']:.2f} "
                  f"term={p['n_terminos_neg']}/{p['n_terminos']} n={p['n']} "
                  f"motivos={','.join(p['motivos']) or '-'}")

        # Antesala: las 8 semanas previas al evento. Acá es donde vive la señal
        # temprana (el 21/04/2026 hubo rumor de paro, petitorios y asamblea, seis
        # semanas antes del 03/06).
        previas = [
            por_semana[R._lunes(e.fecha_inicio) - timedelta(weeks=k)]
            for k in range(1, SEMANAS_ANTESALA + 1)
            if (R._lunes(e.fecha_inicio) - timedelta(weeks=k)) in por_semana
        ]
        avisadas = [p for p in previas if p["severidad"] > 0]
        print(f"        antesala (8 semanas previas): {len(avisadas)} con severidad > 0")
        for p in sorted(avisadas, key=lambda x: x["semana"]):
            print(f"          {p['semana']} sev={p['severidad']:.2f} "
                  f"term={p['n_terminos_neg']}/{p['n_terminos']} "
                  f"motivos={','.join(p['motivos'])}")

    # ---- Veredicto ----
    pct = 100 * len(marcadas) / len(serie)
    ok_ruido = pct <= MAX_PCT_SEMANAS_MARCADAS

    # Semanas marcadas que NINGÚN evento explica (ni su antesala ni su cierre).
    # No son necesariamente errores —pueden ser eventos que nadie cargó— pero son
    # las que hay que ir a mirar a mano antes de confiar en el detector.
    explicadas: set = set()
    for e in eventos:
        fin = e.fecha_fin or e.fecha_inicio
        ini_sem = R._lunes(e.fecha_inicio)
        fin_sem = R._lunes(fin)
        k = -SEMANAS_ANTESALA
        while ini_sem + timedelta(weeks=k) <= fin_sem + timedelta(weeks=SEMANAS_CIERRE):
            explicadas.add(ini_sem + timedelta(weeks=k))
            k += 1
    sin_explicar = [p for p in marcadas if p["semana"] not in explicadas]

    print("\n=== VEREDICTO ===")
    print(f"  [{'OK ' if ok_evento else 'X  '}] cada evento cargado tiene al menos "
          f"una semana marcada")
    print(f"  [{'OK ' if ok_ruido else 'X  '}] ruido sobre el histórico completo: "
          f"{len(marcadas)}/{len(serie)} semanas ({pct:.1f}%), "
          f"máximo tolerado {MAX_PCT_SEMANAS_MARCADAS}%")
    print(f"  [i  ] marcadas sin evento que las explique: {len(sin_explicar)} "
          f"-> {', '.join(str(p['semana']) for p in sin_explicar) or 'ninguna'}")
    print("        (revisar a mano: pueden ser eventos no cargados, no errores)")
    db.close()
    return 0 if (ok_evento and ok_ruido) else 1


if __name__ == "__main__":
    raise SystemExit(main())
