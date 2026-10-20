"""A · ¿Cómo va a estar la percepción la próxima semana? — LOS BASELINES.

Esta es la fase 1 del plan de simulación, y su propósito **no** es predecir bien: es
poner la vara que cualquier modelo posterior tiene que superar. Si una media móvil
acierta igual que 1.900 agentes generativos, la simulación no aporta nada y conviene
enterarse en días, no en meses.

Es la misma disciplina que en este módulo ya descartó embeddings (50,7 % contra 55,3 %
de un matcher de keywords) y al juez LLM para postura (52,3 % contra 90,0 % de una
regla de cuatro líneas). Los dos resultados negativos ahorraron semanas de trabajo.

EL TECHO: EL ERROR IRREDUCIBLE
------------------------------
El índice de una semana se calcula sobre 20-160 comentarios, así que trae su propio
ruido de muestreo (~4 puntos, medido). **Ningún modelo puede bajar de ahí**: no es
falta de ingenio, es que el dato observado ya viene con esa incertidumbre. Un modelo
con MAE 4,2 y otro con 3,9 no se distinguen; declarar ganador al segundo sería leer
ruido.

Por eso `evaluar_baselines` devuelve `error_irreducible` junto a los MAE, y marca
`indistinguible_del_techo` cuando el modelo ya llegó al piso.

CONTRA QUÉ SERIE SE VALIDA (resuelto 08-09-2026)
------------------------------------------------
Durante meses la vara corrió sobre el índice CANÓNICO —conteos crudos— mientras el
tablero mostraba el PONDERADO. Dos series distintas: sd 10,51 contra 9,08. Con eso,
«el modelo le ganó a la vara» y «el índice subió» hablaban de cosas distintas.

No era un descuido: `_ruido` era un estimador BINOMIAL sobre los conteos, y un índice
ponderado rompe ese modelo de ruido. Por eso la mejora del 15 % medida el 01-09-2026 no
se pudo integrar entonces. `_ruido_ponderado` generaliza el estimador a cualquier
esquema de pesos y se reduce EXACTAMENTE al binomial cuando los pesos valen 1 —hay un
test que lo exige—, así que cambiar de serie ya no cambia de instrumento.

Resuelto a favor del PONDERADO (`PONDERAR_TEMA_VALIDACION`), que gana o empata en todo
y además es el número que mira quien decide. El canónico sigue disponible con
`ponderar_tema=False`, y toda respuesta declara cuál usó.

BACKTESTING WALK-FORWARD, NO UN CORTE ÚNICO
-------------------------------------------
Hay ~33 semanas con volumen suficiente. Un corte 70/30 dejaría 10 puntos de test, que
no alcanzan para separar nada. Con walk-forward cada semana se predice usando SOLO lo
anterior, y se aprovechan todos los puntos posibles sin filtrar información del futuro.

⚠️ Partir al azar en vez de por tiempo dejaría semanas futuras en el entrenamiento y
produciría un acierto que no existe fuera del experimento. Acá el orden es sagrado.
"""
from __future__ import annotations

import math
import statistics as st
from datetime import date, timedelta

from sqlalchemy import func, select

from app.services.percepcion import ponderacion, repository
from app.services.percepcion.models import PercepcionEvento
from app.services.percepcion.models import PercepcionHechoDiario as H

# Volumen mínimo para que una semana entre a la evaluación. Por debajo, el índice
# oscila tanto por muestreo que evaluar un pronóstico contra él mide el azar.
N_MIN_SEMANA = 20

