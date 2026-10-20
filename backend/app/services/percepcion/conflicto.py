"""SEÑAL DE CONFLICTO — el volumen adverso, y cuánto se le puede creer.

QUÉ AGREGA AL ÍNDICE
--------------------
El índice es un promedio de tono. Dos cosas que un promedio no puede decir:

1. **El volumen.** «Hubo 104 comentarios adversos» es información distinta de «el
   índice bajó 4 puntos», y para gestión suele ser la que importa. Un promedio sobre
   muchos comentarios amables absorbe una decena de comentarios duros sin moverse.
2. **Cuánto depende de con qué se compare.** Toda variación se mide contra un período
   previo, y elegir ese período es una decisión que cambia el resultado. Este módulo
   la hace explícita en vez de esconderla.

LA LECCIÓN QUE ORIGINÓ ESTE DISEÑO
-----------------------------------
La primera versión comparaba contra UNA ventana previa y avisaba «divergencia» cuando
el índice subía mientras los adversos aumentaban. Sobre el episodio "Toma Campus
Angamos" daba una alerta contundente: adversos de 4,6 % a 12,9 %, casi el triple.

Era un artefacto. Barriendo la ventana previa de 7 a 90 días:

    7 días → 17,0 %   ·   14 días → 15,0 %   ·   21 días → 15,9 %
    28 días → 4,6 %   ·   90 días → 4,1 %

Entre 21 y 28 días el volumen previo salta de 69 a 241 comentarios: adentro cae
Fiestas Patrias 2024, una semana de mucho comentario amable. El «4,6 % previo» no era
el estado normal — era ese pico. Las tres semanas inmediatamente anteriores al paro ya
tenían 15-17 % de adversos, o sea que **el conflicto venía de antes** y durante la
toma ni siquiera subió.

Con una sola ventana, el mismo episodio se puede presentar como alarma o como calma.
Por eso acá se barren VARIAS y se informa si el signo aguanta:

    Paralización jun-jul 2026   +++++++   consistente
    Toma Campus Angamos         ---++++   cambia de signo → no se afirma nada

De los siete episodios medibles del corpus, cinco dan un signo estable y dos no. Los
dos que no son exactamente los que la primera versión usaba como evidencia.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select

from app.services.percepcion import repository
from app.services.percepcion.models import PercepcionHechoDiario as H

# Ventanas previas que se barren. Cubren de "la semana pasada" a "el último trimestre":
# si el signo del cambio aguanta en todas, no depende de dónde se puso el corte.
VENTANAS_PREVIAS = (7, 14, 21, 28, 56, 90)

# Cuánto tiene que moverse la proporción de adversos para contar como movimiento.
# Por debajo de esto entra en la oscilación normal de ventanas de decenas.
DELTA_NOTABLE = 2.0
# Mínimo por ventana para que su comparación signifique algo.
N_MIN = 20
# Comparaciones mínimas para hablar de CONSISTENCIA. Con una sola, "el signo aguanta
# en todas las ventanas" es cierto por vacuidad y suena mucho más firme de lo que es —
# que es justo el error que este módulo existe para no cometer.
MIN_COMPARACIONES = 3


def _ventana(db, desde: date, hasta: date, *, campus=None, facultad=None,
             departamento=None, tema=None) -> dict:
    filas = db.execute(
        select(func.sum(H.n_pos), func.sum(H.n_neu), func.sum(H.n_neg))
        .where(H.fecha >= desde, H.fecha <= hasta,
               *repository._condiciones(campus, facultad, departamento, tema))
    ).one()
    p, u, g = (int(x or 0) for x in filas)
    n = p + u + g
    if n == 0:
        return {"n": 0, "indice": None, "n_adversos": 0, "pct_adversos": None}
    return {
        "n": n,
        "indice": round(50.0 + 50.0 * (p - g) / n, 1),
        "n_adversos": g,
        "pct_adversos": round(100.0 * g / n, 1),
    }


def senal_de_conflicto(db, *, dias: int = 30, campus=None, facultad=None,
                       departamento=None, tema=None,
                       fecha_desde: date | None = None,
                       fecha_hasta: date | None = None) -> dict:
    """Volumen adverso del período y si su variación resiste el cambio de ventana."""
    r = repository._rango(db, dias, fecha_desde, fecha_hasta)
    base = {"hay_datos": False, "actual": None, "comparaciones": [],
            "tendencia": None, "consistente": False, "delta_tipico": None,
            "explicacion": None, "avisos": []}
    if r is None:
        return base
    desde, hasta = r
    kw = {"campus": campus, "facultad": facultad,
          "departamento": departamento, "tema": tema}

    actual = _ventana(db, desde, hasta, **kw)
    if actual["n"] == 0:
        base["avisos"].append("No hay comentarios en el período seleccionado.")
        return base

    comparaciones = []
    for dias_previos in VENTANAS_PREVIAS:
        prev = _ventana(db, desde - timedelta(days=dias_previos),
                        desde - timedelta(days=1), **kw)
        if prev["n"] < N_MIN or prev["pct_adversos"] is None:
            continue
        d_adv = round(actual["pct_adversos"] - prev["pct_adversos"], 1)
        comparaciones.append({
            "dias_previos": dias_previos,
            "n_previo": prev["n"],
            "pct_adversos_previo": prev["pct_adversos"],
            "indice_previo": prev["indice"],
            "delta_adversos": d_adv,
            "delta_indice": (round(actual["indice"] - prev["indice"], 1)
                             if actual["indice"] is not None and prev["indice"] is not None
                             else None),
            "signo": "sube" if d_adv > DELTA_NOTABLE
                     else ("baja" if d_adv < -DELTA_NOTABLE else "igual"),
        })

    tendencia, consistente, tipico = _consenso(comparaciones)
    return {
        "hay_datos": True,
        "periodo": {"desde": desde, "hasta": hasta},
        "actual": actual,
        "comparaciones": comparaciones,
        "tendencia": tendencia,
        "consistente": consistente,
        "delta_tipico": tipico,
        "explicacion": _explicar(actual, comparaciones, tendencia, consistente),
        "avisos": _avisos(actual, comparaciones, consistente),
    }


def _consenso(comparaciones: list[dict]) -> tuple[str | None, bool, float | None]:
    """Qué dicen todas las ventanas juntas, y si dicen lo mismo."""
    if not comparaciones:
        return None, False, None
    deltas = sorted(c["delta_adversos"] for c in comparaciones)
    # Mediana: menos sensible a una ventana atípica que el promedio.
    mediana = deltas[len(deltas) // 2]
    if len(comparaciones) < MIN_COMPARACIONES:
        # No alcanza para hablar de robustez. Se devuelve el dato sin el sello.
        return None, False, mediana
    signos = {c["signo"] for c in comparaciones}
    if len(signos) == 1:
        return signos.pop(), True, mediana
    return None, False, mediana


def _explicar(actual: dict, comparaciones: list[dict], tendencia: str | None,
              consistente: bool) -> str | None:
    if not comparaciones:
        return None
    if not consistente and len(comparaciones) < MIN_COMPARACIONES:
        return (
            f"Solo hay {len(comparaciones)} período previo con volumen suficiente "
            "para comparar. Con menos de "
            f"{MIN_COMPARACIONES} no se puede saber si el cambio es real o depende de "
            "dónde se puso el corte, así que no se afirma nada."
        )
    if not consistente:
        rango = (min(c["delta_adversos"] for c in comparaciones),
                 max(c["delta_adversos"] for c in comparaciones))
        return (
            f"Según con qué período se compare, los comentarios adversos van de "
            f"{rango[0]:+.1f} a {rango[1]:+.1f} puntos porcentuales: **el signo "
            "cambia**. No se puede afirmar que el conflicto haya subido ni bajado — "
            "lo que se estaría midiendo es dónde se puso el corte."
        )
    if tendencia == "sube":
        return (
            f"Los comentarios adversos subieron contra TODAS las ventanas de "
            f"comparación ({len(comparaciones)} probadas, de 7 a 90 días). "
            f"Hoy son {actual['n_adversos']} comentarios ({actual['pct_adversos']:.1f} %). "
            "El aumento no depende de con qué se compare."
        )
    if tendencia == "baja":
        return (
            "Los comentarios adversos bajaron contra todas las ventanas de "
            f"comparación. Hoy son {actual['n_adversos']} ({actual['pct_adversos']:.1f} %)."
        )
    return (
        f"Los comentarios adversos se mantienen: {actual['n_adversos']} "
        f"({actual['pct_adversos']:.1f} %), sin cambios apreciables contra ninguna "
        "ventana de comparación."
    )


def _avisos(actual: dict, comparaciones: list[dict], consistente: bool) -> list[str]:
    avisos: list[str] = []
    if not comparaciones:
        avisos.append(
            f"No hay ningún período previo con {N_MIN}+ comentarios contra el cual "
            "comparar. El volumen de abajo es el dato; la variación no se puede medir."
        )
    elif not consistente:
        avisos.append(
            "Este resultado es SENSIBLE a la ventana de comparación. Suele pasar "
            "cuando en el período previo cae una fecha de mucha actividad amable "
            "—unas Fiestas Patrias, una titulación— que corre el promedio."
        )
    if actual["n_adversos"] == 0 and actual["n"] >= N_MIN:
        avisos.append(
            "Cero comentarios adversos en el período. Conviene recordar que la "
            "ingesta no trae los que Instagram oculta por ofensivos."
        )
    avisos.append(
        "El volumen adverso se cuenta sobre lo ingestado, e Instagram oculta parte de "
        "lo ofensivo. El conflicto real es igual o mayor que el que se ve acá, nunca "
        "menor."
    )
    return avisos
