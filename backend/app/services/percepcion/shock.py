"""C · Si hay un paro, ¿cuánto cae la percepción y cuánto tarda en recuperarse?

Tercera pregunta del plan de simulación. Y la que menos margen tiene para inventar,
porque la respuesta honesta depende de cuántos episodios se pueden medir — no de qué
tan bueno sea el método.

LO QUE ESTE MÓDULO NO HACE: PROMEDIAR
--------------------------------------
La forma natural de contestar sería «un paro cuesta X puntos y se recupera en Y
semanas». No se puede, y conviene decir por qué antes que después.

Sobre el corpus hay 13 episodios disruptivos cargados, pero la ingesta solo tiene
volumen desde fines de 2024: los paros de 2022 y 2023 no tienen comentarios alrededor
con los cuales medir nada. Promediar dos episodios medibles con once vacíos produce un
número con aspecto de resultado y con contenido de ruido.

Por eso la salida son **casos**, cada uno con su propia evidencia declarada. Cuando
haya suficientes episodios medibles, agregar un promedio es un cambio menor; hacerlo
antes sería el error.

CÓMO SE MIDE
------------
Cinco ventanas alrededor del episodio, todas en el ámbito donde ocurrió (un paro en
Antofagasta no se mide contra el índice nacional):

    -8..-5   -4..-1   DURANTE   +1..+4   +5..+8   (semanas)

* **Caída** = índice durante − índice de las 4 semanas previas.
* **Recuperación** = primera semana posterior cuyo índice vuelve al nivel previo. Si
  no vuelve dentro de la ventana observada, se informa *no recuperado*, que es un dato
  y no una falta de dato.

⚠️ Las fechas ESTIMADAS no sirven para medir duración ni velocidad de recuperación:
si el término del paro es aproximado, «cuántas semanas tardó» mide la suposición. El
módulo las marca y `solo_confirmados` las excluye.
"""
from __future__ import annotations

import math
import statistics as st
from types import SimpleNamespace
from datetime import date, timedelta

from sqlalchemy import func, select

from app.services.percepcion import calendario, repository
from app.services.percepcion.models import PercepcionEvento
from app.services.percepcion.models import PercepcionHechoDiario as H

# Semanas de cada ventana lateral.
SEMANAS_LATERAL = 4
# Cuántas ventanas laterales se miran a cada lado.
VENTANAS_LADO = 2

# DENSIDAD mínima, no total. Un umbral por ventana ("20 comentarios en 4 semanas")
# deja pasar 0,7 comentarios por día y llama medible a una ventana casi vacía: fue
# exactamente lo que hizo que octubre 2024 apareciera con un índice previo de 48,2
# construido sobre 28 comentarios en 28 días, en un tramo donde toda la serie de
# Antofagasta tenía UNA semana con volumen. Exigir densidad lo descarta solo.
N_MIN_POR_SEMANA = 15


def _n_minimo(dias: int) -> int:
    """Volumen mínimo de una ventana según su largo, a razón de `N_MIN_POR_SEMANA`."""
    return max(N_MIN_POR_SEMANA, round(N_MIN_POR_SEMANA * max(dias, 1) / 7))


# Semanas consecutivas por encima del nivel previo para declarar RECUPERACIÓN.
#
# Con una sola alcanzaba, y eso confundía oscilación con recuperación: tras el paro de
# junio 2026 la serie hace 51,2 → 87,5 → 85,0 → 64,7 → 83,2 → 68,2, y el criterio de
# una semana declaraba «recuperado en 2» sobre un pico que se vuelve a caer dos veces.
# Volver y quedarse son cosas distintas, y solo la segunda es una recuperación.
SEMANAS_SOSTEN = 3

EVIDENCIA_SUFICIENTE = "suficiente"   # previo y durante medibles
EVIDENCIA_PARCIAL = "parcial"         # uno de los dos
EVIDENCIA_NULA = "insuficiente"       # ninguno