# SOBRE QUÉ SERIE SE MIDE LA VARA. Ver la sección del docstring del módulo.
#
# False = índice CANÓNICO (conteos crudos), que es como se leyó toda la historia del
# proyecto y lo único que se verifica contando.
# True  = índice del TABLERO (peso por tema + crédito recortado), que es el número que
# realmente mira quien decide.
#
# DEFAULT = True desde 09-2026. Medido sobre los 4 años reales, con el estimador de
# ruido generalizado (80 semanas, 74 evaluadas en las tres corridas):
#
#     serie                        sd     ruido   mejor MAE   TECHO
#     canónica                   10,51     4,30      8,62      4,32
#     PONDERADA (tablero)         9,08     2,86      7,31      4,45
#     ponderada simétrica         9,34     3,06      7,31      4,25
#
# La ponderada gana o empata en todo: 15 % menos de MAE, mejor relación ruido/sd
# (0,32 contra 0,41) y el mismo margen para que un modelo aporte. No pierde una sola
# semana. Y encima es el número que mira quien decide.
#
# ⚠️ ESTO CORRIGE UNA CONCLUSIÓN ANTERIOR. El 01-09-2026 se midió que ponderar
# ACHICABA el techo (4,61 → 3,22) y que un modelo lo tendría más difícil. Ese número
# salía de aplicar el estimador BINOMIAL a una serie ponderada, que es justo lo que
# `_ruido_ponderado` vino a arreglar: sobreestimaba el ruido (4,08 contra 2,86). Con
# el estimador correcto el techo no se achica. La conclusión vieja no era un error de
# medición sino del instrumento de medición.
PONDERAR_TEMA_VALIDACION = True
# Semanas de historia antes de empezar a evaluar. Con menos, los baselines que usan
# promedios no tienen de dónde promediar.
MIN_HISTORIA = 6
VENTANA_MEDIA_MOVIL = 4

# Menú de λ del suavizado exponencial. DISCRETO y corto: optimizar un λ continuo sobre
# 20-70 semanas encontraría el valor que memoriza el historial en vez de la dinámica.
# El λ efectivo que elige la serie real ronda 0,2-0,3, coherente con la reversión
# medida (φ≈0,52, vida media ~1 semana).
LAMBDAS_SUAVIZADO = (0.2, 0.3, 0.4, 0.5, 0.7)

# Categorías de semana para el baseline de calendario. Deliberadamente pocas: con ~33
# puntos, un modelo con muchos parámetros memoriza la serie en vez de aprenderla.
CAT_DISRUPTIVA = "disruptiva"   # paro, toma, emergencia
CAT_RECESO = "receso"           # receso, vacaciones, fiestas patrias
CAT_EXAMENES = "examenes"
CAT_NORMAL = "normal"

_TIPOS_A_CATEGORIA = {
    "paro": CAT_DISRUPTIVA, "toma": CAT_DISRUPTIVA, "emergencia": CAT_DISRUPTIVA,
    "receso": CAT_RECESO, "fiestas_patrias": CAT_RECESO,
    "examenes": CAT_EXAMENES,
}


def serie_semanal(db, *, n_min: int = N_MIN_SEMANA,
                  ponderar_tema: bool = PONDERAR_TEMA_VALIDACION) -> list[dict]:
    """Índice por semana, con su volumen y su ruido de muestreo.

    Sin ponderar por likes ni por recencia: un pronóstico se verifica contra un número
    reproducible, no contra uno que depende de los sliders del tablero.

    `ponderar_tema` decide CONTRA QUÉ SERIE se valida (ver el docstring del módulo):
    con True, la del tablero —peso por tema y crédito recortado por atribuibilidad—;
    con False, la canónica de conteos crudos. El agrupamiento baja a (semana, tema)
    porque el peso tiene que aplicarse antes de sumar; el grano de
    `percepcion_hecho_diario` ya incluye `tema`, así que es exacto y sin migración.
    """
    filas = db.execute(
        select(H.fecha, H.tema, func.sum(H.n_pos), func.sum(H.n_neu), func.sum(H.n_neg))
        .group_by(H.fecha, H.tema)
    ).all()

    # semana -> tema -> [npos, nneu, nneg]
    acc: dict[date, dict[str | None, list[int]]] = {}
    for fecha, tema, npos, nneu, nneg in filas:
        f = repository._a_fecha(fecha)
        if f is None:
            continue
        por_tema = acc.setdefault(repository._lunes(f), {})
        a = por_tema.setdefault(tema, [0, 0, 0])
        a[0] += int(npos or 0); a[1] += int(nneu or 0); a[2] += int(nneg or 0)

    serie = []
    for lunes, por_tema in sorted(acc.items()):
        n = sum(sum(v) for v in por_tema.values())
        if n < n_min:
            continue
        grupos, num = [], 0.0
        for tema, (npos, nneu, nneg) in por_tema.items():
            wc = ponderacion.peso_credito(tema) if ponderar_tema else 1.0
            wd = ponderacion.peso_dano(tema) if ponderar_tema else 1.0
            num += wc * npos - wd * nneg
            grupos.append((npos, nneu, nneg, wc, wd))
        serie.append({
            "semana": lunes,
            "n": n,                       # comentarios, nunca pesos: la muestra no se encoge
            "indice": 50.0 + 50.0 * num / n,
            "ruido": _ruido_ponderado(grupos, n),
        })
    return serie


