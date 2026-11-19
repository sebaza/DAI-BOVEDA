"""Render docs/09_benchmark_t2.md from the gitignored aggregate JSON (``artefactos/resultados_t2.json``).

``python tools/informe_t2.py --doc`` assembles the document from ``tools/plantilla_t2.md`` (hand-written text) and the
tables built here. Markers in the template: ``{{tabla:NOMBRE}}`` (a named block), ``{{v:split.modelo.metrica}}`` (point
value, Spanish decimal comma), ``{{ic:split.modelo.metrica}}`` (point and 95 % interval), ``{{d:split.a.b.metrica}}``
(paired difference a - b with interval), ``{{meta:snapshot_hash|version_codigo}}``. Aggregates only.
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

NOMBRES = {
    "baseline": "Tasa histórica del curso (expansiva)",
    "lr_a": "Logística (a) estudiante + carga", "lr_b": "Logística (b) + curso", "lr_c": "Logística (c) + prerrequisitos",
    "lr_d": "Logística (d) + docente",
    "cb_a": "CatBoost (a) estudiante + carga", "cb_b": "CatBoost (b) + curso", "cb_c": "CatBoost (c) + prerrequisitos",
    "cb_d": "CatBoost (d) + docente", "cb_c_id": "CatBoost (c) + identidad del curso",
    "cb_cemb": "CatBoost (d') (c) + embeddings GraphSAGE",
    "nn_gnn": "Red extremo a extremo, GraphSAGE (prerreq. + coinscripción)",
    "nn_gnn_prereq": "Red extremo a extremo, GraphSAGE (solo prerreq.)",
    "nn_mlp": "Red extremo a extremo, atributos del curso sin grafo",
    "nn_ninguno": "Red extremo a extremo, sin representación del curso",
    "cb_c_decay": "CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55)",
    "cb_c_vent": "CatBoost (c) con estadísticas del curso en ventana reciente (P55)",
}
ORDEN = list(NOMBRES)
ETIQ_METRICA = {"ap": "AP (reprobación)", "ap_aprob": "AP (aprobación)", "roc_auc": "ROC-AUC", "brier": "Brier",
                "ece": "ECE", "recall_at_1": "Recall@1", "precision_at_1": "Precision@1", "recall_at_2": "Recall@2",
                "precision_at_2": "Precision@2"}


def miles(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def coma(t: str) -> str:
    return t.replace(".", ",")


def miles_x(n) -> str:
    """Thousands with a sentinel so ``coma_m`` can turn the decimal points into commas without touching the thousands dots."""
    return miles(n).replace(".", "\x00")


def coma_m(t: str) -> str:
    return t.replace(".", ",").replace("\x00", ".")


def con_ic(d: Dict[str, float], dec: int = 3) -> str:
    return f"{d['punto']:.{dec}f} [{d['lo']:.{dec}f}; {d['hi']:.{dec}f}]"


def dec(m: str) -> int:
    return 4 if m == "brier" else 3


def modelos_en(ev: Dict, split: str) -> List[str]:
    return [m for m in ORDEN if m in ev[split]]


def tabla_modelos(ev: Dict, split: str) -> List[str]:
    out = ["| Modelo | AP reprobación | AP aprobación | ROC-AUC | Brier | ECE |", "|---|---|---|---|---|---|"]
    for m in modelos_en(ev, split):
        r = ev[split][m]
        out.append(f"| {NOMBRES[m]} | {con_ic(r['ap'])} | {con_ic(r['ap_aprob'])} | {con_ic(r['roc_auc'])} | "
                   f"{con_ic(r['brier'], 4)} | {con_ic(r['ece'])} |")
    return out


def tabla_ranking(ev: Dict, split: str) -> List[str]:
    out = ["| Modelo | Recall@1 | Precision@1 | Recall@2 | Precision@2 |", "|---|---|---|---|---|"]
    az = ev[split]["__azar"]
    out.append(f"| Orden al azar (esperado, forma cerrada) | {az['recall_at_1']:.3f} | {az['precision_at_1']:.3f} | "
               f"{az['recall_at_2']:.3f} | {az['precision_at_2']:.3f} |")
    for m in modelos_en(ev, split):
        r = ev[split][m]
        out.append(f"| {NOMBRES[m]} | {con_ic(r['recall_at_1'])} | {con_ic(r['precision_at_1'])} | "
                   f"{con_ic(r['recall_at_2'])} | {con_ic(r['precision_at_2'])} |")
    return out


def tabla_deltas(ev: Dict, split: str, pares: List[List[str]]) -> List[str]:
    out = ["| Comparación (A − B, diferencia pareada) | ΔAP reprobación | ΔAP aprobación | ΔROC-AUC | ΔBrier | ΔRecall@1 |",
           "|---|---|---|---|---|---|"]
    for a, b in pares:
        d = ev[split].get(f"__delta__{a}__{b}")
        if d:
            out.append(f"| {NOMBRES[a]} − {NOMBRES[b]} | {con_ic(d['ap'])} | {con_ic(d['ap_aprob'])} | "
                       f"{con_ic(d['roc_auc'])} | {con_ic(d['brier'], 4)} | {con_ic(d['recall_at_1'])} |")
    return out


def tabla_ablacion(ev: Dict, split: str) -> List[str]:
    t = ev[split]
    out = ["| Escalón | Logística AP | CatBoost AP | Logística ROC-AUC | CatBoost ROC-AUC | CatBoost Recall@1 |",
           "|---|---|---|---|---|---|"]
    filas = [("0. Tasa histórica del curso", "baseline", "baseline"), ("a. Estudiante + carga", "lr_a", "cb_a"),
             ("b. + estadística del curso", "lr_b", "cb_b"), ("c. + prerrequisitos explícitos", "lr_c", "cb_c"),
             ("d. + historial de sección/docente (2016+)", "lr_d", "cb_d")]
    for nombre, lr, cb in filas:
        l_ap = con_ic(t[lr]["ap"]) if lr in t else "—"
        c_ap = con_ic(t[cb]["ap"]) if cb in t else "—"
        l_au = con_ic(t[lr]["roc_auc"]) if lr in t else "—"
        c_au = con_ic(t[cb]["roc_auc"]) if cb in t else "—"
        rec = con_ic(t[cb]["recall_at_1"]) if cb in t else "—"
        out.append(f"| {nombre} | {l_ap} | {c_ap} | {l_au} | {c_au} | {rec} |")
    return out


def tabla_grafo(ev: Dict, split: str) -> List[str]:
    t = ev[split]
    claves = ["baseline", "cb_b", "cb_c", "cb_c_id", "cb_cemb", "nn_ninguno", "nn_mlp", "nn_gnn_prereq", "nn_gnn"]
    out = ["| Modelo | AP reprobación | ROC-AUC | Brier | Recall@1 |", "|---|---|---|---|---|"]
    for m in claves:
        if m in t:
            r = t[m]
            out.append(f"| {NOMBRES[m]} | {con_ic(r['ap'])} | {con_ic(r['roc_auc'])} | {con_ic(r['brier'], 4)} | "
                       f"{con_ic(r['recall_at_1'])} |")
    return out


def tabla_semillas(res: Dict) -> List[str]:
    out = ["| Red (3 semillas) | AP valid (media ± sd) | AP test (media ± sd) | Épocas óptimas | Tiempo total (s) |",
           "|---|---|---|---|---|"]
    import statistics as st
    for m, runs in res["semillas"].items():
        v = [r["valid"]["ap"] for r in runs]
        t = [r["test"]["ap"] for r in runs]
        ep = [s["mejor_epoca"] for s in res["info"][m]["semillas"]]
        sd = lambda x: st.stdev(x) if len(x) > 1 else 0.0
        out.append(f"| {NOMBRES[m]} | {st.mean(v):.3f} ± {sd(v):.3f} | {st.mean(t):.3f} ± {sd(t):.3f} | {ep} | "
                   f"{res['tiempos_s'][m]:.0f} |")
    return out


def tabla_calibracion(ev: Dict, modelos: List[str]) -> List[str]:
    out = ["| Decil de riesgo | " + " | ".join(f"{NOMBRES[m]}: predicho / observado" for m in modelos) + " |",
           "|---|" + "---|" * len(modelos)]
    for i in range(10):
        celdas = []
        for m in modelos:
            r = next((x for x in ev["calibracion_test"][m] if x["decil"] == i + 1), None)
            celdas.append(f"{r['riesgo_medio']:.3f} / {r['tasa_observada']:.3f}" if r else "—")
        out.append(f"| {i + 1} | " + " | ".join(celdas) + " |")
    return out


def nombres_programa() -> Dict[str, str]:
    try:
        sys.path.insert(0, str(RAIZ))
        from pipelines.common.db import dev_connection

        with dev_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT cod_programa, nombre_programa FROM neural_core.programa")
            return {c: (n or "") for c, n in cur.fetchall()}
    except Exception:
        return {}


def tabla_grupo(ev: Dict, modelos: List[str], grupo: str, limite: int = 60, nombres: Dict[str, str] = None) -> List[str]:
    nombres = nombres or {}
    cab = "| Grupo | n | Tasa reprobación observada |" + "".join(f" {m}: riesgo / AP |" for m in modelos)
    out = [cab, "|---|---|---|" + "---|" * len(modelos)]
    base = ev["subgrupos_test"][modelos[0]][grupo]
    por = {m: {r["grupo"]: r for r in ev["subgrupos_test"][m][grupo]} for m in modelos}
    for r in base[:limite]:
        et = f"{r['grupo']} {nombres.get(r['grupo'], '')}".strip() if grupo == "programa" else r["grupo"]
        celdas = []
        for m in modelos:
            x = por[m].get(r["grupo"])
            ap = "—" if x is None or x["ap"] != x["ap"] else f"{x['ap']:.3f}"
            celdas.append(f"{x['riesgo_medio']:.3f} / {ap}" if x else "—")
        out.append(f"| {et} | {miles(r['n'])} | {r['tasa_observada']:.3f} | " + " | ".join(celdas) + " |")
    return out


def tabla_sexo(ev: Dict, modelos: List[str]) -> List[str]:
    out = ["| Modelo | Tasa F | Tasa M | Riesgo medio F | Riesgo medio M | AP F | AP M | ΔAP (F−M) | Brecha calibración F | Brecha calibración M |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for m in modelos:
        t = {r["grupo"]: r for r in ev["subgrupos_test"][m]["sexo"]}
        if "F" not in t or "M" not in t:
            continue
        f, h = t["F"], t["M"]
        out.append(f"| {NOMBRES[m]} | {f['tasa_observada']:.3f} | {h['tasa_observada']:.3f} | {f['riesgo_medio']:.3f} | "
                   f"{h['riesgo_medio']:.3f} | {f['ap']:.3f} | {h['ap']:.3f} | {f['ap'] - h['ap']:+.3f} | "
                   f"{f['brecha_calibracion']:+.3f} | {h['brecha_calibracion']:+.3f} |")
    return out


def tabla_tiempos(res: Dict) -> List[str]:
    out = ["| Modelo | Tiempo de entrenamiento (s) | Notas |", "|---|---|---|"]
    for m in ORDEN:
        if m not in res["tiempos_s"]:
            continue
        i = res["info"].get(m, {})
        nota = ""
        if m.startswith("nn_"):
            r = i["semillas"]
            nota = (f"{r[0]['n_parametros']} parámetros; pico de memoria GPU {i['gpu_pico_mb']:.0f} MB; "
                    f"épocas óptimas {[s['mejor_epoca'] for s in r]}")
        elif m.startswith("cb_"):
            nota = f"3 semillas; iteraciones óptimas {i.get('mejores_iteraciones')}"
        elif m.startswith("lr_"):
            nota = f"C = {i['C']}; {i['n_variables']} columnas"
        out.append(f"| {NOMBRES[m]} | {res['tiempos_s'][m]:.0f} | {nota} |")
    return out


def tabla_embudo(res: Dict) -> List[str]:
    out = ["| Paso | Intentos |", "|---|---|"]
    for e in res["embudo"]:
        out.append(f"| {e['paso']} | {miles(e['n'])} |")
    return out


def tabla_split(res: Dict) -> List[str]:
    d = res["descriptivo"]["split"]
    out = ["| Partición | Períodos | Intentos | Reprobados | Tasa de reprobación | Personas | Cursos | Grupos (persona, período) |",
           "|---|---|---|---|---|---|---|---|"]
    per = {"train": "2015-10 a 2020-20", "valid": "2021-10 a 2022-20", "test": "2023-10 a 2024-20",
           "posterior": "2025-10 a 2025-20"}
    for s in ("train", "valid", "test", "posterior"):
        v = d[s]
        out.append(f"| {s} | {per[s]} | {miles(v['n'])} | {miles(v['reprobados'])} | {100 * v['tasa_reprobacion']:.1f} % | "
                   f"{miles(v['personas'])} | {miles(v['cursos'])} | {miles(v['grupos_persona_periodo'])} |")
    return out


def tabla_cobertura(res: Dict) -> List[str]:
    c = res["descriptivo"]["cobertura"]
    filas = [("Curso en la malla oficial del estudiante (programa + catálogo)", "en_malla"),
             ("Programa + catálogo presente en la malla", "malla_conocida"),
             ("Con información de prerrequisitos (curso en malla y catálogo con aristas)", "info_prereq"),
             ("Curso con al menos un prerrequisito (sobre todas las filas)", "con_prerrequisitos"),
             ("Curso con al menos un prerrequisito (sobre filas con información)", "con_prerrequisitos_entre_info"),
             ("Sección con docente en la oferta (2016+)", "tiene_docente"),
             ("Curso con historia previa (n_hist_curso > 0)", "con_historia_curso"),
             ("Intento repetido (el estudiante ya cursó el curso)", "repetido"),
             ("Oportunidad > 1 (campo de la fuente)", "oportunidad_mayor_1")]
    out = ["| Cobertura (fracción de intentos) | train | valid | test | posterior |", "|---|---|---|---|---|"]
    for nombre, k in filas:
        out.append(f"| {nombre} | " + " | ".join(coma(f"{100 * c[s][k]:.1f} %") for s in ("train", "valid", "test", "posterior")) + " |")
    return out


def tabla_periodos(res: Dict) -> List[str]:
    out = ["| Período | Intentos | Tasa de reprobación |", "|---|---|---|"]
    for p, v in sorted(res["descriptivo"]["por_periodo"].items()):
        out.append(f"| {p} | {miles(v['n'])} | {100 * v['tasa_reprobacion']:.1f} % |")
    return out


def tabla_oportunidad(res: Dict) -> List[str]:
    d = res["descriptivo"]["por_oportunidad"]
    out = ["| Partición | Oportunidad 1 | Oportunidad 2 | Oportunidad 3+ |", "|---|---|---|---|"]
    for s in ("train", "valid", "test", "posterior"):
        cel = []
        for o in (1, 2, 3):
            v = d.get(f"{s}|{o}")
            cel.append(f"{miles(v['n'])} ({100 * v['tasa_reprobacion']:.1f} %)" if v else "—")
        out.append(f"| {s} | " + " | ".join(cel) + " |")
    return out


def tabla_enlaces(res: Dict) -> List[str]:
    g = res["info"]["grafo"]
    out = ["| Semilla | AP enlaces retenidos | ROC-AUC enlaces retenidos | AP línea base por grado | ROC-AUC línea base por grado |",
           "|---|---|---|---|---|"]
    for i, e in enumerate(g["enlaces"]):
        out.append(f"| {i} | {e['ap_enlaces']:.3f} | {e['auc_enlaces']:.3f} | {e['ap_grado']:.3f} | {e['auc_grado']:.3f} |")
    return out


def tabla_importancia(res: Dict) -> List[str]:
    imp = res["info"]["cb_c"].get("importancia_top15", {})
    out = ["| Variable | Importancia (media de 3 semillas, % del total) |", "|---|---|"]
    for k, v in imp.items():
        out.append(f"| `{k}` | {v:.1f} |")
    return out


def tabla_ap_periodo(ev: Dict) -> List[str]:
    d = ev["ap_por_periodo_test"]
    ms = list(d)
    periodos = sorted(next(iter(d.values())))
    out = ["| Período (test) | " + " | ".join(NOMBRES[m] for m in ms) + " |", "|---|" + "---|" * len(ms)]
    for p in periodos:
        out.append(f"| {p} | " + " | ".join(f"{d[m][p]:.3f}" for m in ms) + " |")
    return out


BANDAS = ["reprobado", "unanimidad", "distincion", "maxima_distincion"]
ETQ_BANDA = {"reprobado": "Reprobado (< 4,0)", "unanimidad": "Aprobado por Unanimidad (4,0–5,3)",
             "distincion": "Aprobado con Distinción (5,4–6,3)", "maxima_distincion": "Aprobado con Máxima Distinción (6,4–7,0)"}
CORTA_BANDA = {"reprobado": "Reprobado", "unanimidad": "Unanimidad", "distincion": "Distinción", "maxima_distincion": "Máx. distinción"}


def pcti(d: Optional[Dict], dec_: int = 1) -> str:
    """A share with its interval as a percentage; ``None`` (suppressed cell) is a dash."""
    if d is None:
        return "—"
    return coma(f"{100 * d['punto']:.{dec_}f} % [{100 * d['lo']:.{dec_}f}; {100 * d['hi']:.{dec_}f}]")


def pp(d: Optional[Dict]) -> str:
    """A gap in percentage points with its interval."""
    if d is None:
        return "—"
    return coma(f"{100 * d['punto']:+.1f} [{100 * d['lo']:+.1f}; {100 * d['hi']:+.1f}]")


def tabla_bandas_distribucion(bd: Dict) -> List[str]:
    out = ["| Partición | Intentos | " + " | ".join(ETQ_BANDA[c] for c in BANDAS) + " |", "|---|---|" + "---|" * len(BANDAS)]
    for s in ("train", "valid", "test", "posterior"):
        d = bd["distribucion"].get(s)
        if d:
            out.append(f"| {s} | {miles(d['n'])} | " + " | ".join(coma(f"{100 * d[c]:.1f} %") for c in BANDAS) + " |")
    return out


def tabla_bandas_metricas(bd: Dict, split: str) -> List[str]:
    m = bd["metricas"][split]
    out = ["| Modelo | Log-loss | Brier multiclase | " + " | ".join(f"AP {CORTA_BANDA[c].lower()}" for c in BANDAS) + " | AP macro |",
           "|---|---|---|" + "---|" * (len(BANDAS) + 1)]
    for clave, nombre in (("cb_bandas", f"CatBoost multiclase (conjunto {bd['conjunto']})"), ("frecuencias", "Frecuencia de las bandas en train")):
        r = m[clave]
        out.append(f"| {nombre} | {con_ic(r['logloss'], 4)} | {con_ic(r['brier_mc'], 4)} | "
                   + " | ".join(con_ic(r[f"ap_{c}"]) for c in BANDAS) + f" | {con_ic(r['ap_macro'])} |")
    d = m["cb_bandas__vs__frecuencias"]
    out.append(f"| **Diferencia pareada (CatBoost − frecuencia)** | {con_ic(d['logloss'], 4)} | {con_ic(d['brier_mc'], 4)} | "
               + " | ".join(con_ic(d[f"ap_{c}"]) for c in BANDAS) + f" | {con_ic(d['ap_macro'])} |")
    return [coma(x) if x.startswith("|") else x for x in out]


def _fila_programa(f: Dict) -> str:
    cel = []
    for c in BANDAS:
        b = f["bandas"][c]
        if b["observada"] is None:
            cel.append("—")
        else:
            cel.append(f"{100 * b['observada']['punto']:.1f} / {100 * b['predicha']['punto']:.1f} ({100 * b['brecha']['punto']:+.1f})")
    nombre = f"{f['grupo']} · {f.get('nombre', '')}".strip(" ·")
    return coma_m(f"| {nombre} | {miles_x(f['n'])} | " + " | ".join(cel) + " |")


def tabla_bandas_programas(g: Dict) -> List[str]:
    t = g["programa"]
    out = ["| Programa | Intentos | " + " | ".join(f"{CORTA_BANDA[c]}: obs. / pred. (brecha, pp)" for c in BANDAS) + " |", "|---|---|" + "---|" * len(BANDAS)]
    out += [_fila_programa(f) for f in sorted(t["filas"], key=lambda r: -(r["bandas"]["reprobado"]["observada"] or {"punto": 0})["punto"])]
    return out


def tabla_bandas_facultad(g: Dict, banda: str) -> List[str]:
    out = [f"**{ETQ_BANDA[banda]}**", "", "| Facultad | Intentos | % observado | % esperado (modelo) | Brecha (pp, pred. − obs.) | Brecha de la frecuencia global (pp) |",
           "|---|---|---|---|---|---|"]
    for f in sorted(g["facultad"]["filas"], key=lambda r: -(r["bandas"][banda]["observada"] or {"punto": 0})["punto"]):
        b = f["bandas"][banda]
        out.append(f"| {f['grupo']} | {miles(f['n'])} | {pcti(b['observada'])} | {pcti(b['predicha'])} | {pp(b['brecha'])} | {pp(b['brecha_base'])} |")
    return out


def tabla_bandas_resumen(bd: Dict) -> List[str]:
    out = ["| Evaluación | Nivel | Grupos | ≥ 100 intentos (listados) | 10 a 99 (solo contados) | < 10 (suprimidos) | Intentos en listados | " + " | ".join(
        f"MAE {CORTA_BANDA[c].lower()}: modelo / frecuencia" for c in BANDAS) + " | " + " | ".join(f"ρ {CORTA_BANDA[c].lower()}" for c in BANDAS) + " |",
           "|---|---|---|---|---|---|---|" + "---|" * (2 * len(BANDAS))]
    for clave, etq in (("test", "test"), ("valid_test", "valid + test")):
        for nivel in ("programa", "facultad"):
            r = bd["grupos"][clave][nivel]["resumen"]
            mae = [f"{100 * r['mae_modelo'][c]['punto']:.2f} / {100 * r['mae_base'][c]['punto']:.2f} pp" if c in r["mae_modelo"] else "—" for c in BANDAS]
            sp = [f"{r['spearman'][c]['punto']:.2f}" if c in r["spearman"] else "—" for c in BANDAS]
            out.append(f"| {etq} | {nivel} | {r['grupos_total']} | {r['grupos_100_o_mas']} | {r['grupos_10_a_99']} | {r['grupos_menos_10']} | "
                       f"{miles_x(r['filas_en_listados'])} de {miles_x(r['filas_total'])} | " + " | ".join(mae) + " | " + " | ".join(sp) + " |")
    return [coma_m(x) for x in out]


def tabla_bandas_ranking(bd: Dict, nivel: str, nombres: Dict[str, str]) -> List[str]:
    r = bd["grupos"]["test"][nivel]["resumen"]["ranking"].get("reprobado")
    if not r:
        return ["No hay grupos listados."]
    etq = (lambda g: g) if nivel == "facultad" else (lambda g: f"{g} · {nombres.get(g, '')}".strip(" ·"))
    out = ["| Posición | Mayor % de reprobados observado | Mayor % esperado | Menor % observado | Menor % esperado |", "|---|---|---|---|---|"]
    for i in range(r["tamano"]):
        out.append(f"| {i + 1} | " + " | ".join(etq(r[c][i]) for c in ("top_observado", "top_predicho", "bottom_observado", "bottom_predicho")) + " |")
    return out


def _t45_grupo(r45: Optional[Dict], k: str, tgt: str, nivel: str, grupo: str) -> Optional[Dict]:
    if not r45:
        return None
    for f in r45["por_k"][k]["targets"][tgt]["grupos"][nivel]["filas"]:
        if f["grupo"] == grupo:
            return f
    return None


def tabla_pronostico_agregado(bd: Dict, r45: Optional[Dict], nivel: str, k: str = "2") -> List[str]:
    """P74: expected share of each grade band (T2 band model, test) next to the expected share eliminated (T5) and with a
    change of program (T4) of T4/T5 at cut ``k`` (test); each cell is predicted (observed); a dash = the group does not meet
    the thresholds of that task (n >= 100 and 10 events) or the band has fewer than 10 attempts."""
    cab = ("| " + ("Programa" if nivel == "programa" else "Facultad") + " | Intentos (T2) | " + " | ".join(f"% {CORTA_BANDA[c].lower()}" for c in BANDAS)
           + f" | % eliminado (T5, k = {k}) | % elimin. efectiva (T5, sin reintegro) | % con cambio de programa (T4, k = {k}) |")
    out = [cab, "|---|---|" + "---|" * (len(BANDAS) + 3)]
    nombres = {}
    for f in bd["grupos"]["test"]["programa"]["filas"]:
        nombres[f["grupo"]] = f.get("nombre", "")
    filas = bd["grupos"]["test"][nivel]["filas"]
    for f in sorted(filas, key=lambda r: -(r["bandas"]["reprobado"]["predicha"] or {"punto": 0})["punto"]):
        cel = []
        for c in BANDAS:
            b = f["bandas"][c]
            cel.append("—" if b["observada"] is None else f"{100 * b['predicha']['punto']:.1f} ({100 * b['observada']['punto']:.1f})")
        for tgt in ("T5", "T5E", "T4"):
            g = _t45_grupo(r45, k, tgt, nivel, f["grupo"])
            cel.append("—" if g is None else f"{100 * g['riesgo_medio']['punto']:.1f} ({100 * g['tasa_observada']['punto']:.1f})")
        nombre = f["grupo"] if nivel == "facultad" else f"{f['grupo']} · {nombres.get(f['grupo'], '')}".strip(" ·")
        out.append(coma_m(f"| {nombre} | {miles_x(f['n'])} | " + " | ".join(cel) + " |"))
    return out


def tabla_deriva(ev: Dict) -> List[str]:
    """P55: course statistics with a recent window or exponential decay against the expanding history (set c)."""
    ms = [m for m in ("cb_c", "cb_c_decay", "cb_c_vent") if m in ev["test"]]
    out = ["| Partición | Modelo | AP reprobación | ROC-AUC | Brier | ECE |", "|---|---|---|---|---|---|"]
    for sp in ("valid", "test", "posterior"):
        for m in ms:
            r = ev[sp][m]
            out.append(f"| {sp} | {NOMBRES[m]} | {con_ic(r['ap'])} | {con_ic(r['roc_auc'])} | {con_ic(r['brier'], 4)} | {con_ic(r['ece'])} |")
    out.append("")
    out.append("| Diferencia pareada de AP (A − B) | valid | test | posterior | ¿El intervalo de test excluye 0? |")
    out.append("|---|---|---|---|---|")
    for a, b in (("cb_c_decay", "cb_c"), ("cb_c_vent", "cb_c"), ("cb_c_decay", "cb_c_vent")):
        d = {sp: ev[sp].get(f"__delta__{a}__{b}") for sp in ("valid", "test", "posterior")}
        if not all(d.values()):
            continue
        t = d["test"]["ap"]
        excluye = "sí" if t["lo"] > 0 else "sí (empeora)" if t["hi"] < 0 else "no"
        out.append(f"| {NOMBRES[a]} − {NOMBRES[b]} | {con_ic(d['valid']['ap'])} | {con_ic(t)} | {con_ic(d['posterior']['ap'])} | {excluye} |")
    return [coma(x) if x.startswith("|") else x for x in out]


def tabla_cambios(res: Dict) -> List[str]:
    prev = CB.cargar_previo("resultados_t2")
    if prev is None:
        return CB.sin_previo()
    ea, en = prev["evaluacion"], res["evaluacion"]
    da, dn = prev["descriptivo"]["split"], res["descriptivo"]["split"]
    filas = [("Intentos de train", da["train"]["n"], dn["train"]["n"], 0), ("Intentos de test", da["test"]["n"], dn["test"]["n"], 0),
             ("Tasa de reprobación de train", da["train"]["tasa_reprobacion"], dn["train"]["tasa_reprobacion"], 4),
             ("Tasa de reprobación de test", da["test"]["tasa_reprobacion"], dn["test"]["tasa_reprobacion"], 4)]
    for m in ("baseline", "cb_a", "cb_b", "cb_c", "cb_d", "lr_c", "nn_gnn"):
        if m in ea["test"] and m in en["test"]:
            filas.append((f"AP de test, {NOMBRES[m]}", ea["test"][m]["ap"], en["test"][m]["ap"], 3))
    for m in ("cb_b", "cb_c"):
        filas.append((f"ROC-AUC de test, {NOMBRES[m]}", ea["test"][m]["roc_auc"], en["test"][m]["roc_auc"], 3))
    for a_, b_ in (("cb_c", "cb_b"), ("cb_cemb", "cb_c"), ("nn_gnn", "nn_mlp")):
        filas.append((f"ΔAP de test pareado, {NOMBRES[a_]} − {NOMBRES[b_]}", ea["test"].get(f"__delta__{a_}__{b_}", {}).get("ap"),
                      en["test"].get(f"__delta__{a_}__{b_}", {}).get("ap"), 3))
    out = CB.tabla(filas)
    out.append("")
    out.append(f"Mejor CatBoost en valid: {NOMBRES[ea['mejor_catboost_valid']]} → {NOMBRES[en['mejor_catboost_valid']]}.")
    return out


def bloques(res: Dict) -> Dict[str, str]:
    ev = res["evaluacion"]
    nl = "\n"
    mejor = ev["mejor_catboost_valid"]
    b: Dict[str, str] = {
        "embudo": nl.join(tabla_embudo(res)), "split": nl.join(tabla_split(res)),
        "cobertura": nl.join(tabla_cobertura(res)), "periodos": nl.join(tabla_periodos(res)),
        "oportunidad": nl.join(tabla_oportunidad(res)), "semillas": nl.join(tabla_semillas(res)),
        "tiempos": nl.join(tabla_tiempos(res)), "enlaces": nl.join(tabla_enlaces(res)),
        "importancia": nl.join(tabla_importancia(res)), "ap_periodo": nl.join(tabla_ap_periodo(ev)),
    }
    for sp in ("valid", "test", "posterior"):
        b[f"modelos.{sp}"] = nl.join(tabla_modelos(ev, sp))
        b[f"ranking.{sp}"] = nl.join(tabla_ranking(ev, sp))
        b[f"deltas.{sp}"] = nl.join(tabla_deltas(ev, sp, ev["pares"]))
        b[f"ablacion.{sp}"] = nl.join(tabla_ablacion(ev, sp))
        b[f"grafo.{sp}"] = nl.join(tabla_grafo(ev, sp))
    claves = [m for m in dict.fromkeys(["baseline", "cb_b", "cb_c", mejor, "nn_gnn"]) if m in ev["subgrupos_test"]]
    b["calibracion"] = nl.join(tabla_calibracion(ev, [m for m in ("baseline", "cb_c", "nn_gnn") if m in ev["calibracion_test"]]))
    nom = nombres_programa()
    for g in ("programa", "sem_malla", "oportunidad", "sexo", "en_malla", "info_prereq"):
        if g == "sexo":
            b["sub.sexo"] = nl.join(tabla_sexo(ev, claves))
        else:
            b[f"sub.{g}"] = nl.join(tabla_grupo(ev, claves, g, 80, nom))
    b["modelos_sub"] = ", ".join(f"`{m}`" for m in claves)
    b["cambios"] = nl.join(tabla_cambios(res))
    if "cb_c_decay" in ev["test"]:
        b["deriva"] = nl.join(tabla_deriva(ev))
    bd = ev.get("bandas")
    if bd:
        r45p = ART / "resultados_t45.json"
        r45 = json.loads(r45p.read_text(encoding="utf-8")) if r45p.exists() else None
        b["bandas.distribucion"] = nl.join(tabla_bandas_distribucion(bd))
        for sp in ("valid", "test", "posterior"):
            b[f"bandas.metricas.{sp}"] = nl.join(tabla_bandas_metricas(bd, sp))
        b["bandas.resumen"] = nl.join(tabla_bandas_resumen(bd))
        b["bandas.programas"] = nl.join(tabla_bandas_programas(bd["grupos"]["test"]))
        for c in BANDAS:
            b[f"bandas.facultad.{c}"] = nl.join(tabla_bandas_facultad(bd["grupos"]["test"], c))
        for nivel in ("programa", "facultad"):
            b[f"bandas.ranking.{nivel}"] = nl.join(tabla_bandas_ranking(bd, nivel, {f["grupo"]: f.get("nombre", "") for f in bd["grupos"]["test"]["programa"]["filas"]}))
            b[f"pronostico.{nivel}"] = nl.join(tabla_pronostico_agregado(bd, r45, nivel))
    return b


def _valor(ev: Dict, ruta: str, tipo: str) -> str:
    if tipo == "d":
        split, a, b, metrica = ruta.split(".")
        m = ev[split][f"__delta__{a}__{b}"][metrica]
    else:
        split, modelo, metrica = ruta.split(".")
        m = ev[split][modelo][metrica]
    d = dec(metrica)
    return coma(con_ic(m, d) if tipo in ("ic", "d") else f"{m['punto']:.{d}f}")


def documento() -> str:
    res = json.loads((ART / "resultados_t2.json").read_text(encoding="utf-8"))
    blq = bloques(res)
    ev = res["evaluacion"]
    plantilla = (RAIZ / "tools" / "plantilla_t2.md").read_text(encoding="utf-8")

    def sustituir(m) -> str:
        clave = m.group(1)
        tipo, _, ruta = clave.partition(":")
        if tipo == "meta":
            return {"snapshot_hash": res["snapshot_hash"], "version_codigo": res["version_codigo"],
                    "mejor_cb": ev["mejor_catboost_valid"], "ram": f"{res['ram_pico_mb']:.0f}",
                    "segundos": f"{res['segundos_totales']:.0f}"}[ruta]
        if tipo == "tabla":
            return blq[ruta]
        if tipo == "n":
            sp, k = ruta.split(".")
            return miles(res["descriptivo"]["split"][sp][k]) if k != "tasa_reprobacion" else coma(
                f"{100 * res['descriptivo']['split'][sp][k]:.1f}")
        if tipo in ("v", "ic", "d"):
            return _valor(ev, ruta, tipo)
        if tipo == "b":                       # a metric of the band model: split.modelo.metrica
            split, modelo, metrica = ruta.split(".")
            return coma(con_ic(ev["bandas"]["metricas"][split][modelo][metrica], dec(metrica) if metrica != "logloss" else 4))
        if tipo == "bd":                      # difference of the band model against the frequency baseline
            split, metrica = ruta.split(".")
            return coma(con_ic(ev["bandas"]["metricas"][split]["cb_bandas__vs__frecuencias"][metrica], 4 if metrica == "logloss" else 3))
        if tipo == "bx":                      # any value of ``evaluacion.bandas`` by dotted path
            x = ev["bandas"]
            for q in ruta.split("."):
                x = x[int(q)] if isinstance(x, list) else x[q]
            return coma(f"{x:.3f}") if isinstance(x, float) else miles(x) if isinstance(x, int) else str(x)
        raise KeyError(clave)

    return re.sub(r"\{\{([^}]+)\}\}", sustituir, plantilla)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["--doc"]:
        (RAIZ / "docs" / "09_benchmark_t2.md").write_text(documento(), encoding="utf-8")
        print("escrito docs/09_benchmark_t2.md")
        return 0
    res = json.loads((ART / "resultados_t2.json").read_text(encoding="utf-8"))
    for nombre, texto in bloques(res).items():
        print(f"\n<!--{{{{tabla:{nombre}}}}}-->\n{texto}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