def _indice_ventana_ponderado(db, desde: date, hasta: date,
                              ambito: str | None) -> float | None:
    """Índice de la ventana con el peso por TEMA, acotado al mismo ámbito.

    Va por `percepcion_hecho_diario` igual que `_indice_ventana` —y no por los
    comentarios— para que las dos columnas de la tabla sean comparables: mismo
    universo, mismo recorte por sede, y la única diferencia es el peso. Calcularlo por
    otra vía daba dos números que no se podían restar entre sí.
    """
    from app.services.percepcion import ponderacion

    q = select(H.tema, func.sum(H.n_pos), func.sum(H.n_neu), func.sum(H.n_neg)).where(
        H.fecha >= desde, H.fecha <= hasta
    )
    if ambito and ambito != "global":
        q = q.where(H.campus == ambito)
    credito = dano = 0.0
    n = 0
    for tema, p, u, g in db.execute(q.group_by(H.tema)):
        p, u, g = int(p or 0), int(u or 0), int(g or 0)
        # Crédito y daño con pesos distintos, igual que el índice del tablero: si esta
        # columna usara el peso simétrico, las dos de la tabla dejarían de ser restables
        # entre sí, que es justo lo que esta función existe para evitar.
        credito += ponderacion.peso_credito(tema) * p
        dano += ponderacion.peso_dano(tema) * g
        n += p + u + g          # el denominador NO se pondera
    return None if not n else 50.0 + 50.0 * (credito - dano) / n


def _indice_ventana(db, desde: date, hasta: date, ambito: str | None) -> tuple[int, float | None]:
    """(n, índice) del período, acotado al ámbito del episodio.

    Un paro de Antofagasta se mide contra Antofagasta. Medirlo contra el índice global
    diluiría el efecto con las sedes que no lo vivieron, y el resultado sería más chico
    que el real sin que nada lo indique.
    """
    q = select(func.sum(H.n_pos), func.sum(H.n_neu), func.sum(H.n_neg)).where(
        H.fecha >= desde, H.fecha <= hasta
    )
    if ambito and ambito != "global":
        q = q.where(H.campus == ambito)
    p, u, g = db.execute(q).one()
    p, u, g = int(p or 0), int(u or 0), int(g or 0)
    n = p + u + g
    if n == 0:
        return 0, None
    return n, 50.0 + 50.0 * (p - g) / n


def _serie_posterior(db, desde: date, semanas: int, ambito: str | None) -> list[dict]:
    """Índice semana a semana después del episodio, para medir la recuperación."""
    out = []
    for i in range(semanas):
        ini = desde + timedelta(days=7 * i)
        n, idx = _indice_ventana(db, ini, ini + timedelta(days=6), ambito)
        out.append({"semana": ini, "n": n, "indice": idx})
    return out


# Mínimo de comentarios para que un tipo de cuenta cuente como estrato. Por debajo se
# excluye y los pesos se renormalizan: un estrato de n=1 al 0 % o al 100 % mueve el
# índice varios puntos sin ninguna evidencia detrás.
N_MIN_ESTRATO = 5


def filas_para_composicion(db) -> list:
    """Un registro por comentario scoreado, con el TIPO de cuenta que lo recibió.

    Baja al nivel de comentario a propósito: `percepcion_hecho_diario` tiene fecha,
    origen, campus, facultad, departamento y tema, pero NO el tipo de cuenta — y el
    tipo es justo la dimensión cuya mezcla se mueve entre ventanas. Con ~8.000
    comentarios el costo es despreciable y no hace falta tocar el esquema que escribe
    el worker.
    """
    from app.services.percepcion.models import (
        PercepcionComentario as _M,
        PercepcionCuenta as _C,
        PercepcionPublicacion as _P,
        PercepcionScore as _S,
    )

    filas = db.execute(
        select(_C.tipo, _C.handle, _M.fecha_comentario, _S.sentimiento, _M.tema)
        .join(_P, _P.cuenta_id == _C.id)
        .join(_M, _M.publicacion_id == _P.id)
        .join(_S, _S.comentario_id == _M.id)
    ).all()
    # Un solo recorrido con TODO lo que necesitan las cuatro lecturas: `tipo` para la
    # estandarizacion por composicion, `handle` para el indice critico y `tema` para
    # el ponderado. Repetir la consulta por indicador seria tres viajes a la base
    # para los mismos ~8.000 registros.
    return [
        SimpleNamespace(
            tipo=tipo or "(sin tipo)",
            handle=handle,
            fecha=fc.date() if hasattr(fc, "date") else repository._a_fecha(fc),
            sentimiento=sent,
            tema=tema,
        )
        for tipo, handle, fc, sent, tema in filas
    ]