def _ruido_ponderado(grupos: list[tuple[int, int, int, float, float]], n: int) -> float:
    """Cuánto oscila el índice de esta semana solo por muestreo, con pesos cualesquiera.

    `grupos` son tuplas (npos, nneu, nneg, peso_credito, peso_daño), una por tema.

    Cada comentario aporta `Z = +wc` si es POS, `−wd` si es NEG y 0 si es NEU, y el
    índice es `50 + 50·(1/n)·Σ Z`. Con los comentarios independientes y el peso fijo
    dentro de cada tema:

        Var(Z | t) = wc²·p + wd²·q − (wc·p − wd·q)²
        ruido      = 50·√( Σ_t n_t · Var(Z|t) ) / n

    Con wc = wd = 1 y un solo grupo esto se reduce EXACTAMENTE a la fórmula binomial
    anterior —`[p(1−p) + q(1−q) + 2pq]/n`—, y hay un test que lo exige. Esa
    equivalencia es lo que permite cambiar de serie sin cambiar de vara.

    Proporciones suavizadas (Laplace) DENTRO de cada tema, por el mismo motivo que en
    `volatilidad.py`: con `p̂ = x/n` un tema homogéneo daría varianza cero, que es
    falso. Con temas de pocos comentarios el suavizado infla el ruido, y ese es el
    lado correcto para errar: un ruido sobreestimado hace la vara más exigente.
    """
    if n < 1:
        return 0.0
    total = 0.0
    for npos, nneu, nneg, wc, wd in grupos:
        n_t = npos + nneu + nneg
        if n_t < 1:
            continue
        den = n_t + 3
        p, q = (npos + 1) / den, (nneg + 1) / den
        var_z = wc * wc * p + wd * wd * q - (wc * p - wd * q) ** 2
        total += n_t * max(var_z, 0.0)
    return 50.0 * math.sqrt(total) / n


# --------------------------------------------------------------------------- #
# Categorías de calendario
# --------------------------------------------------------------------------- #
def categorias_por_semana(db, semanas: list[date]) -> dict[date, str]:
    """Qué tipo de semana fue cada una, según el calendario cargado.

    Prioridad DISRUPTIVA > EXAMENES > RECESO: si una semana tiene un paro y además
    cae en receso, lo que la define es el paro. Sin un orden explícito, el resultado
    dependería de cuál evento devolvió primero la base.
    """
    if not semanas:
        return {}
    eventos = db.execute(
        select(PercepcionEvento.tipo, PercepcionEvento.fecha_inicio,
               PercepcionEvento.fecha_fin)
    ).all()

    orden = {CAT_DISRUPTIVA: 3, CAT_EXAMENES: 2, CAT_RECESO: 1, CAT_NORMAL: 0}
    out = {s: CAT_NORMAL for s in semanas}
    for tipo, ini, fin in eventos:
        cat = _TIPOS_A_CATEGORIA.get(tipo)
        if cat is None:
            continue
        ini = repository._a_fecha(ini)
        fin = repository._a_fecha(fin) or ini
        if ini is None:
            continue
        for s in semanas:
            # ¿Se solapan la semana [s, s+6] y el evento [ini, fin]?
            if ini <= s + timedelta(days=6) and fin >= s:
                if orden[cat] > orden[out[s]]:
                    out[s] = cat
    return out


# --------------------------------------------------------------------------- #
# Los baselines. Cada uno recibe la historia y devuelve la predicción, o None.
# --------------------------------------------------------------------------- #
def _persistencia(hist: list[dict], _cat_hist, _cat_obj) -> float | None:
    """«La semana que viene será igual a esta». El más difícil de superar."""
    return hist[-1]["indice"] if hist else None


def _media_movil(hist: list[dict], _cat_hist, _cat_obj) -> float | None:
    ventana = hist[-VENTANA_MEDIA_MOVIL:]
    return st.mean(x["indice"] for x in ventana) if ventana else None


