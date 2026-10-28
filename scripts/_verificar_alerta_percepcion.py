"""Verifica la ALERTA TEMPRANA del módulo contra los 4 años de historia real.

Qué demuestra: que los dos niveles implementados en `repository` encienden donde
deben — no en un caso de prueba, sino sobre los ocho episodios disruptivos que el
calendario registra, con los mismos datos que ve el tablero.

Por qué existe: la calibración de la alerta se hizo en un análisis aparte, y un
análisis que no se puede volver a correr contra el código real es una promesa, no
una medición. Esto cierra el círculo: usa `repository._detectar_anomalias_semanales`
tal cual está, no una reimplementación.

    SOLO LECTURA (`mode=ro`). No modifica ningún dato.

Uso:
    backend\\.venv\\Scripts\\python.exe scripts/_verificar_alerta_percepcion.py
    backend\\.venv\\Scripts\\python.exe scripts/_verificar_alerta_percepcion.py --db RUTA

Lee la base del worker (`PERCEPCION_DATABASE_URL` o `--db`). ⚠️ La operacional local
tiene datos SIMULADOS: apuntar siempre a la base real del worker.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

# La consola de Windows arranca en cp1252 y revienta con las flechas y los acentos
# del informe. Se fuerza UTF-8 en vez de escribir el reporte en ASCII: el que lee
# esto es una persona, y "→" no se reemplaza por "->" para complacer a una consola.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.services.percepcion import cripto, lexico, repository  # noqa: E402

RUTA_CALENDARIO = Path(__file__).resolve().parents[1] / "backend" / "app" / "data" / "percepcion_calendario_ucn.json"

# Ventana en la que un aviso cuenta como anticipación del episodio.
VENT_PREV_SEMANAS = 6
# Semanas DESPUÉS del fin que siguen contando como parte del episodio. Sin esto, la
# semana del 06-07-2026 —tres días después de terminar la paralización, con cuatro
# comentarios de léxico negativo— se contaba como falsa alarma. Es la cola del
# conflicto, no un error: la conversación no se apaga el día que se levanta el paro.
VENT_POST_SEMANAS = 2
# Un episodio solo es evaluable si su ventana previa tuvo con qué avisar. Sin esto
# entran los de 2022-2023 —años de 66 y 151 comentarios— y ninguna señal puede
# detectarlos por falta de datos, no por ser mala.
MIN_SEMANAS_UTILES = 2
MENCION = re.compile(r"@[\w.]+")
NO_PALABRA = re.compile(r"[^\w\sáéíóúüñÁÉÍÓÚÜÑ]", re.UNICODE)


def _sin_contenido(texto: str | None) -> bool:
    """Comentario sin nada evaluable: solo menciones, solo emojis, 1-2 palabras.

    Es el 54,9 % del corpus. Se excluye del índice y del %neg —donde solo aporta
    masa neutra— pero NO del conteo de léxico: «Paro?» tiene una palabra y es
    exactamente la señal que se quiere ver.
    """
    t = (texto or "").strip()
    if not t:
        return True
    t = NO_PALABRA.sub(" ", MENCION.sub(" ", t))
    return len([w for w in t.split() if len(w) > 1]) < 3


def _lunes(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _ruta_db(explicita: str | None) -> Path:
    if explicita:
        return Path(explicita)
    url = os.getenv("PERCEPCION_DATABASE_URL", "")
    if url.startswith("sqlite"):
        return Path(url.split("///")[-1])
    return Path.home() / "Documents" / "GitHub" / "Sentiment_Analisys_University" / "percepcion_real.db"


def serie_semanal(db: Path) -> list[dict]:
    """La serie que consume la detección, armada desde comentario ⋈ score."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    filas = con.execute("""
        SELECT substr(C.fecha_comentario, 1, 10) AS f, C.id, C.texto,
               S.prob_pos, S.prob_neg, S.sentimiento
          FROM percepcion_comentario C
          JOIN percepcion_score S ON S.comentario_id = C.id
         WHERE C.fecha_comentario IS NOT NULL
    """).fetchall()
    con.close()

    acc: dict[date, dict] = defaultdict(
        lambda: {"n": 0, "pos": 0.0, "neg": 0.0, "n_neg": 0, "lex": 0, "lex_neg": 0})
    for r in filas:
        w = _lunes(date.fromisoformat(r["f"]))
        a = acc[w]
        es_neg = (r["sentimiento"] or "").upper().startswith("NEG")
        texto = cripto.texto_de(r["id"], r["texto"])
        if lexico.detectar(texto):
            a["lex"] += 1
            if es_neg:
                a["lex_neg"] += 1
        if _sin_contenido(texto):
            continue
        a["n"] += 1
        a["pos"] += float(r["prob_pos"] or 0)
        a["neg"] += float(r["prob_neg"] or 0)
        a["n_neg"] += int(es_neg)

    if not acc:
        return []
    w, fin, serie = min(acc), max(acc), []
    while w <= fin:
        a = acc.get(w)
        n = a["n"] if a else 0
        serie.append({
            "semana": w, "n": n,
            "indice": (50 + 50 * (a["pos"] - a["neg"]) / n) if n else None,
            "pct_neg": (100 * a["n_neg"] / n) if n else None,
            "n_terminos": a["lex"] if a else 0,
            "n_terminos_neg": a["lex_neg"] if a else 0,
        })
        w += timedelta(weeks=1)
    return serie


def episodios() -> list[dict]:
    """Episodios disruptivos del calendario, fusionando los que son el mismo hecho.

    La toma del 08-06-2026 y el paro del 15-06 son un episodio, no dos alarmas:
    si se cuentan por separado, la misma señal detecta "dos" y el número miente.
    """
    cal = json.loads(RUTA_CALENDARIO.read_text(encoding="utf-8"))
    crudos = sorted(
        (date.fromisoformat(e["fecha_inicio"]),
         date.fromisoformat(e["fecha_fin"]) if e.get("fecha_fin") else date.fromisoformat(e["fecha_inicio"]),
         e["nombre"])
        for e in cal["eventos"] if e["tipo"] in ("paro", "toma", "emergencia")
    )
    out: list[dict] = []
    for a, b, nombre in crudos:
        if out and a <= out[-1]["fin"] + timedelta(days=7):
            out[-1]["fin"] = max(out[-1]["fin"], b)
            out[-1]["nombres"].append(nombre)
        else:
            out.append({"ini": a, "fin": b, "nombres": [nombre]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", help="ruta a percepcion_real.db")
    args = ap.parse_args()

    db = _ruta_db(args.db)
    if not db.exists():
        print(f"[ERROR] no existe la base: {db}")
        return 2
    print(f"Base: {db}")

    semanal = serie_semanal(db)
    if not semanal:
        print("[ERROR] la base no tiene comentarios con score.")
        return 2
    # Se pasa por el MISMO camino que el tablero: agrupar en unidades de detección
    # y recién ahí detectar. Saltearse la agrupación mediría otra cosa.
    serie = repository._agrupar_en_bloques(semanal)
    repository._detectar_anomalias_semanales(serie)
    por_semana = {p["semana"]: p for p in serie}
    unidad = repository.UNIDAD_DETECCION_SEMANAS
    print(f"Semanas: {len(semanal)}  ({semanal[0]['semana']} → {semanal[-1]['semana']})")
    print(f"Unidad de detección: {unidad} semana(s)  →  {len(serie)} bloques")
    print(f"Memoria del baseline: {repository.VENTANA_BASELINE_SEMANAS} semanas\n")

    eps = episodios()
    ancho = 46
    print("=" * 100)
    print("ANTICIPACIÓN POR EPISODIO")
    print("=" * 100)
    print(f"{'Episodio':<{ancho}}{'inicio':>12}{'nivel':>11}{'lead':>8}  semana del aviso")
    print("-" * 100)

    cubiertos = set()
    detecta = {repository.NIVEL_ALERTA: [], repository.NIVEL_ATENCION: []}
    evaluables = 0
    for ep in eps:
        w_ini = _lunes(ep["ini"])
        # Las semanas se traducen a BLOQUES: la serie ya no está indexada por lunes
        # de semana sino por lunes de quincena. Sin esta traducción se buscarían
        # claves que no existen y ninguna alarma se encontraría jamás.
        ventana = []
        for k in range(VENT_PREV_SEMANAS, -1, -1):
            b = repository._bloque_de(w_ini - timedelta(weeks=k))
            if b not in ventana:
                ventana.append(b)
        cubiertos.update(ventana)
        w = w_ini
        fin_cubierto = _lunes(ep["fin"]) + timedelta(weeks=VENT_POST_SEMANAS)
        while w <= fin_cubierto:
            cubiertos.add(repository._bloque_de(w))
            w += timedelta(weeks=1)

        utiles = sum(1 for x in ventana
                     if (por_semana.get(x, {}).get("n") or 0) >= repository.MIN_N_SEMANA)
        nombre = ep["nombres"][0][:ancho - 2]
        if utiles < MIN_SEMANAS_UTILES:
            print(f"{'~ ' + nombre:<{ancho}}{str(ep['ini']):>12}"
                  f"   no evaluable ({utiles} semana/s con muestra)")
            continue
        evaluables += 1

        avisos = [(x, por_semana[x]["nivel_alerta"]) for x in ventana
                  if por_semana.get(x, {}).get("nivel_alerta")]
        if not avisos:
            print(f"{nombre:<{ancho}}{str(ep['ini']):>12}{'—':>11}{'—':>8}  sin aviso")
            continue
        # El nivel que se reporta es el MÁS FUERTE que se encendió en la ventana.
        primero = min(avisos, key=lambda t: t[0])
        nivel = (repository.NIVEL_ALERTA
                 if any(n == repository.NIVEL_ALERTA for _, n in avisos)
                 else repository.NIVEL_ATENCION)
        lead = (ep["ini"] - primero[0]).days
        detecta[nivel].append(lead)
        print(f"{nombre:<{ancho}}{str(ep['ini']):>12}{nivel:>11}{str(lead) + ' d':>8}  {primero[0]}")

    print("-" * 100)
    encendidas = [p for p in serie if p["nivel_alerta"]]
    falsas = [p for p in encendidas if p["semana"] not in cubiertos]
    total_det = sum(len(v) for v in detecta.values())
    anios = (serie[-1]["semana"] - serie[0]["semana"]).days / 365.25
    print(f"  Episodios evaluables: {evaluables} de {len(eps)}")
    print(f"  Detectados: {total_det}"
          + (f"  ·  lead mediano {median([l for v in detecta.values() for l in v]):.0f} días"
             if total_det else ""))
    for niv, leads in detecta.items():
        if leads:
            print(f"     {niv:<9} {len(leads)} episodio/s  ·  lead {median(leads):.0f} d "
                  f"(rango {min(leads)}–{max(leads)})")
    print(f"  Semanas encendidas en total: {len(encendidas)}")
    print(f"  Falsas alarmas: {len(falsas)}  ({len(falsas)/anios:.1f} por año)"
          + (f"  ·  precisión {(len(encendidas)-len(falsas))/len(encendidas):.0%}"
             if encendidas else ""))

    if falsas:
        print("\n  Las falsas alarmas, para poder mirarlas:")
        for p in falsas:
            print(f"     {p['semana']}  [{p['nivel_alerta']:<8}] n={p['n']:>4} "
                  f"idx={(f'{p[chr(105)+chr(110)+chr(100)+chr(105)+chr(99)+chr(101)]:.1f}' if p['indice'] is not None else '—'):>5} "
                  f"%neg={(f'{p[chr(112)+chr(99)+chr(116)+chr(95)+chr(110)+chr(101)+chr(103)]:.0f}' if p['pct_neg'] is not None else '—'):>4} "
                  f"lex_neg={p['n_terminos_neg']}")

    # El índice NO debe encender ningún nivel. Es la regla más contraintuitiva del
    # módulo y la que más fácil se rompe sin querer al tocar la detección.
    por_indice = [p for p in encendidas
                  if "indice" in p["motivos"] and p["n_terminos_neg"] < repository.MIN_TERMINOS_ALARMA
                  and (p["z_pct_neg"] is None or p["z_pct_neg"] < repository.Z_ATENCION_PCT_NEG)]
    print(f"\n  Niveles encendidos SOLO por el índice: {len(por_indice)} "
          f"({'OK — el índice no alarma solo' if not por_indice else 'ERROR: revisar la detección'})")
    return 0 if not por_indice else 1


if __name__ == "__main__":
    raise SystemExit(main())