def pesos_por_tipo(filas) -> dict[str, float]:
    """Participación de cada tipo de cuenta en TODO el corpus.

    Es el estándar contra el que se comparan las ventanas. Fijo a propósito: si los
    pesos se recalcularan por ventana, la corrección no corregiría nada.
    """
    conteo: dict[str, int] = {}
    for f in filas:
        conteo[f.tipo] = conteo.get(f.tipo, 0) + 1
    total = sum(conteo.values())
    return {t: n / total for t, n in conteo.items()} if total else {}


def _conteos(filas, desde: date, hasta: date) -> dict[str, list[int]]:
    acc: dict[str, list[int]] = {}
    for f in filas:
        if f.fecha is None or not (desde <= f.fecha <= hasta):
            continue
        celda = acc.setdefault(f.tipo, [0, 0, 0])
        celda[0 if f.sentimiento == "POS" else 2 if f.sentimiento == "NEG" else 1] += 1
    return acc


def _indice(pos: int, neu: int, neg: int) -> float | None:
    n = pos + neu + neg
    return None if n == 0 else 50.0 + 50.0 * (pos - neg) / n


def indice_crudo(filas, desde: date, hasta: date) -> float | None:
    """El índice tal como se venía calculando: todos los comentarios juntos."""
    p = u = g = 0
    for pos, neu, neg in _conteos(filas, desde, hasta).values():
        p += pos; u += neu; g += neg
    return _indice(p, u, g)


def indice_estandarizado(filas, desde: date, hasta: date,
                         pesos: dict[str, float],
                         *, n_min: int = N_MIN_ESTRATO) -> float | None:
    """Índice de la ventana con la MEZCLA DE CUENTAS FIJA.

    El índice crudo de una ventana mezcla todas las cuentas, y entre la ventana previa
    y la del conflicto esa mezcla cambia muchísimo. Medido sobre «Paralización general
    junio-julio»:

        centros de alumnos (índice ~72)   n=114  ->  n=4
        feucn              (índice ~28)   n=26   ->  n=102

    feucn no se pone más negativa durante el paro —está en 28-32 antes, durante y
    después—: lo que cambia es su PESO. El índice agregado baja aunque nadie haya
    cambiado de opinión. Con la mezcla fija, la caída de ese episodio pasa de −15,6 a
    −4,7: dos tercios eran composición.

    Se estandariza por TIPO de cuenta y no por tema porque se probaron los dos: por
    tema la caída queda casi igual (−13,7), por tipo se corrige de verdad. Lo que se
    mueve entre ventanas es QUIÉN comenta, no de qué se habla.
    """
    acc = _conteos(filas, desde, hasta)
    num = den = 0.0
    for tipo, (pos, neu, neg) in acc.items():
        if pos + neu + neg < n_min:
            continue
        idx = _indice(pos, neu, neg)
        peso = pesos.get(tipo, 0.0)
        if idx is None or peso <= 0:
            continue
        num += peso * idx
        den += peso
    return num / den if den else None