def _estacional(hist: list[dict], _cat_hist, cat_obj) -> float | None:
    """El mismo período del año anterior. Cae a la media si no hay dato.

    El fallback no es cosmético: con 33 semanas repartidas en 4 años, la mayoría no
    tiene equivalente exacto. Un baseline que devuelve None en esos casos no se puede
    comparar con los otros, porque estaría evaluado sobre otro conjunto.
    """
    objetivo = cat_obj["semana"]
    hace_un_anio = objetivo - timedelta(days=364)  # 52 semanas exactas
    cercanas = [x for x in hist if abs((x["semana"] - hace_un_anio).days) <= 14]
    if cercanas:
        return st.mean(x["indice"] for x in cercanas)
    return st.mean(x["indice"] for x in hist) if hist else None


def _calendario(hist: list[dict], cat_hist: dict[date, str], cat_obj) -> float | None:
    """Media histórica de las semanas de la MISMA categoría de calendario.

    Modelo de cuatro parámetros como mucho. Con ~33 puntos, cualquier cosa más
    grande memoriza la serie. Si la categoría de la semana objetivo nunca se vio
    antes, cae a la media general — decir "no sé" no es una opción cuando los otros
    baselines sí responden: el conjunto de evaluación tiene que ser el mismo.
    """
    if not hist:
        return None
    cat = cat_hist.get(cat_obj["semana"], CAT_NORMAL)
    iguales = [x["indice"] for x in hist if cat_hist.get(x["semana"]) == cat]
    return st.mean(iguales) if iguales else st.mean(x["indice"] for x in hist)


def _suavizado(hist: list[dict], _cat_hist, _cat_obj) -> float | None:
    """Suavizado exponencial: un promedio donde lo reciente pesa más, `λ` calibrado.

    Es el resultado POSITIVO de la fase 2, y sale al revés de lo que el plan esperaba:
    lo que mejora el pronóstico no es más modelo sino MENOS. Un parámetro, calibrado
    sobre el pasado, le saca 0,40 puntos de MAE a la media móvil (6,91 contra 7,31),
    mientras que el modelo poblacional de cuatro y cinco parámetros da 7,54 y 7,50.

    Tiene sentido con lo que se midió de la serie: hay reversión a la media con φ≈0,52
    y vida media de ~1 semana, así que pesar las semanas por antigüedad es exactamente
    la forma correcta de promediar. La media móvil, que le da el mismo peso a la semana
    pasada y a la de hace un mes, está tirando información.

    ⚠️ λ SE ELIGE MIRANDO SOLO EL PASADO, y hay un test que lo exige. Fijarlo por el λ
    que mejor anduvo sobre toda la serie daría 6,80 —un número que no existe fuera del
    experimento— porque esa elección ya vio los datos contra los que se evalúa.

    El menú de λ es DISCRETO y corto a propósito: optimizar un λ continuo sobre 20-70
    semanas encontraría el valor que memoriza el historial.
    """
    if not hist:
        return None
    valores = [x["indice"] for x in hist]
    if len(valores) < 5:                       # todavía no hay con qué calibrar
        return st.mean(valores)

    def ewma(vals: list[float], lam: float) -> float:
        s = vals[0]
        for v in vals[1:]:
            s = lam * v + (1 - lam) * s
        return s

    mejor, mejor_mae = LAMBDAS_SUAVIZADO[0], float("inf")
    for lam in LAMBDAS_SUAVIZADO:
        # Backtest interno del propio baseline, solo sobre el historial recibido.
        errs = [abs(ewma(valores[:j], lam) - valores[j]) for j in range(3, len(valores))]
        if errs and st.mean(errs) < mejor_mae:
            mejor, mejor_mae = lam, st.mean(errs)
    return ewma(valores, mejor)


BASELINES = (
    ("persistencia", "La semana que viene será igual a esta", _persistencia),
    ("media_movil", f"Promedio de las últimas {VENTANA_MEDIA_MOVIL} semanas", _media_movil),
    ("suavizado", "Promedio donde lo reciente pesa más", _suavizado),
    ("estacional", "El mismo período del año anterior", _estacional),
    ("calendario", "Promedio histórico de semanas del mismo tipo", _calendario),
)


