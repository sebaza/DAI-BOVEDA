"""Render docs/12_benchmark_t6.md from the gitignored aggregate JSON (``artefactos/resultados_t6.json``).

``python tools/informe_t6.py --doc`` assembles the document from ``tools/plantilla_t6.md`` (hand-written text) and the tables
built here. Markers in the template: ``{{tabla:NOMBRE}}`` (a named block), ``{{x:ruta}}`` (a value of the JSON by dotted path),
``{{pct:ruta}}`` (a proportion as a percentage), ``{{n:ruta}}`` (a count; 1 to 9 print as "< 10"), ``{{inc:ruta}}`` (an
incidence ``{punto, lo, hi}`` as a percentage with its interval), ``{{ic:split.tau.modelo.metrica}}`` (metric with interval),
``{{d:split.tau.a.b.metrica}}`` (paired difference a - b), ``{{meta:...}}``.
Aggregates only: a group with fewer than 100 units or fewer than 10 events is never printed; counts under 10 are shown as
"< 10" and a rate that would reveal one is a dash.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cambios_etapa_b as CB  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
ART = RAIZ / "artefactos"

NOMBRES = {"baseline_programa": "Incidencia histórica por programa", "cox_perfil": "Cox (perfil de ingreso)",
           "cox_agg": "Cox (ingreso + trayectoria académica)"}
ORDEN = ["baseline_programa", "cox_perfil", "cox_agg"]
ETIQ = {"ap": "AP", "roc_auc": "ROC-AUC", "brier": "Brier", "ece": "ECE"}
ANIOS = {"2": "1 año", "4": "2 años", "8": "4 años"}
SPLIT_ETIQ = {"train": "train (egreso hasta 2022)", "valid": "valid (egreso 2023)", "test": "test (egreso 2024 o después)"}
MIN_RIESGO = 100


def miles(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def coma(t: str) -> str:
    return t.replace(".", ",")


def pct(x: float, dec: int = 1) -> str:
    return coma(f"{100 * x:.{dec}f}") + " %"


def pct_ic(d: Dict[str, float], dec: int = 1) -> str:
    if d["lo"] != d["lo"]:
        return pct(d["punto"], dec)
    return coma(f"{100 * d['punto']:.{dec}f} % [{100 * d['lo']:.{dec}f}; {100 * d['hi']:.{dec}f}]")


def fmt(x: float, d: int = 3, signo: bool = False) -> str:
    if x != x:
        return "—"
    return coma(f"{x:+.{d}f}" if signo else f"{x:.{d}f}")


def n_pub(n: int) -> str:
    """Counts of 1 to 9 people are never printed."""
    return "< 10" if 0 < int(n) < 10 else miles(n)


def tasa_pub(eventos: int, n: int, dec: int = 1) -> str:
    """A rate whose numerator is between 1 and 9 would reveal that count: it is a dash."""
    return "—" if 0 < int(eventos) < 10 or n == 0 else pct(eventos / n, dec)


def con_ic(d: Dict[str, float], dec: int = 3) -> str:
    cero = f"{0:.{dec}f}"
    limpio = lambda x: cero if f"{x:.{dec}f}" == f"{-0.0:.{dec}f}" else f"{x:.{dec}f}"      # noqa: E731  (no "-0,000")
    if d["lo"] != d["lo"]:
        return limpio(d["punto"])
    return f"{limpio(d['punto'])} [{limpio(d['lo'])}; {limpio(d['hi'])}]"


def dec(m: str) -> int:
    return 4 if m in ("brier", "ece") else 3


def celda_incidencia(inc: Dict[str, Dict[str, float]], en_riesgo: Optional[Dict[str, int]], tau: str) -> str:
    """Incidence at ``tau`` with its interval; a dash when fewer than ``MIN_RIESGO`` units are still followed up at ``tau``."""
    if en_riesgo is not None and en_riesgo.get(tau, 0) < MIN_RIESGO:
        return "—"
    return pct_ic(inc[tau])


# ---------------------------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------------------------
def tabla_embudo(e: Dict, principal: Optional[tuple] = None) -> List[str]:
    filas = [("Trayectorias de pregrado de las cohortes 2015 o posteriores (población T3: sin IN/PE/IE, sin Intercambio, Plan Común unido a su especialidad)", "poblacion"),
             ("− sin egreso en un período cerrado (el egreso es el evento de T3)", "sin_egreso"),
             ("= **Trayectorias egresadas**", "egresados"),
             ("− con egreso anterior al inicio de la fuente de postgrado (201650)", "egreso_antes_de_la_fuente"),
             ("− con matrícula de postgrado UCN **antes** del ingreso a pregrado", "postgrado_previo_antes"),
             ("− con matrícula de postgrado UCN **durante** el pregrado o en el semestre del egreso", "postgrado_previo_durante"),
             ("− sin semestre cerrado después del egreso (egreso en el último período cerrado)", "sin_seguimiento"),
             ("= Unidades con el evento anterior (`matricula_postgrado`, sensibilidad)", "elegibles"),
             ("… de ellas, con matrícula posterior al egreso (evento anterior)", "eventos")]
    out = ["| Paso | Trayectorias |", "|---|---|"]
    for nombre, clave in filas:
        out.append(f"| {nombre} | {n_pub(e[clave])} |")
    if principal is not None and "previo_estados" in e:
        out.append(f"| − con matrícula previa en la fuente de estados de postgrado (evento principal, D65) | {n_pub(e['previo_estados'])} |")
        out.append(f"| = **Unidades de T6 con el evento principal (estado `M`, P86)** | {n_pub(principal[0])} |")
        out.append(f"| … de ellas, con estado `M` posterior al egreso dentro del seguimiento (evento principal) | {n_pub(principal[1])} |")
    return out


def tabla_viabilidad(v: Dict) -> List[str]:
    u = v["umbrales"]
    out = ["| Familia de modelos | Mínimo de eventos por partición | train | valid | test | ¿Se entrena? |", "|---|---|---|---|---|---|"]
    ev = v["eventos"]
    for nombre, clave in (("Línea base e incidencia por programa, Cox", "clasico"), ("CatBoost", "catboost"), ("MLP en GPU (3 semillas)", "red")):
        out.append(f"| {nombre} | {u[clave]} | {n_pub(ev['train'])} | {n_pub(ev['valid'])} | {n_pub(ev['test'])} | {'sí' if v[clave] else 'no'} |")
    return out


def tabla_horizonte(ph: Dict) -> List[str]:
    out = ["| Horizonte | Partición | Unidades con seguimiento completo | Matriculados en el horizonte | Tasa |", "|---|---|---|---|---|"]
    for tau, d in ph.items():
        for s in ("train", "valid", "test"):
            c = d[s]
            if c["n"] == 0:
                out.append(f"| {ANIOS[tau]} | {SPLIT_ETIQ[s]} | 0 | — | — |")
            else:
                out.append(f"| {ANIOS[tau]} | {SPLIT_ETIQ[s]} | {miles(c['n'])} | {n_pub(c['eventos'])} | {tasa_pub(c['eventos'], c['n'])} |")
    return out


def tabla_particion(desc: Dict) -> List[str]:
    out = ["| Partición | Unidades | Matriculados después del egreso | Seguimiento (semestres: mín. · mediana · máx.) | 1 año | 2 años | 4 años |", "|---|---|---|---|---|---|---|"]
    filas = [("global", "Todas las unidades", desc["global"], None)] + [(s, SPLIT_ETIQ[s], desc["particion"][s], desc["particion"][s]["seguimiento"]) for s in ("train", "valid", "test")]
    for _, etq, d, seg in filas:
        s = f"{seg['min']} · {coma(str(seg['mediana']))} · {seg['max']}" if seg else "—"
        celdas = [celda_incidencia(d["incidencia"], d["en_riesgo"], t) for t in ("2", "4", "8")]
        out.append(f"| {etq} | {miles(d['n'])} | {n_pub(d['eventos'])} | {s} | " + " | ".join(celdas) + " |")
    return out


def _etq_grupo(nivel: str, f: Dict) -> str:
    if nivel == "facultad":
        return f["grupo"]                                  # the faculty NAME (stage B)
    if nivel == "programa":
        return f"{f['grupo']} · {f.get('nombre', '')}".strip(" ·")
    return f["grupo"]


def _grupos(n: int, adjetivo: str) -> str:
    return f"{n} grupo {adjetivo}" if n == 1 else f"{n} grupos {adjetivo}s"


def tabla_incidencia(t: Dict, nivel: str) -> List[str]:
    """Observed cumulative incidence of the reportable groups; the suppressed ones are only counted."""
    r = t["resumen"]
    if not t["filas"]:
        return [f"No hay grupos que cumplan los umbrales (n ≥ {r['n_min']} y ≥ {r['eventos_min']} eventos); "
                f"{_grupos(r['grupos_suprimidos'], 'suprimido')}."]
    out = ["| Grupo | Unidades | Matriculados | 1 año | 2 años |", "|---|---|---|---|---|"]
    for f in sorted(t["filas"], key=lambda x: -x["incidencia"]["2"]["punto"]):
        riesgo = f.get("en_riesgo")
        out.append(f"| {_etq_grupo(nivel, f)} | {miles(f['n'])} | {miles(f['eventos'])} | "
                   f"{celda_incidencia(f['incidencia'], riesgo, '2')} | {celda_incidencia(f['incidencia'], riesgo, '4')} |")
    out.append("")
    out.append(f"{_grupos(r['grupos_reportables'], 'reportado')} y {_grupos(r['grupos_suprimidos'], 'suprimido')} (menos de {r['n_min']} unidades o menos de "
               f"{r['eventos_min']} matriculados); los reportados cubren {miles(r['filas_en_reportables'])} de {miles(r['filas_total'])} unidades.")
    return out


def tabla_metricas(ev: Dict, split: str) -> List[str]:
    out = []
    for tau, h in ev["horizontes"][split].items():
        if h["n"] == 0 or not h["modelos"]:
            continue
        out.append(f"**{ANIOS[tau].capitalize()}** · {miles(h['n'])} unidades con seguimiento completo, {n_pub(h['eventos'])} matriculados"
                   f" · {'concluyente' if h['conclusivo'] else '**no concluyente** (menos de 30 matriculados o de 30 no matriculados)'}")
        out.append("")
        out.append("| Modelo | " + " | ".join(ETIQ.values()) + " |")
        out.append("|---|" + "---|" * len(ETIQ))
        for m in ORDEN:
            d = h["modelos"][m]
            celdas = [coma(con_ic(d[c], dec(c))) if split == "test" else coma(f"{d[c]['punto']:.{dec(c)}f}") for c in ETIQ]
            out.append(f"| {NOMBRES[m]} | " + " | ".join(celdas) + " |")
        out.append("")
    return out


def tabla_deltas(ev: Dict, split: str = "test") -> List[str]:
    out = ["| Horizonte | Diferencia pareada | ΔAP | ΔROC-AUC | Lectura (ΔAP) |", "|---|---|---|---|---|"]
    for tau, h in ev["horizontes"][split].items():
        for p, d in h["pares"].items():
            a, b = p.split("__vs__")
            ap = d["ap"]
            lectura = "mejora" if ap["lo"] > 0 else "empeora" if ap["hi"] < 0 else "sin diferencia (el intervalo incluye 0)"
            out.append(f"| {ANIOS[tau]} | {NOMBRES[a]} − {NOMBRES[b]} | {coma(con_ic(ap))} | {coma(con_ic(d['roc_auc']))} | {lectura} |")
    return out


def tabla_calibracion(ev: Dict) -> List[str]:
    """Reliability of the kept model and of the baseline at 1 year on test; bins are merged so that none has 1 to 9 events."""
    cal = ev["calibracion_test"]
    cons = ev["seleccion"]["conservado"]
    out = ["| Modelo | Grupo de riesgo (1 = más alto) | n | Riesgo medio predicho | Incidencia observada |", "|---|---|---|---|---|"]
    for m in dict.fromkeys([cons, "baseline_programa"]):
        for f in cal[m]:
            ev_ = round(f["tasa_observada"] * f["n"])
            out.append(f"| {NOMBRES[m]} | {f['grupo']} | {miles(f['n'])} | {pct(f['riesgo_medio'], 2)} | {tasa_pub(ev_, f['n'], 2)} |")
    return out


def tabla_grupos_resumen(ev: Dict) -> List[str]:
    out = ["| Evaluación | Nivel | Grupos | Reportables (n ≥ 100 y ≥ 10 matriculados) | Suprimidos | Unidades en reportables |", "|---|---|---|---|---|---|"]
    for clave, etq in (("test", "test"), ("valid_test", "valid + test")):
        g = ev["grupos"][clave]
        for nivel in ("programa", "facultad"):
            r = g[nivel]["resumen"]
            out.append(f"| {etq} (1 año; {miles(g['n'])} unidades) | {nivel} | {r['grupos_total']} | {r['grupos_reportables']} | "
                       f"{r['grupos_suprimidos']} | {miles(r['filas_en_reportables'])} de {miles(r['filas_total'])} |")
    return out


def tabla_grupos_modelo(ev: Dict, clave: str, nivel: str) -> List[str]:
    filas = ev["grupos"][clave][nivel]["filas"]
    if not filas:
        return ["No hay grupos que cumplan los umbrales (n ≥ 100 y ≥ 10 matriculados en el horizonte)."]
    out = ["| " + ("Programa" if nivel == "programa" else "Facultad") + " | n | Matriculados | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la incidencia histórica |",
           "|---|---|---|---|---|---|---|"]
    for f in sorted(filas, key=lambda r: -r["tasa_observada"]["punto"]):
        out.append(f"| {_etq_grupo(nivel, f)} | {miles(f['n'])} | {miles(f['eventos'])} | {pct_ic(f['tasa_observada'])} | "
                   f"{pct_ic(f['riesgo_medio'])} | {pct_ic(f['brecha'])} | {pct_ic(f['brecha_base'])} |")
    return out


def tabla_sexo(ev: Dict) -> List[str]:
    out = ["| Sexo (registro) | Unidades | Matriculados | Tasa observada | Riesgo medio predicho | AP | ROC-AUC |", "|---|---|---|---|---|---|---|"]
    for f in ev["sexo"]["tabla"]:
        if f["eventos"] < 10:
            out.append(f"| {f['grupo']} | {miles(f['n'])} | < 10 | — | {pct(f['riesgo_medio'], 2)} | — | — |")
        else:
            out.append(f"| {f['grupo']} | {miles(f['n'])} | {miles(f['eventos'])} | {pct(f['tasa_observada'], 2)} | {pct(f['riesgo_medio'], 2)} | "
                       f"{fmt(f['ap'])} | {fmt(f['roc_auc'])} |")
    return out


def tabla_sensibilidad(desc: Dict, viab: Dict, sens: Optional[Dict] = None) -> List[str]:
    """The three readings of the event: the primary (state source, P86), the previous one (``estado_matricula`` of
    ``matricula_postgrado``) and any later row of ``matricula_postgrado``."""
    s = desc["sensibilidad_cualquier_fila"]
    out = ["| Definición del evento | Unidades | train | valid | test | Total de eventos | Incidencia a 1 año | a 2 años | a 4 años |", "|---|---|---|---|---|---|---|---|---|"]
    p = viab["eventos"]
    g = desc["global"]
    out.append(f"| **Estado `M` de la fuente de estados de postgrado (principal, P86)** | {miles(g['n'])} | {n_pub(p['train'])} | {n_pub(p['valid'])} | {n_pub(p['test'])} | {miles(sum(p.values()))} | "
               + " | ".join(celda_incidencia(g["incidencia"], g["en_riesgo"], t) for t in ("2", "4", "8")) + " |")
    if sens:
        d, v = sens["descriptivo"], sens["viabilidad"]["eventos"]
        gg = d["global"]
        out.append(f"| `estado_matricula = MATRICULADO` de `matricula_postgrado` (evento anterior, sensibilidad) | {miles(gg['n'])} | {n_pub(v['train'])} | {n_pub(v['valid'])} | {n_pub(v['test'])} | {miles(sum(v.values()))} | "
                   + " | ".join(celda_incidencia(gg["incidencia"], gg["en_riesgo"], t) for t in ("2", "4", "8")) + " |")
        s = d["sensibilidad_cualquier_fila"]
    e = s["eventos_por_particion"]
    sg = s["global"]
    out.append(f"| Cualquier fila de postgrado UCN posterior al egreso (`matricula_postgrado`, sensibilidad) | {miles(sg['n'])} | {n_pub(e['train'])} | {n_pub(e['valid'])} | {n_pub(e['test'])} | {miles(sum(e.values()))} | "
               + " | ".join(celda_incidencia(sg["incidencia"], sg["en_riesgo"], t) for t in ("2", "4", "8")) + " |")
    return out


def tabla_viabilidad_fuentes(res: Dict) -> List[str]:
    """Viability gate (D68) for both event sources with the stage B counts."""
    out = ["| Fuente del evento | Eventos train / valid / test | Escalón clásico (≥ 30 por partición) | CatBoost (≥ 100 de train) | Red (≥ 300 de train) |", "|---|---|---|---|---|"]
    si = lambda b: "sí" if b else "no"                                                              # noqa: E731
    for etq, v in (("Estados de postgrado (principal)", res["viabilidad"]), ("`matricula_postgrado` (sensibilidad)", res["sensibilidad_matricula"]["viabilidad"])):
        e = v["eventos"]
        out.append(f"| {etq} | {miles(e['train'])} / {miles(e['valid'])} / {miles(e['test'])} | {si(v['clasico'])} | {si(v['catboost'])} | {si(v['red'])} |")
    return out


def tabla_niveles(res: Dict) -> List[str]:
    """Events by program level (magister, doctorado, otro) and the cause-specific cumulative incidence of each level."""
    n, inc = res["eventos_por_nivel"], res["incidencia_por_nivel"]
    etq = {"magister": "Magíster", "doctorado": "Doctorado", "otro": "Otro (diplomado, postítulo, sin nombre)"}
    out = ["| Nivel del programa | train | valid | test | Total | Incidencia a 1 año | a 2 años | a 4 años |", "|---|---|---|---|---|---|---|---|"]
    ocultas = False
    for nivel in ("magister", "doctorado", "otro"):
        cel = []
        for s in ("train", "valid", "test"):
            v = n["por_particion"][s].get(nivel)
            cel.append("< 10" if v is None else miles(v))
            ocultas = ocultas or v is None
        tot = n["total"].get(nivel)
        i = inc[nivel]["incidencia"]
        incs = ["—", "—", "—"] if i is None else [pct_ic(i[t]) for t in ("2", "4", "8")]
        out.append(f"| {etq[nivel]} | " + " | ".join(cel) + f" | {'< 10' if tot is None else miles(tot)} | " + " | ".join(incs) + " |")
    out.append("")
    out.append("Incidencia específica de causa: la primera matrícula de otro nivel censura la unidad en ese momento. Un recuento de 1 a 9 no se imprime.")
    return out


def tabla_modelos_sensibilidad(res: Dict) -> List[str]:
    """Test metrics at 1 year of the three models with the previous event (sensitivity run)."""
    sens = res["sensibilidad_matricula"]
    if not sens.get("modelos"):
        return ["La sensibilidad no es viable."]
    h = sens["modelos"]["horizontes"]["test"]["2"]
    out = [f"{miles(h['n'])} unidades con seguimiento completo a 1 año y {n_pub(h['eventos'])} matriculados en test (evento anterior).", "",
           "| Modelo | " + " | ".join(ETIQ.values()) + " |", "|---|" + "---|" * len(ETIQ)]
    for m in ORDEN:
        d = h["modelos"][m]
        out.append(f"| {NOMBRES[m]} | " + " | ".join(coma(con_ic(d[c], dec(c))) for c in ETIQ) + " |")
    s = sens["modelos"]["seleccion"]
    out.append("")
    out.append(f"Modelo conservado con el evento anterior: **{NOMBRES[s['conservado']]}** (mejor Cox en valid: {NOMBRES[s['mejor_cox']]}; "
               f"ΔAP frente a la incidencia por programa: {coma(con_ic(s['delta_ap_vs_baseline']))}).")
    return out


def tabla_cambios(res: Dict) -> List[str]:
    prev = CB.cargar_previo("resultados_t6")
    if prev is None:
        return CB.sin_previo()
    ant = prev["modelos"]["horizontes"]["test"]["2"]
    nue = res["modelos"]["horizontes"]["test"]["2"]
    sa, sn = prev["modelos"]["seleccion"], res["modelos"]["seleccion"]
    filas = [("Eventos de train / valid / test", "/".join(miles(prev["viabilidad"]["eventos"][s]) for s in ("train", "valid", "test")),
              "/".join(miles(res["viabilidad"]["eventos"][s]) for s in ("train", "valid", "test")), 0),
             ("Unidades", prev["n_particion"] and sum(prev["n_particion"].values()), sum(res["n_particion"].values()), 0),
             ("Incidencia acumulada a 1 año (todas las unidades)", prev["descriptivo"]["global"]["incidencia"]["2"], res["descriptivo"]["global"]["incidencia"]["2"], 4),
             ("Incidencia acumulada a 4 años (todas las unidades)", prev["descriptivo"]["global"]["incidencia"]["8"], res["descriptivo"]["global"]["incidencia"]["8"], 4),
             ("Incidencia por programa, AP test a 1 año", ant["modelos"]["baseline_programa"]["ap"], nue["modelos"]["baseline_programa"]["ap"], 3),
             ("Cox (perfil), AP test a 1 año", ant["modelos"]["cox_perfil"]["ap"], nue["modelos"]["cox_perfil"]["ap"], 3),
             ("Cox (perfil), ROC-AUC test a 1 año", ant["modelos"]["cox_perfil"]["roc_auc"], nue["modelos"]["cox_perfil"]["roc_auc"], 3),
             ("Cox (perfil) − incidencia por programa, ΔAP pareado", ant["pares"].get("cox_perfil__vs__baseline_programa", {}).get("ap"),
              nue["pares"].get("cox_perfil__vs__baseline_programa", {}).get("ap"), 3)]
    out = CB.tabla(filas)
    out.append("")
    out.append(f"Modelo conservado: {NOMBRES[sa['conservado']]} → {NOMBRES[sn['conservado']]}. "
               f"Programas con incidencia reportable: {prev['descriptivo']['grupos']['programa']['resumen']['grupos_reportables']} → "
               f"{res['descriptivo']['grupos']['programa']['resumen']['grupos_reportables']}; "
               f"facultades: {prev['descriptivo']['grupos']['facultad']['resumen']['grupos_reportables']} → "
               f"{res['descriptivo']['grupos']['facultad']['resumen']['grupos_reportables']}.")
    return out


def tabla_tiempos(res: Dict) -> List[str]:
    out = ["| Modelo | Segundos de entrenamiento | Columnas de entrada | Penalización elegida (valid) |", "|---|---|---|---|"]
    for m in ORDEN:
        i = res["info"][m]
        out.append(f"| {NOMBRES[m]} | {fmt(res['tiempos_s'][m], 1)} | {i.get('columnas_entrada', '—')} | {coma(str(i.get('penalizador', '—')))} |")
    return out


def bloques(res: Dict) -> Dict[str, str]:
    nl = "\n"
    d = res["descriptivo"]
    b: Dict[str, str] = {
        "embudo": nl.join(tabla_embudo(res["embudo"], (res["n_unidades"], res["eventos"]) if "n_unidades" in res else None)), "viabilidad": nl.join(tabla_viabilidad(res["viabilidad"])),
        "horizonte": nl.join(tabla_horizonte(d["por_horizonte"])), "particion": nl.join(tabla_particion(d)),
        "sensibilidad": nl.join(tabla_sensibilidad(d, res["viabilidad"], res.get("sensibilidad_matricula"))),
        "viabilidad_fuentes": nl.join(tabla_viabilidad_fuentes(res)), "niveles": nl.join(tabla_niveles(res)),
        "modelos_sensibilidad": nl.join(tabla_modelos_sensibilidad(res)), "cambios": nl.join(tabla_cambios(res)),
        "grupos.programa": nl.join(tabla_incidencia(d["grupos"]["programa"], "programa")),
        "grupos.facultad": nl.join(tabla_incidencia(d["grupos"]["facultad"], "facultad")),
    }
    for nombre, t in d["estratos"].items():
        b[f"estrato.{nombre}"] = nl.join(tabla_incidencia(t, nombre))
    if res.get("modelos"):
        ev = res["modelos"]
        b.update({"metricas.test": nl.join(tabla_metricas(ev, "test")), "metricas.valid": nl.join(tabla_metricas(ev, "valid")),
                  "deltas.test": nl.join(tabla_deltas(ev)), "deltas.valid": nl.join(tabla_deltas(ev, "valid")),
                  "calibracion": nl.join(tabla_calibracion(ev)), "grupos_resumen": nl.join(tabla_grupos_resumen(ev)),
                  "sexo": nl.join(tabla_sexo(ev)), "tiempos": nl.join(tabla_tiempos(res))})
        for clave in ("test", "valid_test"):
            for nivel in ("programa", "facultad"):
                b[f"gm.{clave}.{nivel}"] = nl.join(tabla_grupos_modelo(ev, clave, nivel))
    return b


def _ruta(res: Dict, ruta: str):
    x = res
    for p in ruta.split("."):
        x = x[int(p)] if isinstance(x, list) else x[p]
    return x


def documento() -> str:
    res = json.loads((ART / "resultados_t6.json").read_text(encoding="utf-8"))
    blq = bloques(res)
    plantilla = (RAIZ / "tools" / "plantilla_t6.md").read_text(encoding="utf-8")

    def sustituir(m) -> str:
        clave = m.group(1)
        tipo, _, ruta = clave.partition(":")
        if tipo == "meta":
            return {"snapshot_hash": res["snapshot_hash"], "version_codigo": res["version_codigo"], "ram": f"{res['ram_pico_mb']:.0f}",
                    "segundos": f"{res['segundos_totales']:.0f}", "cierre": res["periodo_cierre"], "boot": str(res["n_boot"])}[ruta]
        if tipo == "tabla":
            return blq[ruta]
        if tipo == "x":
            v = _ruta(res, ruta)
            return coma(f"{v:.3f}") if isinstance(v, float) else miles(v) if isinstance(v, int) else str(v)
        if tipo == "pct":
            return pct(float(_ruta(res, ruta)))
        if tipo == "n":
            return n_pub(int(_ruta(res, ruta)))
        if tipo == "inc":
            return pct_ic(_ruta(res, ruta))
        if tipo == "ic":
            split, tau, modelo, metrica = ruta.split(".")
            return coma(con_ic(res["modelos"]["horizontes"][split][tau]["modelos"][modelo][metrica], dec(metrica)))
        if tipo == "d":
            split, tau, a, b2, metrica = ruta.split(".")
            return coma(con_ic(res["modelos"]["horizontes"][split][tau]["pares"][f"{a}__vs__{b2}"][metrica], dec(metrica)))
        raise KeyError(clave)

    return re.sub(r"\{\{([^}]+)\}\}", sustituir, plantilla)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["--doc"]:
        (RAIZ / "docs" / "12_benchmark_t6.md").write_text(documento(), encoding="utf-8")
        print("escrito docs/12_benchmark_t6.md")
        return 0
    res = json.loads((ART / "resultados_t6.json").read_text(encoding="utf-8"))
    for nombre, texto in bloques(res).items():
        print(f"\n<!--{{{{tabla:{nombre}}}}}-->\n{texto}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