def perfil_episodio(db, episodio: dict, *, semanas_recuperacion: int = 12,
                    filas_comp=None, pesos_comp=None) -> dict:
    """Las cinco ventanas de un episodio, su caída y su recuperación.

    `episodio` es una fila de `calendario.episodios_disruptivos`.
    """
    ini = episodio["desde"]
    fin = episodio["hasta"] or ini
    ambito = episodio.get("ambito")

    ventanas = []
    for k in range(VENTANAS_LADO, 0, -1):
        d0 = ini - timedelta(days=7 * SEMANAS_LATERAL * k)
        d1 = ini - timedelta(days=7 * SEMANAS_LATERAL * (k - 1) + 1)
        n, idx = _indice_ventana(db, d0, d1, ambito)
        ventanas.append({"etiqueta": f"-{SEMANAS_LATERAL * k} a -{SEMANAS_LATERAL * (k - 1) + 1} sem",
                         "desde": d0, "hasta": d1, "n": n, "indice": idx})

    n_dur, idx_dur = _indice_ventana(db, ini, fin, ambito)
    ventanas.append({"etiqueta": "durante", "desde": ini, "hasta": fin,
                     "n": n_dur, "indice": idx_dur})

    for k in range(VENTANAS_LADO):
        d0 = fin + timedelta(days=7 * SEMANAS_LATERAL * k + 1)
        d1 = fin + timedelta(days=7 * SEMANAS_LATERAL * (k + 1))
        n, idx = _indice_ventana(db, d0, d1, ambito)
        ventanas.append({"etiqueta": f"+{SEMANAS_LATERAL * k + 1} a +{SEMANAS_LATERAL * (k + 1)} sem",
                         "desde": d0, "hasta": d1, "n": n, "indice": idx})

    # La ventana previa inmediata es la referencia: es el estado del que se partió.
    previa = ventanas[VENTANAS_LADO - 1]
    dias_previa = (previa["hasta"] - previa["desde"]).days + 1
    idx_prev = previa["indice"] if previa["n"] >= _n_minimo(dias_previa) else None
    dias_dur = (fin - ini).days + 1
    idx_durante = idx_dur if n_dur >= _n_minimo(dias_dur) else None

    if idx_prev is not None and idx_durante is not None:
        evidencia = EVIDENCIA_SUFICIENTE
    elif idx_prev is not None or idx_durante is not None:
        evidencia = EVIDENCIA_PARCIAL
    else:
        evidencia = EVIDENCIA_NULA

    caida = (round(idx_durante - idx_prev, 1)
             if idx_prev is not None and idx_durante is not None else None)

    # La MISMA comparación con la mezcla de cuentas fija. Se informa al lado de la
    # cruda, no en su lugar: la cruda es lo que efectivamente se leyó en el tablero
    # esas semanas, y la estandarizada dice cuánto de eso fue opinión y cuánto fue
    # que cambió quién comentaba. Ver `indice_estandarizado`.
    # Las tres lecturas de la ventana del conflicto, para la tabla de episodios:
    # el indice PONDERADO por tema (el principal), el CRITICO (solo canales donde la
    # critica existe) y el VOLUMEN adverso crudo. El volumen es el que delata los
    # episodios flacos: "Toma pabellon +19,0" con 2 comentarios adversos de 47 no
    # midio el conflicto, midio posteo normal.
    idx_pond = _indice_ventana_ponderado(db, ini, fin, ambito)
    idx_crit = None
    n_adversos = pct_adversos = None
    if filas_comp is not None:
        try:
            from app.services.percepcion import critica

            idx_crit = critica.indice_critico(filas_comp, ini, fin)
            vol = critica.volumen_adverso(filas_comp, ini, fin)
            n_adversos, pct_adversos = vol["n_adversos"], vol["proporcion"]
        except Exception:
            # Un indicador de apoyo que falla no puede dejar sin perfil al episodio.
            pass

    caida_est = est_prev = est_dur = None
    if filas_comp is not None and pesos_comp:
        est_prev = indice_estandarizado(
            filas_comp, previa["desde"], previa["hasta"], pesos_comp)
        est_dur = indice_estandarizado(filas_comp, ini, fin, pesos_comp)
        if est_prev is not None and est_dur is not None and caida is not None:
            caida_est = round(est_dur - est_prev, 1)

    return {
        **episodio,
        "ventanas": ventanas,
        "indice_previo": round(idx_prev, 1) if idx_prev is not None else None,
        "indice_durante": round(idx_durante, 1) if idx_durante is not None else None,
        "caida": caida,
        "indice_previo_estandarizado": round(est_prev, 1) if est_prev is not None else None,
        "indice_durante_estandarizado": round(est_dur, 1) if est_dur is not None else None,
        "caida_estandarizada": caida_est,
        "indice_ponderado": round(idx_pond, 1) if idx_pond is not None else None,
        "indice_critico": round(idx_crit, 1) if idx_crit is not None else None,
        "n_adversos": n_adversos,
        "pct_adversos": pct_adversos,
        "composicion": (None if caida is None or caida_est is None
                        else round(caida - caida_est, 1)),
        "evidencia": evidencia,
        **_recuperacion(db, fin, idx_prev, ambito, semanas_recuperacion),
    }