# --------------------------------------------------------------------------- #
# Evaluación
# --------------------------------------------------------------------------- #
def evaluar_baselines(db, *, n_min: int = N_MIN_SEMANA,
                      min_historia: int = MIN_HISTORIA,
                      ponderar_tema: bool = PONDERAR_TEMA_VALIDACION) -> dict:
    """Backtesting walk-forward de los cuatro baselines.

    Para cada semana evaluable se predice usando SOLO las anteriores. El resultado no
    es un ranking de campeones: es la vara. Lo que importa después es si algún modelo
    la supera por más que el error irreducible.

    `ponderar_tema` elige la serie contra la que se valida, y el resultado lo DECLARA
    en `serie`. La vara, el techo y el desvío salen todos de esa misma serie: comparar
    el MAE de una contra el ruido de la otra no significaría nada.
    """
    serie = serie_semanal(db, n_min=n_min, ponderar_tema=ponderar_tema)
    base = {
        "semanas_con_datos": len(serie),
        "evaluadas": 0,
        "n_min_semana": n_min,
        "serie": "ponderada" if ponderar_tema else "canonica",
        "error_irreducible": None,
        "desvio_serie": None,
        "modelos": [],
        "avisos": [],
    }
    if len(serie) <= min_historia:
        base["avisos"].append(
            f"Solo hay {len(serie)} semanas con {n_min}+ comentarios; se necesitan más "
            f"de {min_historia} para poder evaluar un pronóstico."
        )
        return base

    semanas = [x["semana"] for x in serie]
    cats = categorias_por_semana(db, semanas)

    errores: dict[str, list[float]] = {n: [] for n, _, _ in BASELINES}
    for i in range(min_historia, len(serie)):
        hist, objetivo = serie[:i], serie[i]
        for nombre, _desc, fn in BASELINES:
            pred = fn(hist, cats, objetivo)
            if pred is not None:
                errores[nombre].append(abs(pred - objetivo["indice"]))

    evaluadas = len(serie) - min_historia
    # El piso: promedio del ruido de muestreo de las semanas evaluadas.
    irreducible = st.mean(x["ruido"] for x in serie[min_historia:])
    # La referencia de "no hacer nada": el desvío de la propia serie. Un modelo con
    # MAE mayor que esto es peor que decir siempre el promedio histórico.
    desvio = st.pstdev([x["indice"] for x in serie])

    modelos = []
    for nombre, desc, _fn in BASELINES:
        errs = errores[nombre]
        if not errs:
            continue
        mae = st.mean(errs)
        modelos.append({
            "nombre": nombre,
            "descripcion": desc,
            "mae": round(mae, 2),
            "rmse": round(math.sqrt(st.mean(e * e for e in errs)), 2),
            "n_predicciones": len(errs),
            # El modelo ya toca el piso de ruido: no se le puede pedir más.
            "indistinguible_del_techo": mae <= irreducible,
            "peor_que_no_hacer_nada": mae > desvio,
        })
    modelos.sort(key=lambda m: m["mae"])

    base.update({
        "evaluadas": evaluadas,
        "error_irreducible": round(irreducible, 2),
        "desvio_serie": round(desvio, 2),
        "modelos": modelos,
        "avisos": _avisos(modelos, evaluadas, irreducible),
    })
    return base


def _avisos(modelos: list[dict], evaluadas: int, irreducible: float) -> list[str]:
    """Las advertencias que impiden leer este cuadro como un campeonato."""
    avisos = []
    if evaluadas < 20:
        avisos.append(
            f"Solo {evaluadas} semanas evaluadas. Con esta cantidad, diferencias de "
            "menos de un punto de MAE no significan nada."
        )
    if modelos:
        mejor = modelos[0]
        if mejor["indistinguible_del_techo"]:
            avisos.append(
                f"«{mejor['nombre']}» ya llegó al error irreducible ({irreducible:.1f} "
                "puntos de ruido de muestreo). Ningún modelo puede bajar de ahí: la "
                "incertidumbre está en el dato observado, no en el pronóstico."
            )
        if len(modelos) > 1:
            brecha = modelos[1]["mae"] - mejor["mae"]
            if brecha < 1.0:
                avisos.append(
                    f"«{mejor['nombre']}» y «{modelos[1]['nombre']}» difieren en "
                    f"{brecha:.2f} puntos de MAE: están empatados. No hay un ganador."
                )
    avisos.append(
        "Estos son los baselines, no un modelo. La regla del proyecto es que una "
        "simulación que no le gane a todos ellos —por más que el error irreducible— "
        "no se integra."
    )
    return avisos
