"""Render docs/11_benchmark_t4_t5.md from the gitignored aggregate JSON (``artefactos/resultados_t45.json``).

``python tools/informe_t45.py --doc`` assembles the document from ``tools/plantilla_t45.md`` (hand-written text) and the
tables built here. Markers in the template: ``{{tabla:NOMBRE}}`` (a named block), ``{{v:k.T.modelo.metrica}}`` (point value,
Spanish decimal comma), ``{{ic:k.T.modelo.metrica}}`` (point and 95 % interval), ``{{d:k.T.a.b.metrica}}`` (paired
difference a - b with interval), ``{{mc:k.modelo.metrica}}`` (multiclass, point and interval), ``{{x:ruta}}`` (a value of
the JSON by dotted path), ``{{pct:ruta}}``, ``{{tasa:k.split.resultado}}`` (share of a split), ``{{sens:k.metrica}}`` (T5 sensitivity of the
kept model), ``{{meta:...}}``. ``T`` is ``T4`` or ``T5``.
Aggregates only: a group with fewer than 100 rows or fewer than 10 events is never printed; counts under 10 are shown as "< 10".
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cambios_etapa_b as CB  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
ART = RAIZ / "artefactos"

NOMBRES = {
    "baseline_tasa": "Tasa histórica por programa", "lr_adm": "Logística (perfil de ingreso)",
    "lr_agg": "Logística (ingreso + agregados)", "cb_adm": "CatBoost (perfil de ingreso)",
    "cb_agg": "CatBoost (ingreso + agregados)", "gru_adm": "GRU (ingreso + secuencia)",
    "gru_agg": "GRU (ingreso + agregados + secuencia)",
    "mc_base": "Frecuencias de resultado por programa", "mc_lr_agg": "Logística multinomial (ingreso + agregados)",
    "mc_cb_agg": "CatBoost multiclase (ingreso + agregados)",
}
ORDEN = ["baseline_tasa", "lr_adm", "lr_agg", "cb_adm", "cb_agg", "gru_adm", "gru_agg"]
ETIQ = {"ap": "AP", "roc_auc": "ROC-AUC", "brier": "Brier", "ece": "ECE", "recall_10": "Recall@10 %", "precision_10": "Precision@10 %"}
TAREA = {"T4": "T4 (transición real de programa)", "T5": "T5 (eliminación)", "T5E": "T5 (eliminación efectiva, sin reintegro)"}
CORTE = {"2": "k = 2 (fin del 2.º semestre)", "4": "k = 4 (fin del 4.º semestre)"}
RESULTADO = {"continua": "Continúa", "egreso": "Egreso", "transicion": "Transición (T4)", "eliminacion": "Eliminación (T5)",
             "otra_salida": "Otra salida", "transicion_ambigua": "Transición ambigua (excluida)", "censurado": "Censurado (excluido)"}
SPLITS = ("train", "valid", "test", "posterior")
SPLIT_ETIQ = {"train": "train (2015–2019)", "valid": "valid (2020–2021)", "test": "test (2022–2023)", "posterior": "control posterior (2024 en adelante)"}


def miles(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def coma(t: str) -> str:
    return t.replace(".", ",")


def pct(x: float, dec: int = 1) -> str:
    return coma(f"{100 * x:.{dec}f}") + " %"


def fmt(x: float, d: int = 3, signo: bool = False) -> str:
    """Spanish-decimal number; a missing value is a dash."""
    if x != x:
        return "—"
    return coma(f"{x:+.{d}f}" if signo else f"{x:.{d}f}")


def n_pub(n: int) -> str:
    """Counts of 1 to 9 people are never printed."""
    return "< 10" if 0 < int(n) < 10 else miles(n)


def con_ic(d: Dict[str, float], dec: int = 3) -> str:
    if d["lo"] != d["lo"]:
        return f"{d['punto']:.{dec}f}"
    return f"{d['punto']:.{dec}f} [{d['lo']:.{dec}f}; {d['hi']:.{dec}f}]"


def dec(m: str) -> int:
    return 4 if m.startswith("brier") or m in ("ece", "logloss", "brier_mc") else 3


def nombre_modelo(m: str) -> str:
    return NOMBRES.get(m, m)


# ---------------------------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------------------------
def tabla_embudo(res: Dict) -> List[str]:
    e = res["embudo"]
    ks = [k for k in ("2", "4") if f"embudo_k{k}_poblacion" in e]
    filas = [("Unidades de pregrado de las cohortes 2015 o posteriores (población T3: sin IN/PE/IE, sin Intercambio, Plan Común unido a su especialidad)", "poblacion"),
             ("− sin estado de matrícula en el período del corte", "sin_matricula_en_corte"),
             ("− con estado de salida en el período del corte (D24, P52)", "salida_en_corte"),
             ("− egresado o titulado hasta el corte", "ya_egresado_o_titulado"),
             ("− sin seguimiento después del corte (corte en el último período cerrado)", "sin_seguimiento"),
             ("= Elegibles en T3", "elegibles_t3"),
             ("− con una transición ya iniciada en el período del corte (se conoce al corte)", "transicion_iniciada_en_corte"),
             ("= **Filas de T4/T5** (una por trayectoria y corte)", "elegibles"),
             ("… de ellas, con horizonte no cerrado (censuradas, fuera de los modelos)", "censurados"),
             ("… de ellas, transición ambigua (fuera de los modelos)", "n_transicion_ambigua")]
    out = ["| Paso | " + " | ".join(f"k = {k}" for k in ks) + " |", "|---|" + "---|" * len(ks)]
    for nombre, clave in filas:
        out.append(f"| {nombre} | " + " | ".join(miles(e[f"embudo_k{k}_{clave}"]) for k in ks) + " |")
    memo = [("Memo: trayectorias de Plan Común elegibles en este corte", "plan_comun_elegibles"),
            ("Memo: … de ellas, unidas a una especialidad (su elección no es una transición)", "plan_comun_unidos_elegibles"),
            ("Memo: filas con eliminación y transición dentro del horizonte (solo se cuenta la primera, §3)", "eliminacion_y_transicion"),
            ("Memo: filas con eliminación y matriculadas en el período del horizonte (en cualquier programa)", "eliminacion_con_matricula_al_horizonte"),
            ("Memo: filas observadas sin transición en el horizonte pero con una en los dos semestres siguientes", "transicion_en_los_dos_semestres_posteriores"),
            ("Memo: … de ellas, clasificadas «otra salida» (el destino empieza después del horizonte)", "otra_salida_con_transicion_posterior")]
    for nombre, clave in memo:
        out.append(f"| {nombre} | " + " | ".join(miles(e[f"embudo_k{k}_{clave}"]) for k in ks) + " |")
    return out


def tabla_resultados(res: Dict) -> List[str]:
    c = res["descriptivo"]["cuentas"]
    out = ["| k | Partición | Filas | " + " | ".join(RESULTADO[r] for r in RESULTADO) + " |", "|---|---|---|" + "---|" * len(RESULTADO)]
    for k in ("2", "4"):
        for s in SPLITS:
            d = c.get(k, {}).get(s)
            if not d:
                continue
            tot = sum(d.values())
            celdas = []
            for r in RESULTADO:
                n = d.get(r, 0)
                celdas.append("—" if n == 0 else f"{n_pub(n)}" + ("" if n < 10 else f" ({pct(n / tot)})"))
            out.append(f"| {k} | {SPLIT_ETIQ[s]} | {miles(tot)} | " + " | ".join(celdas) + " |")
    return out


def tabla_otra_salida(res: Dict) -> List[str]:
    t = res["descriptivo"]["otra_salida_tipos"]
    nombres = {"salida_explicita": "estado de salida distinto de E", "interrupcion": "interrupción (sin matrícula en el horizonte)", "ausencia": "ausencia sin estado"}
    out = ["| k | Partición | " + " | ".join(nombres.values()) + " |", "|---|---|" + "---|" * len(nombres)]
    for k in ("2", "4"):
        for s in ("train", "valid", "test"):
            d = t.get(k, {}).get(s)
            if d:
                out.append(f"| {k} | {s} | " + " | ".join(n_pub(d.get(c, 0)) for c in nombres) + " |")
    return out


def tabla_metricas(ev: Dict, tgt: str, k: str, split: str) -> List[str]:
    d = ev["targets"][tgt][split]
    ms = [m for m in ORDEN if m in d]
    cols = ["ap", "roc_auc", "brier", "ece"]
    out = ["| Modelo | " + " | ".join(ETIQ[c] for c in cols) + " |", "|---|" + "---|" * len(cols)]
    for m in ms:
        if split == "test":
            celdas = [coma(con_ic(d[m][c], dec(c))) for c in cols]
        else:
            celdas = [coma(f"{d[m][c]:.{dec(c)}f}") for c in cols]
        out.append(f"| {nombre_modelo(m)} | " + " | ".join(celdas) + " |")
    return out


def tabla_deltas(ev: Dict, tgt: str) -> List[str]:
    d = ev["targets"][tgt]["test"]
    pares = [k for k in d if "__vs__" in k]
    out = ["| Diferencia pareada (test) | ΔAP | ΔROC-AUC | ΔBrier | Lectura (ΔAP) |", "|---|---|---|---|---|"]
    for p in pares:
        a, b = p.split("__vs__")
        ap = d[p]["ap"]
        lectura = "mejora" if ap["lo"] > 0 else "empeora" if ap["hi"] < 0 else "sin diferencia (el intervalo incluye 0)"
        out.append(f"| {nombre_modelo(a)} − {nombre_modelo(b)} | {coma(con_ic(ap))} | {coma(con_ic(d[p]['roc_auc']))} | "
                   f"{coma(con_ic(d[p]['brier'], 4))} | {lectura} |")
    return out


def tabla_seleccion(res: Dict) -> List[str]:
    out = ["| Tarea | k | Mejor clásico (valid) | Mejor red (valid) | Modelo conservado | AP valid del conservado |", "|---|---|---|---|---|---|"]
    for tgt in ("T4", "T5"):
        for k in res["ks"]:
            s = res["por_k"][str(k)]["targets"][tgt]["seleccion"]
            ap = s["ap_valid"][s["conservado"]]
            out.append(f"| {tgt} | {k} | {nombre_modelo(s['clasico'])} | {nombre_modelo(s['red'])} | **{nombre_modelo(s['conservado'])}** | "
                       f"{fmt(ap)} |")
    return out


def tabla_calibracion(ev: Dict, tgt: str) -> List[str]:
    cal = ev["targets"][tgt]["calibracion_test"]
    cons = ev["targets"][tgt]["seleccion"]["conservado"]
    out = ["| Decil de riesgo | " + f"{nombre_modelo(cons)}: riesgo medio | observado | n |" + " Tasa histórica: riesgo medio | observado |", "|---|---|---|---|---|---|"]
    a, b = cal[cons], cal["baseline_tasa"]
    for i, fila in enumerate(a):
        bb = b[i] if i < len(b) else None
        base = f"{fmt(bb['riesgo_medio'])} | {fmt(bb['tasa_observada'])} |" if bb else "— | — |"
        out.append(f"| {fila['decil']} | {fmt(fila['riesgo_medio'])} | {fmt(fila['tasa_observada'])} | {miles(fila['n'])} | {base}")
    return out


def _etq_grupo(nivel: str, f: Dict) -> str:
    if nivel == "facultad":
        return f["grupo"]                                  # the faculty NAME (stage B)
    return f"{f['grupo']} · {f.get('nombre', '')}".strip(" ·")


def tabla_grupos(grupos: Dict, nivel: str) -> List[str]:
    filas = grupos[nivel]["filas"]
    if not filas:
        return ["No hay grupos que cumplan los umbrales (n ≥ 100 y ≥ 10 eventos)."]
    out = ["| " + ("Programa" if nivel == "programa" else "Facultad") + " | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |",
           "|---|---|---|---|---|---|---|---|---|"]
    for f in sorted(filas, key=lambda r: -r["tasa_observada"]["punto"]):
        out.append(f"| {_etq_grupo(nivel, f)} | {miles(f['n'])} | {miles(f['eventos'])} | {coma(con_ic(f['tasa_observada']))} | "
                   f"{coma(con_ic(f['riesgo_medio']))} | {coma(con_ic(f['brecha']))} | {coma(con_ic(f['brecha_base']))} | "
                   f"{fmt(f['ap'])} | {fmt(f['roc_auc'])} |")
    return out


def tabla_grupos_resumen(res: Dict, clave: str = "grupos") -> List[str]:
    out = ["| Tarea | k | Nivel | Grupos (total / reportables) | Filas en grupos reportables | Eventos en grupos reportables | Error absoluto medio ponderado del modelo | … de la tasa histórica | Diferencia | ρ de Spearman (pred. vs obs.) |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for tgt in ("T4", "T5"):
        for k in res["ks"]:
            for nivel in ("programa", "facultad"):
                r = res["por_k"][str(k)]["targets"][tgt][clave][nivel]["resumen"]
                if r["grupos_reportables"] == 0:
                    out.append(f"| {tgt} | {k} | {nivel} | {r['grupos_total']} / 0 | — | — | — | — | — | — |")
                    continue
                sp = "—" if r["spearman_modelo"]["punto"] != r["spearman_modelo"]["punto"] or r["grupos_reportables"] < 5 else coma(con_ic(r["spearman_modelo"], 2))
                out.append(f"| {tgt} | {k} | {nivel} | {r['grupos_total']} / {r['grupos_reportables']} | {miles(r['filas_en_reportables'])} de {miles(r['filas_total'])} ({pct(r['filas_en_reportables'] / r['filas_total'], 0)}) | "
                           f"{miles(r['eventos_en_reportables'])} de {miles(r['eventos_total'])} | {coma(con_ic(r['mae_modelo'], 4))} | {coma(con_ic(r['mae_base'], 4))} | "
                           f"{coma(con_ic(r['mae_modelo_menos_base'], 4))} | {sp} |")
    return out


def tabla_ranking(grupos: Dict, nivel: str, nombres: Dict[str, str]) -> List[str]:
    r = grupos[nivel]["resumen"].get("ranking")
    if not r:
        return ["No hay grupos reportables."]
    etq = (lambda g: g) if nivel == "facultad" else (lambda g: f"{g} · {nombres.get(g, '')}".strip(" ·"))
    out = ["| Posición | Mayor tasa observada | Mayor riesgo predicho | Menor tasa observada | Menor riesgo predicho |", "|---|---|---|---|---|"]
    for i in range(r["tamano"]):
        out.append(f"| {i + 1} | " + " | ".join(etq(r[c][i]) for c in ("top_observado", "top_predicho", "bottom_observado", "bottom_predicho")) + " |")
    c = grupos[nivel]["resumen"]["coincidencia_top"]
    out.append(f"\nCoincidencia entre los {c['k']} grupos de mayor tasa observada y los {c['k']} de mayor riesgo predicho: {c['n']}.")
    return out


def tabla_multiclase(ev: Dict, k: str) -> List[str]:
    mc = ev["multiclase"]
    ms = [m for m in ("mc_base", "mc_lr_agg", "mc_cb_agg") if m in mc["test"]]
    clases = ["transicion", "eliminacion", "continua", "otra_salida", "egreso"]
    out = ["| Modelo | Log-loss | Brier multiclase | AP macro | " + " | ".join(f"AP {RESULTADO[c].split(' (')[0].lower()}" for c in clases) + " |",
           "|---|---|---|---|" + "---|" * len(clases)]
    for m in ms:
        t = mc["test"][m]
        celdas = [("—" if t[f"ap_{c}"]["punto"] != t[f"ap_{c}"]["punto"] else coma(con_ic(t[f"ap_{c}"]))) for c in clases]
        out.append(f"| {nombre_modelo(m)} | {coma(con_ic(t['logloss'], 4))} | {coma(con_ic(t['brier_mc'], 4))} | {coma(con_ic(t['ap_macro']))} | " + " | ".join(celdas) + " |")
    n = mc["n_clase_test"]
    out.append("\nEventos en test: " + ", ".join(f"{RESULTADO[c].split(' (')[0].lower()} {n_pub(n[c])}" for c in clases) + ".")
    return out


def tabla_multiclase_deltas(ev: Dict) -> List[str]:
    t = ev["multiclase"]["test"]
    out = ["| Diferencia pareada (test) | Δ log-loss | Δ AP macro | Δ AP transición | Δ AP eliminación |", "|---|---|---|---|---|"]
    for p in [k for k in t if "__vs__" in k]:
        a, b = p.split("__vs__")
        out.append(f"| {nombre_modelo(a)} − {nombre_modelo(b)} | {coma(con_ic(t[p]['logloss'], 4))} | {coma(con_ic(t[p]['ap_macro']))} | "
                   f"{coma(con_ic(t[p]['ap_transicion']))} | {coma(con_ic(t[p]['ap_eliminacion']))} |")
    return out


def tabla_sexo(ev: Dict, tgt: str) -> List[str]:
    sub = ev["targets"][tgt]["subgrupos_test"]["sexo"]
    out = ["| Sexo | n | Tasa observada | Riesgo medio | Brecha (pred. − obs.) | AP | ROC-AUC | Recall@10 % | ECE |", "|---|---|---|---|---|---|---|---|---|"]
    for f in sub:
        out.append(f"| {f['grupo']} | {miles(f['n'])} | {fmt(f['tasa_observada'])} | {fmt(f['riesgo_medio'])} | {fmt(f['brecha_calibracion'], 3, True)} | "
                   f"{fmt(f['ap'])} | {fmt(f['roc_auc'])} | {fmt(f['recall_10'])} | {fmt(f['ece'], 4)} |")
    b = ev["targets"][tgt]["brecha_sexo"]
    if b:
        out.append(f"\nBrechas F − M: tasa observada {fmt(b['tasa_observada'], 3, True)}, riesgo medio {fmt(b['riesgo_medio'], 3, True)}, "
                   f"AP {fmt(b['ap'], 3, True)}, Recall@10 % {fmt(b['recall_10'], 3, True)}, brecha de calibración {fmt(b['brecha_calibracion'], 3, True)}.")
    return out


def tabla_cohorte(ev: Dict, tgt: str, g: str = "cohorte") -> List[str]:
    sub = ev["targets"][tgt]["subgrupos_test"][g]
    out = ["| Grupo | n | Tasa observada | Riesgo medio | Brecha | AP | ROC-AUC |", "|---|---|---|---|---|---|---|"]
    for f in sub:
        out.append(f"| {f['grupo']} | {miles(f['n'])} | {fmt(f['tasa_observada'])} | {fmt(f['riesgo_medio'])} | {fmt(f['brecha_calibracion'], 3, True)} | "
                   f"{fmt(f['ap'])} | {fmt(f['roc_auc'])} |")
    return out


def tabla_tiempos(res: Dict) -> List[str]:
    out = ["| k | Tarea | " + " | ".join(nombre_modelo(m) for m in ORDEN[1:]) + " |", "|---|---|" + "---|" * (len(ORDEN) - 1)]
    for k in res["ks"]:
        for tgt in ("T4", "T5"):
            t = res["tiempos_s"][str(k)][tgt]
            out.append(f"| {k} | {tgt} | " + " | ".join(f"{t.get(m, 0):.0f} s" for m in ORDEN[1:]) + " |")
        mc = res["tiempos_s"][str(k)]["multiclase"]
        out.append(f"| {k} | multiclase | logística {mc['mc_lr_agg']:.0f} s · CatBoost {mc['mc_cb_agg']:.0f} s | | | | | |")
    return out


def tabla_causales(res: Dict) -> List[str]:
    c = res["causales_eliminacion"]
    tot = sum(x["n"] for x in c)
    out = ["| Código de causal del estado E | Filas de eliminación (T5, train + valid + test) | Proporción |", "|---|---|---|"]
    for x in c:
        out.append(f"| {x['causal']} | {miles(x['n'])} | {pct(x['n'] / tot)} |")
    return out


def tabla_registro_e(res: Dict) -> List[str]:
    out = ["| Período | Estados E | Estados de matrícula (M, N, J) | E por cada 1.000 matrículas |", "|---|---|---|---|"]
    for r in res["registro_e"]:
        if r["periodo"] > res["periodo_cierre"]:
            continue
        tasa = 1000 * r["e"] / r["matriculados"] if r["matriculados"] else float("nan")
        out.append(f"| {r['periodo']} | {n_pub(r['e'])} | {miles(r['matriculados'])} | {fmt(tasa, 1)} |")
    return out


def tabla_sensibilidad_e(res: Dict, tgt: str = "T5") -> List[str]:
    """Evaluation (c): test rows whose horizon does not touch the doubtful recording of E (``horizonte_e_dudoso`` False)."""
    out = ["| k | Modelo conservado | Filas de test sin horizonte dudoso | Filas excluidas | Eventos | Tasa observada | Riesgo medio | AP (conservado) | AP (tasa histórica) | ΔAP pareado | ECE (conservado) |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in res["ks"]:
        t5 = res["por_k"][str(k)]["targets"][tgt]
        s = t5["sensibilidad_registro_e"]
        if not s.get("evaluado"):
            out.append(f"| {k} | — | {miles(s['n'])} de {miles(s['n_total_test'])} | {miles(s['n_excluidas'])} | {n_pub(s['eventos'])} | no evaluable (menos de 100 filas o 10 eventos) | | | | | |")
            continue
        c = t5["seleccion"]["conservado"]
        m, b = s["modelos"][c], s["modelos"]["baseline_tasa"]
        out.append(f"| {k} | {nombre_modelo(c)} | {miles(s['n'])} de {miles(s['n_total_test'])} | {miles(s['n_excluidas'])} | {miles(s['eventos'])} | {fmt(s['tasa_observada'])} | "
                   f"{fmt(m['riesgo_medio'])} | {coma(con_ic(m['ap']))} | {coma(con_ic(b['ap']))} | {coma(con_ic(s['delta_ap_vs_base']))} | {coma(con_ic(m['ece'], 4))} |")
    return out


def tabla_tres_evaluaciones(res: Dict) -> List[str]:
    """T5 evaluated three ways on test: (a) the current label, (b) the elimination without reintegro, (c) (a) without the rows
    whose horizon touches the doubtful recording of E. Each with its 95 % interval and the paired AP difference vs the baseline."""
    out = ["| k | Evaluación | Modelo conservado | Filas | Eventos | Tasa observada | AP | ROC-AUC | Brier | ECE | AP tasa histórica | ΔAP pareado vs tasa histórica |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in res["ks"]:
        ev = res["por_k"][str(k)]["targets"]
        for etq, tgt in (("(a) etiqueta actual: eliminación", "T5"), ("(b) eliminación efectiva (sin reintegro)", "T5E")):
            if tgt not in ev:
                continue
            t = ev[tgt]
            c = t["seleccion"]["conservado"]
            m, b = t["test"][c], t["test"]["baseline_tasa"]
            par = t["test"].get(f"{c}__vs__baseline_tasa", {}).get("ap") if c != "baseline_tasa" else None
            if par is None:                      # the kept model may be a network: the stored pairs are against other models
                par = {"punto": m["ap"]["punto"] - b["ap"]["punto"], "lo": float("nan"), "hi": float("nan")}
            n = t["n"]["test"]
            out.append(f"| {k} | {etq} | {nombre_modelo(c)} | {miles(n['n'])} | {miles(n['eventos'])} | {fmt(n['tasa'])} | {coma(con_ic(m['ap']))} | "
                       f"{coma(con_ic(m['roc_auc']))} | {coma(con_ic(m['brier'], 4))} | {coma(con_ic(m['ece'], 4))} | {coma(con_ic(b['ap']))} | {coma(con_ic(par))} |")
        for etq, tgt in (("(c) etiqueta actual sin horizontes dudosos", "T5"),):
            t = ev[tgt]
            s = t["sensibilidad_registro_e"]
            if not s.get("evaluado"):
                out.append(f"| {k} | {etq} | — | {miles(s['n'])} | {n_pub(s['eventos'])} | no evaluable (menos de 100 filas o 10 eventos) | | | | | | |")
                continue
            c = t["seleccion"]["conservado"]
            m, b = s["modelos"][c], s["modelos"]["baseline_tasa"]
            out.append(f"| {k} | {etq} | {nombre_modelo(c)} | {miles(s['n'])} | {miles(s['eventos'])} | {fmt(s['tasa_observada'])} | {coma(con_ic(m['ap']))} | "
                       f"{coma(con_ic(m['roc_auc']))} | {coma(con_ic(m['brier'], 4))} | {coma(con_ic(m['ece'], 4))} | {coma(con_ic(b['ap']))} | {coma(con_ic(s['delta_ap_vs_base']))} |")
    return out


def conservado_ap(res: Dict, k, tgt: str):
    t = res["por_k"][str(k)]["targets"][tgt]
    c = t["seleccion"]["conservado"]
    return c, t["test"][c]["ap"], t["test"][c]["roc_auc"]


def tabla_cambios(res: Dict) -> List[str]:
    """Before / after of the stage B rebuild: kept model and test metrics of T4 and T5, and the label counts."""
    prev = CB.cargar_previo("resultados_t45")
    if prev is None:
        return CB.sin_previo()
    out = ["| Tarea y corte | Modelo conservado (antes → después) | AP de test antes | AP de test después | ROC-AUC antes | ROC-AUC después | Cambio de AP |",
           "|---|---|---|---|---|---|---|"]
    for tgt in ("T4", "T5"):
        for k in res["ks"]:
            k = str(k)
            tp, tn = prev["por_k"][k]["targets"][tgt], res["por_k"][k]["targets"][tgt]
            cp, cn = tp["seleccion"]["conservado"], tn["seleccion"]["conservado"]
            a, b = tp["test"][cp], tn["test"][cn]
            out.append(f"| {tgt} k = {k} | {nombre_modelo(cp)} → {nombre_modelo(cn)} | {CB.celda(a['ap'])} | {CB.celda(b['ap'])} | "
                       f"{CB.celda(a['roc_auc'])} | {CB.celda(b['roc_auc'])} | {CB.delta(a['ap'], b['ap'])} |")
    return out


def tabla_etiquetas_p71(res: Dict) -> List[str]:
    """T4 label counts before and after dating the transfer at the exit from the origin program (P71)."""
    import json as _json
    p = CB.PREVIO / "etiquetas_t45_antes.json"
    if not p.exists():
        return CB.sin_previo()
    antes = {(r[0], r[1], r[2]): int(r[3]) for r in _json.loads(p.read_text(encoding="utf-8"))["cuentas"]}
    out = ["| k | Partición | Transiciones (T4) antes | Transiciones (T4) después | Otra salida antes | Otra salida después | Continúa antes | Continúa después |",
           "|---|---|---|---|---|---|---|---|"]
    c = res["descriptivo"]["cuentas"]
    for k in ("2", "4"):
        for s in ("train", "valid", "test"):
            d = c.get(k, {}).get(s)
            if not d:
                continue
            out.append(f"| {k} | {s} | {miles(antes.get((k, s, 'transicion'), 0))} | {miles(d.get('transicion', 0))} | "
                       f"{miles(antes.get((k, s, 'otra_salida'), 0))} | {miles(d.get('otra_salida', 0))} | "
                       f"{miles(antes.get((k, s, 'continua'), 0))} | {miles(d.get('continua', 0))} |")
    return out


def bloques(res: Dict) -> Dict[str, str]:
    nl = "\n"
    nombres = {}
    for k in res["ks"]:
        for tgt in ("T4", "T5"):
            for clave in ("grupos", "grupos_valid_test"):
                for f in res["por_k"][str(k)]["targets"][tgt][clave]["programa"]["filas"]:
                    nombres[f["grupo"]] = f.get("nombre", "")
    b: Dict[str, str] = {
        "embudo": nl.join(tabla_embudo(res)), "resultados": nl.join(tabla_resultados(res)),
        "otra_salida": nl.join(tabla_otra_salida(res)), "seleccion": nl.join(tabla_seleccion(res)),
        "grupos_resumen": nl.join(tabla_grupos_resumen(res)), "grupos_resumen_vt": nl.join(tabla_grupos_resumen(res, "grupos_valid_test")),
        "tiempos": nl.join(tabla_tiempos(res)), "causales": nl.join(tabla_causales(res)),
        "registro_e": nl.join(tabla_registro_e(res)), "sensibilidad_e": nl.join(tabla_sensibilidad_e(res)),
        "sensibilidad_e_efectiva": nl.join(tabla_sensibilidad_e(res, "T5E")), "tres_evaluaciones": nl.join(tabla_tres_evaluaciones(res)),
        "cambios": nl.join(tabla_cambios(res)), "etiquetas_p71": nl.join(tabla_etiquetas_p71(res)),
    }
    for k in res["ks"]:
        k = str(k)
        ev = res["por_k"][k]
        b[f"multiclase.{k}"] = nl.join(tabla_multiclase(ev, k))
        b[f"multiclase_deltas.{k}"] = nl.join(tabla_multiclase_deltas(ev))
        for tgt in ("T4", "T5", "T5E"):
            if tgt not in ev["targets"]:
                continue
            b[f"test.{tgt}.{k}"] = nl.join(tabla_metricas(ev, tgt, k, "test"))
            b[f"valid.{tgt}.{k}"] = nl.join(tabla_metricas(ev, tgt, k, "valid"))
            b[f"deltas.{tgt}.{k}"] = nl.join(tabla_deltas(ev, tgt))
            b[f"calibracion.{tgt}.{k}"] = nl.join(tabla_calibracion(ev, tgt))
            b[f"sexo.{tgt}.{k}"] = nl.join(tabla_sexo(ev, tgt))
            b[f"cohorte.{tgt}.{k}"] = nl.join(tabla_cohorte(ev, tgt, "cohorte"))
            b[f"plan_comun.{tgt}.{k}"] = nl.join(tabla_cohorte(ev, tgt, "plan_comun"))
            for clave, pref in (("grupos", "g"), ("grupos_valid_test", "gvt")):
                for nivel in ("programa", "facultad"):
                    g = ev["targets"][tgt][clave]
                    b[f"{pref}.{tgt}.{k}.{nivel}"] = nl.join(tabla_grupos(g, nivel))
                    b[f"ranking.{pref}.{tgt}.{k}.{nivel}"] = nl.join(tabla_ranking(g, nivel, nombres))
    return b


def _ruta(res: Dict, ruta: str):
    x = res
    for p in ruta.split("."):
        x = x[int(p)] if isinstance(x, list) else x[p]
    return x


def _valor(res: Dict, ruta: str, tipo: str) -> str:
    if tipo == "d":
        k, tgt, a, b, metrica = ruta.split(".")
        m = res["por_k"][k]["targets"][tgt]["test"][f"{a}__vs__{b}"][metrica]
    elif tipo == "mc":
        k, modelo, metrica = ruta.split(".")
        m = res["por_k"][k]["multiclase"]["test"][modelo][metrica]
    else:
        k, tgt, modelo, metrica = ruta.split(".")
        m = res["por_k"][k]["targets"][tgt]["test"][modelo][metrica]
    d = dec(metrica)
    return coma(con_ic(m, d) if tipo in ("ic", "d", "mc") else f"{m['punto']:.{d}f}")


def documento() -> str:
    res = json.loads((ART / "resultados_t45.json").read_text(encoding="utf-8"))
    blq = bloques(res)
    plantilla = (RAIZ / "tools" / "plantilla_t45.md").read_text(encoding="utf-8")

    def sustituir(m) -> str:
        clave = m.group(1)
        tipo, _, ruta = clave.partition(":")
        if tipo == "meta":
            return {"snapshot_hash": res["snapshot_hash"], "version_codigo": res["version_codigo"],
                    "ram": f"{res['ram_pico_mb']:.0f}", "segundos": f"{res['segundos_totales']:.0f}",
                    "minutos": f"{res['segundos_totales'] / 60:.0f}", "cierre": res["periodo_cierre"], "gpu": str(res.get("gpu")),
                    "boot": str(res["n_boot"])}[ruta]
        if tipo == "tabla":
            return blq[ruta]
        if tipo == "x":
            v = _ruta(res, ruta)
            return coma(f"{v:.3f}") if isinstance(v, float) else miles(v) if isinstance(v, int) else str(v)
        if tipo == "pct":
            return pct(float(_ruta(res, ruta)))
        if tipo == "n":
            return n_pub(int(_ruta(res, ruta)))
        if tipo == "tasa":
            k, split, resultado = ruta.split(".")
            c = res["descriptivo"]["cuentas"][k][split]
            return pct(c.get(resultado, 0) / sum(c.values()))
        if tipo == "sens":
            k, metrica = ruta.split(".")
            t5 = res["por_k"][k]["targets"]["T5"]
            return coma(con_ic(t5["sensibilidad_registro_e"]["modelos"][t5["seleccion"]["conservado"]][metrica], dec(metrica)))
        if tipo in ("v", "ic", "d", "mc"):
            return _valor(res, ruta, tipo)
        raise KeyError(clave)

    return re.sub(r"\{\{([^}]+)\}\}", sustituir, plantilla)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["--doc"]:
        (RAIZ / "docs" / "11_benchmark_t4_t5.md").write_text(documento(), encoding="utf-8")
        print("escrito docs/11_benchmark_t4_t5.md")
        return 0
    res = json.loads((ART / "resultados_t45.json").read_text(encoding="utf-8"))
    for nombre, texto in bloques(res).items():
        print(f"\n<!--{{{{tabla:{nombre}}}}}-->\n{texto}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