def _recuperacion(db, fin: date, idx_prev: float | None, ambito: str | None,
                  semanas: int) -> dict:
    """Semanas hasta volver al nivel previo. `None` con motivo cuando no se puede.

    «No recuperado» y «no medible» son cosas distintas y no se pueden mostrar igual:
    la primera es un hallazgo (el episodio dejó huella), la segunda es falta de datos.
    """
    if idx_prev is None:
        return {"recuperado_en_semanas": None,
                "motivo_recuperacion": "sin nivel previo medible contra el cual comparar",
                "serie_posterior": []}

    serie = _serie_posterior(db, fin + timedelta(days=1), semanas, ambito)
    medibles = [s for s in serie if s["n"] >= N_MIN_POR_SEMANA and s["indice"] is not None]
    if len(medibles) < SEMANAS_SOSTEN:
        return {"recuperado_en_semanas": None,
                "motivo_recuperacion": (
                    f"hacen falta {SEMANAS_SOSTEN} semanas medibles seguidas para "
                    f"afirmar una recuperación y solo hay {len(medibles)}"),
                "serie_posterior": serie}

    # Recuperado = SEMANAS_SOSTEN consecutivas por encima del nivel previo. Un solo
    # pico no cuenta: volver y quedarse son cosas distintas.
    seguidas = 0
    for i, s in enumerate(serie, start=1):
        if s["n"] < N_MIN_POR_SEMANA or s["indice"] is None:
            seguidas = 0          # una semana sin datos corta la racha
            continue
        if s["indice"] >= idx_prev:
            seguidas += 1
            if seguidas >= SEMANAS_SOSTEN:
                # La recuperación empezó donde arrancó la racha, no donde se confirmó.
                return {"recuperado_en_semanas": i - SEMANAS_SOSTEN + 1,
                        "motivo_recuperacion": None, "serie_posterior": serie}
        else:
            seguidas = 0
    return {"recuperado_en_semanas": None,
            "motivo_recuperacion": (
                f"no se sostuvo {SEMANAS_SOSTEN} semanas sobre el nivel previo dentro "
                f"de las {semanas} posteriores"),
            "serie_posterior": serie}


def fusionar_solapados(episodios: list[dict]) -> list[dict]:
    """Une los episodios que se solapan en el mismo ámbito en UN episodio.

    Hace falta porque la toma y el paro de un mismo conflicto se cargan por separado
    —y con razón: en 2026 la toma terminó el 26 de junio y la paralización siguió
    hasta el 3 de julio, y fusionarlas en el calendario borraría esa semana—. Pero
    para medir respuesta a shock son **el mismo shock**: la comunidad vivió una sola
    interrupción, no dos.

    Sin esto, los dos episodios medibles del corpus se contaban como cuatro, con
    números idénticos, y el resultado parecía tener el doble de evidencia de la que
    tiene. Las facetas se conservan en `componentes` para no perder el detalle.

    El período resultante es la UNIÓN: del primer inicio al último fin, que es lo que
    duró la interrupción vista desde afuera.
    """
    if not episodios:
        return []
    orden = sorted(episodios, key=lambda e: (e.get("ambito") or "", e["desde"]))
    grupos: list[dict] = []
    for ev in orden:
        fin_ev = ev["hasta"] or ev["desde"]
        ultimo = grupos[-1] if grupos else None
        mismo_ambito = ultimo is not None and (ultimo.get("ambito") or "") == (ev.get("ambito") or "")
        # Se solapan si el nuevo arranca antes de que termine el acumulado.
        if ultimo is not None and mismo_ambito and ev["desde"] <= (ultimo["hasta"] or ultimo["desde"]):
            ultimo["hasta"] = max(ultimo["hasta"] or ultimo["desde"], fin_ev)
            ultimo["componentes"].append(ev["nombre"])
            # El grupo hereda el tipo más grave y la confianza más débil: si una de
            # las partes tiene fechas estimadas, el conjunto tampoco está confirmado.
            if ev["tipo"] == "paro":
                ultimo["tipo"] = "paro"
            if ev.get("confianza") != "confirmado":
                ultimo["confianza"] = ev.get("confianza") or "estimado"
            ultimo["dias"] = (ultimo["hasta"] - ultimo["desde"]).days + 1
            continue
        grupos.append({**ev, "hasta": fin_ev, "componentes": [ev["nombre"]],
                       "dias": (fin_ev - ev["desde"]).days + 1})
    # El nombre del grupo es el de su componente más largo: el que mejor lo describe.
    for g in grupos:
        if len(g["componentes"]) > 1:
            g["nombre"] = max(g["componentes"], key=len)
    return sorted(grupos, key=lambda e: e["desde"])


def respuesta_a_shock(db, *, solo_confirmados: bool = False,
                      semanas_recuperacion: int = 12) -> dict:
    """Perfil de TODOS los episodios disruptivos, con su evidencia declarada.

    No devuelve un promedio. Ver el docstring del módulo: con dos episodios medibles
    y once vacíos, un promedio tendría aspecto de resultado y contenido de ruido.
    """
    episodios = fusionar_solapados(
        calendario.episodios_disruptivos(db, solo_confirmados=solo_confirmados))
    # Se arma UNA sola vez para todos los episodios: son ~8.000 filas y cada perfil
    # las recorre por ventana, no por comentario.
    try:
        # `critica.filas_de_comentarios` trae handle, fecha, tono Y tema: sirve para
        # las tres lecturas nuevas y para la estandarizacion. Se le agrega el tipo de
        # cuenta, que es lo unico que le falta a esa consulta.
        filas_comp = filas_para_composicion(db)
        pesos_comp = pesos_por_tipo(filas_comp)
    except Exception:
        # Sin composición se sigue informando la caída cruda: es peor no responder
        # nada que responder sin la corrección.
        filas_comp, pesos_comp = None, {}
    perfiles = [perfil_episodio(db, e, semanas_recuperacion=semanas_recuperacion,
                                filas_comp=filas_comp, pesos_comp=pesos_comp)
                for e in episodios]
    # Los medibles primero, y dentro de ellos los más recientes.
    orden = {EVIDENCIA_SUFICIENTE: 0, EVIDENCIA_PARCIAL: 1, EVIDENCIA_NULA: 2}
    perfiles.sort(key=lambda p: (orden[p["evidencia"]], -p["desde"].toordinal()))

    medibles = [p for p in perfiles if p["evidencia"] == EVIDENCIA_SUFICIENTE]
    caidas = [p["caida"] for p in medibles if p["caida"] is not None]

    return {
        "episodios": perfiles,
        "total": len(perfiles),
        "medibles": len(medibles),
        "n_min_por_semana": N_MIN_POR_SEMANA,
        "semanas_sosten": SEMANAS_SOSTEN,
        # Solo se informa el rango cuando hay más de un caso; con uno, el "rango" es
        # el propio número disfrazado de estadística.
        "caida_rango": ([min(caidas), max(caidas)] if len(caidas) > 1 else None),
        "avisos": _avisos(perfiles, medibles, caidas),
    }


def _avisos(perfiles: list[dict], medibles: list[dict], caidas: list[float]) -> list[str]:
    avisos: list[str] = []
    sin = len(perfiles) - len(medibles)
    if sin:
        avisos.append(
            f"{sin} de {len(perfiles)} episodios no se pueden medir: no hay "
            f"{N_MIN_POR_SEMANA}+ comentarios por semana en su ventana previa o "
            "durante. La ingesta "
            "tiene volumen recién desde fines de 2024, así que los paros anteriores "
            "quedaron sin corpus alrededor."
        )
    if len(medibles) == 1:
        avisos.append(
            "Hay UN solo episodio medible. Alcanza para describir ese caso, no para "
            "estimar cuánto cuesta un paro en general: no se puede promediar sobre uno."
        )
    elif len(caidas) > 1:
        avisos.append(
            f"Con {len(caidas)} episodios medibles el rango es indicativo, no un "
            "promedio: cada paro tuvo su propio contexto y duración."
        )
    estimados = [p for p in perfiles if p.get("confianza") != "confirmado"]
    if estimados:
        avisos.append(
            f"{len(estimados)} episodios tienen fechas ESTIMADAS. Su caída puede "
            "leerse con cuidado, pero su duración y su recuperación no: medirlas "
            "sobre fechas aproximadas mide la suposición."
        )
    return avisos
