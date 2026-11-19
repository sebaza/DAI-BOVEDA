"""Render docs/10_benchmark_t3.md from the gitignored aggregate JSON (``artefactos/resultados_t3.json``).

``python tools/informe_t3.py --doc`` assembles the document from ``tools/plantilla_t3.md`` (hand-written text) and the
tables built here. Markers in the template: ``{{tabla:NOMBRE}}`` (a named block), ``{{v:k.split.modelo.metrica}}`` (point
value, Spanish decimal comma), ``{{ic:k.split.modelo.metrica}}`` (point and 95 % interval), ``{{d:k.split.a.b.metrica}}``
(paired difference a - b with interval), ``{{x:ruta}}`` (a value of the JSON by dotted path), ``{{meta:...}}``.
Aggregates only; groups smaller than 10 are never printed.
"""
from __future__ import annotations

import json
import re
import statistics as st
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cambios_etapa_b as CB  # noqa: E402
import informe_t3_beneficios as IB3  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
ART = RAIZ / "artefactos"

NOMBRES = {
    "km_global": "Aalen–Johansen global (sin covariables)", "km_programa": "Aalen–Johansen por programa",
    "cox_adm": "Cox causa-específico (ingreso)", "cox_agg": "Cox causa-específico (ingreso + agregados)",
    "dt_lr_adm": "Logística persona-período (ingreso)", "dt_lr_agg": "Logística persona-período (ingreso + agregados)",
    "dt_cb_adm": "CatBoost persona-período (ingreso)", "dt_cb_agg": "CatBoost persona-período (ingreso + agregados)",
    "nn_mlp_adm": "Red MLP de riesgos discretos (ingreso)", "nn_mlp_agg": "Red MLP de riesgos discretos (ingreso + agregados)",
    "nn_gru": "Red GRU de riesgos discretos (ingreso + agregados + secuencia)",
}
ORDEN = list(NOMBRES)
ETIQ = {"c": "C de Uno", "auc": "AUC(t)", "brier": "Brier", "ibs": "IBS"}
CORTE = {"0": "k = 0 (al ingreso)", "2": "k = 2 (fin del 2.º semestre)", "4": "k = 4 (fin del 4.º semestre)"}
SUBGRUPO_ETIQ = {"programa": "programa (n ≥ 500)", "programa_n150": "programa (n ≥ 150)", "via": "vía de ingreso",
                 "sexo": "sexo (solo evaluación de equidad)", "duracion_nominal": "duración nominal del programa (semestres)",
                 "cohorte": "cohorte de admisión", "plan_comun": "trayectoria de Plan Común (D47)"}


def miles(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def coma(t: str) -> str:
    return t.replace(".", ",")


def pct(x: float, dec: int = 1) -> str:
    return coma(f"{100 * x:.{dec}f}") + " %"


def con_ic(d: Dict[str, float], dec: int = 3) -> str:
    if d["lo"] != d["lo"]:
        return f"{d['punto']:.{dec}f}"
    return f"{d['punto']:.{dec}f} [{d['lo']:.{dec}f}; {d['hi']:.{dec}f}]"


def dec(m: str) -> int:
    return 4 if m.startswith("brier") or m == "ibs" else 3


def modelos_en(ev: Dict, split: str) -> List[str]:
    return [m for m in ORDEN if m in ev[split]]


def tabla_embudo(res: Dict) -> List[str]:
    e = res["embudo"]
    filas = [("Unidades de pregrado de las cohortes 2015 o posteriores (T1, sin IN/PE/IE, sin Programa de Intercambio, con Plan Común unido a su especialidad)", "poblacion"),
             ("− sin estado de matrícula en el período del corte", "sin_matricula_en_corte"),
             ("− con estado de salida en el período del corte (D24, P52)", "salida_en_corte"),
             ("− egresado o titulado hasta el corte", "ya_egresado_o_titulado"),
             ("− sin seguimiento después del corte (corte en el último período cerrado)", "sin_seguimiento"),
             ("= **Elegibles**", "elegibles")]
    ks = [k for k in ("0", "2", "4") if f"embudo_k{k}_poblacion" in e]
    out = ["| Paso | " + " | ".join(f"k = {k}" for k in ks) + " |", "|---|" + "---|" * len(ks)]
    for nombre, clave in filas:
        out.append(f"| {nombre} | " + " | ".join(miles(e[f"embudo_k{k}_{clave}"]) for k in ks) + " |")
    memo = [("Memo: episodios de cohortes anteriores a 2015, fuera de la ventana (P49/P50)", "cohortes_anteriores_excluidas"),
            ("Memo: episodios del Programa de Intercambio excluidos (cohortes 2015 o posteriores)", "intercambio_excluidos"),
            ("Memo: … de ellos, elegibles en este corte si se hubieran mantenido", "intercambio_elegibles_excluidos"),
            ("Memo: episodios de especialidad unidos a un Plan Común (no cuentan como unidad)", "especialidades_absorbidas"),
            ("Memo: … de ellos, elegibles en este corte como unidad separada (doble conteo evitado)", "especialidades_absorbidas_elegibles"),
            ("Memo: trayectorias de Plan Común elegibles en este corte", "plan_comun_elegibles"),
            ("Memo: … de ellas, unidas a una especialidad", "plan_comun_unidos_elegibles")]
    for nombre, clave in memo:
        out.append(f"| {nombre} | " + " | ".join(miles(e[f"embudo_k{k}_{clave}"]) for k in ks) + " |")
    return out


def tabla_union(res: Dict) -> List[str]:
    e = res["embudo"]
    g = lambda c: int(e[f"embudo_k0_{c}"])                          # noqa: E731  (population-level counts, equal at every k)
    filas = [
        ("Episodios de Ingeniería Civil Plan Común (programas 8633 y 8643) de las cohortes 2015 o posteriores", g("plan_comun_episodios")),
        ("… con una especialidad de Ingeniería Civil como primer episodio posterior dentro de 2 períodos regulares (**unidos**, regla aplicada)", g("plan_comun_unidos")),
        ("… … de ellos, con vía de admisión ES (Elección Especialidad) en la especialidad", g("unidos_es")),
        ("… … de ellos, con el mismo período de admisión que el Plan Común", g("unidos_mismo_periodo")),
        ("… … de ellos, con ES y el mismo período de admisión (regla estricta alternativa)", g("unidos_es_mismo_periodo")),
        ("… con primera especialidad posterior fuera de la ventana de 2 períodos (no se unen)", g("plan_comun_fuera_de_ventana")),
        ("… sin continuación en Ingeniería Civil (conservan el tratamiento anterior: salida)", g("plan_comun_sin_continuacion") - g("plan_comun_fuera_de_ventana")),
    ]
    return ["| Plan Común y su continuación | Episodios |", "|---|---|"] + [f"| {a} | {miles(b)} |" for a, b in filas]


def tabla_plan_comun(res: Dict) -> List[str]:
    d = res["descriptivo"]["plan_comun"]
    nombres = {"unidas": "unidas a una especialidad", "sin_continuacion": "sin continuación"}
    out = ["| k | Partición | Trayectorias de Plan Común | Egreso | Salida definitiva | Censura | Mediana del tiempo al egreso (semestres) |",
           "|---|---|---|---|---|---|---|"]
    for k in ("0", "2", "4"):
        for s in ("train", "valid", "test", "posterior"):
            for g in ("unidas", "sin_continuacion"):
                v = d.get(k, {}).get(s, {}).get(g)
                if not v or v["n"] < 10:
                    continue
                med = "—" if v["tiempo_mediano_egreso"] is None or v["egreso"] < 10 else coma(f"{v['tiempo_mediano_egreso']:.0f}")
                out.append(f"| {k} | {s} | {nombres[g]}: {miles(v['n'])} | {miles(v['egreso'])} ({pct(v['egreso'] / v['n'])}) | "
                           f"{miles(v['salida'])} ({pct(v['salida'] / v['n'])}) | {miles(v['censura'])} ({pct(v['censura'] / v['n'])}) | {med} |")
    return out


def tabla_consistencia(res: Dict) -> List[str]:
    c = {k: int(v) for k, v in res["consistencia"].items()}
    filas = [
        ("Episodios de la población (cohortes ≥ 2015)", c["episodios"]),
        ("Con algún estado de clase egreso/titulación (G, Z, K, L, U)", c["con_estado_egreso_titulacion"]),
        ("Con fila vinculada en `titulacion` (banner_titulados)", c["con_fila_titulacion"]),
        ("… en ambas fuentes", c["ambos"]), ("… solo en estados (egresados sin fila de titulación)", c["solo_estado"]),
        ("… solo en la tabla de titulación (sin estado)", c["solo_fila"]),
        ("Con estado `U` (Titulado)", c["con_estado_titulado"]),
        ("… `U` sin fila de titulación", c["estado_titulado_sin_fila"]),
        ("Fila de titulación sin estado `U`", c["fila_sin_estado_titulado"]),
        ("Ambas fuentes: fecha de titulación en el mismo semestre que el primer estado de egreso", c["fila_mismo_slot_que_primer_estado"]),
        ("… en un semestre anterior al primer estado", c["fila_antes_que_primer_estado"]),
        ("… en un semestre posterior al primer estado", c["fila_despues_del_primer_estado"]),
        ("Fila con estado `U`: misma fecha-semestre", c["fila_mismo_slot_del_estado_titulado"]),
        ("… fecha-semestre un semestre antes que el estado `U`", c["fila_un_slot_antes_del_estado_titulado"]),
        ("… otro desfase", c["fila_otro_desfase_del_estado_titulado"]),
        ("Salida definitiva registrada antes del egreso", c["salida_definitiva_antes_del_egreso"]),
        ("Egreso registrado después del último período cerrado (censurado)", c["egreso_posterior_al_cierre"]),
        ("Filas de `titulacion` sin episodio vinculado (todas las cohortes; no se usan)", c["filas_titulacion_sin_episodio"]),
    ]
    return ["| Concordancia entre fuentes | Episodios |", "|---|---|"] + [f"| {a} | {miles(b)} |" for a, b in filas]


def tabla_split(res: Dict) -> List[str]:
    d = res["descriptivo"]["por_k_split"]
    cohortes = {"train": "2015-2017", "valid": "2018", "test": "2019-2020", "posterior": "2021 en adelante"}
    out = ["| k | Partición (cohortes) | Episodios | Egreso/titulación | Salida definitiva | Censura administrativa | Seguimiento (semestres) | Mediana del tiempo al egreso |",
           "|---|---|---|---|---|---|---|---|"]
    for k in ("0", "2", "4"):
        for s in ("train", "valid", "test", "posterior"):
            v = d.get(k, {}).get(s)
            if not v:
                continue
            seg = f"{v['seguimiento_min']}–{v['seguimiento_max']}"
            med = "—" if v["tiempo_mediano_egreso"] is None else coma(f"{v['tiempo_mediano_egreso']:.0f}")
            out.append(f"| {k} | {s} ({cohortes[s]}) | {miles(v['n'])} | {miles(v['egreso'])} ({pct(v['egreso'] / v['n'])}) | "
                       f"{miles(v['salida'])} ({pct(v['salida'] / v['n'])}) | {miles(v['censura'])} ({pct(v['censura'] / v['n'])}) | "
                       f"{seg} | {med} |")
    return out


def tabla_cohorte(res: Dict) -> List[str]:
    out = ["| Cohorte | Episodios (k = 2) | Egreso/titulación observado | Salida definitiva | Censurado | Seguimiento mediano (semestres) |",
           "|---|---|---|---|---|---|"]
    for a, v in sorted(res["descriptivo"]["por_cohorte"].items()):
        if int(a) < 2015 or v["n"] < 10:
            continue
        seg = coma(format(v["seguimiento_mediano"], ".0f"))
        out.append(f"| {a} | {miles(v['n'])} | {pct(v['egreso'])} | {pct(v['salida'])} | {pct(v['censura'])} | {seg} |")
    return out


def tabla_incidencia(res: Dict) -> List[str]:
    out = ["| Partición (k = 0) | Semestre desde la admisión | Incidencia acumulada de egreso (Aalen–Johansen) | 1 − Kaplan–Meier (salida como censura) | Diferencia | Incidencia acumulada de salida (AJ) |",
           "|---|---|---|---|---|---|"]
    for s, v in res["descriptivo"]["incidencia_comparada"].items():
        for i, sl in enumerate(v["slots"]):
            if sl in (8, 10, 12, 14, 16, 18):
                dif = coma(format(100 * (v["ingenua"][i] - v["F1"][i]), "+.1f"))
                out.append(f"| {s} (n = {miles(v['n'])}) | {sl} | {pct(v['F1'][i])} | {pct(v['ingenua'][i])} | "
                           f"{dif} pp | {pct(v['F2'][i])} |")
    return out


def tabla_salida(res: Dict) -> List[str]:
    out = ["| Partición (k = 2) | Salidas | Explícitas | Por ausencia sostenida | Explícitas con matrícula posterior en otro programa | Por ausencia con matrícula posterior en otro programa |",
           "|---|---|---|---|---|---|"]
    for s, v in res["descriptivo"]["salida"].items():
        if v["n"] < 10:
            continue
        out.append(f"| {s} | {miles(v['n'])} | {miles(v['explicita'])} | {miles(v['ausencia'])} | "
                   f"{miles(v['a_otro_programa_explicita'])} ({pct(v['a_otro_programa_explicita'] / max(v['explicita'], 1))}) | "
                   f"{miles(v['a_otro_programa_ausencia'])} ({pct(v['a_otro_programa_ausencia'] / max(v['ausencia'], 1))}) |")
    return out


def tabla_duracion(res: Dict) -> List[str]:
    out = ["| Duración nominal (semestres) | Episodios (k = 2, 2015-2020) | Egreso/titulación observado | Salida definitiva |", "|---|---|---|---|"]
    for a, v in sorted(res["descriptivo"]["duracion_nominal"].items(), key=lambda kv: int(kv[0])):
        if v["n"] < 10:
            continue
        out.append(f"| {'sin dato' if int(a) < 0 else a} | {miles(v['n'])} | {pct(v['egreso'])} | {pct(v['salida'])} |")
    return out


def tabla_rank(ev: Dict, split: str) -> List[str]:
    hs = sorted({int(k.split("_")[1]) for k in next(iter(m for m in ev[split].values() if isinstance(m, dict) and "ibs" in m)) if k.startswith("c_")})
    cab = "| Modelo | " + " | ".join(f"C de Uno (t = {h})" for h in hs) + " | " + " | ".join(f"AUC(t = {h})" for h in hs) + " |"
    out = [cab, "|---|" + "---|" * (2 * len(hs))]
    for m in modelos_en(ev, split):
        r = ev[split][m]
        out.append(f"| {NOMBRES[m]} | " + " | ".join(con_ic(r[f"c_{h}"]) for h in hs) + " | "
                   + " | ".join(con_ic(r[f"auc_{h}"]) for h in hs) + " |")
    return out


def tabla_brier(ev: Dict, split: str) -> List[str]:
    hs = sorted({int(k.split("_")[1]) for k in next(iter(m for m in ev[split].values() if isinstance(m, dict) and "ibs" in m)) if k.startswith("c_")})
    cab = "| Modelo | " + " | ".join(f"Brier(t = {h})" for h in hs) + " | IBS |"
    out = [cab, "|---|" + "---|" * (len(hs) + 1)]
    for m in modelos_en(ev, split):
        r = ev[split][m]
        out.append(f"| {NOMBRES[m]} | " + " | ".join(con_ic(r[f"brier_{h}"], 4) for h in hs) + f" | {con_ic(r['ibs'], 4)} |")
    return out


def tabla_deltas(ev: Dict, split: str, pares: List[List[str]]) -> List[str]:
    hs = [10, 12] if split != "posterior" else [8, 10]
    out = ["| Comparación (A − B, diferencia pareada) | " + " | ".join(f"ΔC (t = {h})" for h in hs) + " | "
           + " | ".join(f"ΔAUC (t = {h})" for h in hs) + " | ΔBrier (t = 12) | ΔIBS |", "|---|" + "---|" * (2 * len(hs) + 2)]
    for a, b in pares:
        d = ev[split].get(f"__delta__{a}__{b}")
        if d:
            bh = 12 if split != "posterior" else 10
            out.append(f"| {NOMBRES[a]} − {NOMBRES[b]} | " + " | ".join(con_ic(d[f"c_{h}"]) for h in hs) + " | "
                       + " | ".join(con_ic(d[f"auc_{h}"]) for h in hs) + f" | {con_ic(d[f'brier_{bh}'], 4)} | {con_ic(d['ibs'], 4)} |")
    return out


def tabla_ablacion(ev: Dict, split: str) -> List[str]:
    t = ev[split]
    h = 12 if split != "posterior" else 10
    out = [f"| Escalón | Cox C({h}) | Logística C({h}) | CatBoost C({h}) | Red C({h}) | Cox IBS | Logística IBS | CatBoost IBS | Red IBS |",
           "|---|---|---|---|---|---|---|---|---|"]
    filas = [("0. Aalen–Johansen global", ["km_global"] * 4), ("1. Aalen–Johansen por programa", ["km_programa"] * 4),
             ("2. Perfil de ingreso", ["cox_adm", "dt_lr_adm", "dt_cb_adm", "nn_mlp_adm"]),
             ("3. + agregados académicos al corte", ["cox_agg", "dt_lr_agg", "dt_cb_agg", "nn_mlp_agg"]),
             ("4. + secuencia de semestres (GRU)", [None, None, None, "nn_gru"])]
    for nombre, ms in filas:
        c = [con_ic(t[m][f"c_{h}"]) if m in t else "—" for m in ms]
        i = [con_ic(t[m]["ibs"], 4) if m in t else "—" for m in ms]
        out.append(f"| {nombre} | " + " | ".join(c) + " | " + " | ".join(i) + " |")
    return out


def tabla_calibracion(ev: Dict, tau: str, modelos: List[str]) -> List[str]:
    cal = ev["calibracion_test"][tau]
    ms = [m for m in modelos if m in cal]
    out = ["| Decil de riesgo | " + " | ".join(f"{NOMBRES[m]}: predicho / observado" for m in ms) + " |", "|---|" + "---|" * len(ms)]
    for i in range(10):
        celdas = []
        for m in ms:
            r = next((x for x in cal[m] if x["decil"] == i + 1), None)
            celdas.append(f"{r['riesgo_medio']:.3f} / {r['tasa_observada']:.3f}" if r and r["n"] >= 10 else "—")
        out.append(f"| {i + 1} | " + " | ".join(celdas) + " |")
    return out


def tabla_incidencia_media(ev: Dict) -> List[str]:
    t = ev["incidencia_media_test"]
    ms = [m for m in ev["modelos_subgrupo"]]
    out = ["| Horizonte (semestres desde la admisión) | Episodios con seguimiento | Incidencia observada | " + " | ".join(NOMBRES[m] for m in ms) + " |",
           "|---|---|---|" + "---|" * len(ms)]
    for tau, v in t.items():
        out.append(f"| {tau} | {miles(v['n'])} | {pct(v['observada'])} | " + " | ".join(pct(v[m]) for m in ms) + " |")
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
    ms = [m for m in modelos if m in ev["subgrupos_test"]]
    base = ev["subgrupos_test"][ms[0]][grupo]
    if not base:
        return ["*(ningún grupo alcanza el tamaño mínimo)*"]
    cab = "| Grupo | n (con seguimiento a 12) | Incidencia observada a 12 |" + "".join(f" {NOMBRES[m]}: predicha / AUC |" for m in ms)
    out = [cab, "|---|---|---|" + "---|" * len(ms)]
    por = {m: {r["grupo"]: r for r in ev["subgrupos_test"][m][grupo]} for m in ms}
    for r in base[:limite]:
        if r["n"] < 10:
            continue
        et = f"{r['grupo']} {nombres.get(r['grupo'], '')}".strip() if grupo.startswith("programa") else r["grupo"]
        celdas = []
        for m in ms:
            x = por[m].get(r["grupo"])
            ap = "—" if x is None or x["auc"] != x["auc"] else f"{x['auc']:.3f}"
            celdas.append(f"{x['incidencia_predicha']:.3f} / {ap}" if x else "—")
        out.append(f"| {et} | {miles(r['n'])} | {r['incidencia_observada']:.3f} | " + " | ".join(celdas) + " |")
    return out


def tabla_sexo(ev: Dict) -> List[str]:
    out = ["| Modelo | Incidencia F | Incidencia M | Predicha F | Predicha M | AUC F | AUC M | ΔAUC (F−M) | Brecha de calibración F | Brecha de calibración M |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for m in ev["modelos_subgrupo"]:
        t = {r["grupo"]: r for r in ev["subgrupos_test"][m]["sexo"]}
        if "F" not in t or "M" not in t:
            continue
        f, h = t["F"], t["M"]
        out.append(f"| {NOMBRES[m]} | {f['incidencia_observada']:.3f} | {h['incidencia_observada']:.3f} | {f['incidencia_predicha']:.3f} | "
                   f"{h['incidencia_predicha']:.3f} | {f['auc']:.3f} | {h['auc']:.3f} | {f['auc'] - h['auc']:+.3f} | "
                   f"{f['brecha_calibracion']:+.3f} | {h['brecha_calibracion']:+.3f} |")
    return out


def tabla_tiempos(res: Dict) -> List[str]:
    out = ["| k | Modelo | Tiempo de entrenamiento (s) | Notas |", "|---|---|---|---|"]
    for k in res["ks"]:
        k = str(k)
        for m in ORDEN:
            if m not in res["tiempos_s"][k]:
                continue
            i = res["info"][k].get(m, {})
            nota = ""
            if m.startswith("nn_"):
                r = i["semillas"]
                nota = (f"{r[0]['n_parametros']} parámetros; pico de GPU {i['gpu_pico_mb']:.0f} MB; "
                        f"épocas óptimas {[s['mejor_epoca'] for s in r]}")
            elif m.startswith("dt_cb"):
                nota = f"3 semillas; iteraciones óptimas {i.get('mejores_iteraciones')}"
            elif m.startswith("dt_lr"):
                nota = f"C = {i['C']}; {i['n_variables']} columnas; {miles(i['filas_persona_periodo'])} filas persona-período"
            elif m.startswith("cox"):
                nota = f"penalizador {i['penalizador']}; {i['n_variables']} columnas activas"
            out.append(f"| {k} | {NOMBRES[m]} | {res['tiempos_s'][k][m]:.0f} | {nota} |")
    return out


def tabla_semillas(res: Dict) -> List[str]:
    out = ["| k | Red (3 semillas) | C(12) valid (media ± sd) | C(12) test (media ± sd) | IBS test (media ± sd) |", "|---|---|---|---|---|"]
    sd = lambda x: st.stdev(x) if len(x) > 1 else 0.0       # noqa: E731
    for k in res["ks"]:
        for m, runs in res["semillas"][str(k)].items():
            v = [r["valid"]["c_12"] for r in runs]
            t = [r["test"]["c_12"] for r in runs]
            i = [r["test"]["ibs"] for r in runs]
            out.append(f"| {k} | {NOMBRES[m]} | {st.mean(v):.3f} ± {sd(v):.3f} | {st.mean(t):.3f} ± {sd(t):.3f} | "
                       f"{st.mean(i):.4f} ± {sd(i):.4f} |")
    return out


def tabla_importancia(res: Dict, k: str) -> List[str]:
    imp = (res["info"][k].get("dt_cb_agg") or res["info"][k].get("dt_cb_adm") or {}).get("importancia_top15", {})
    out = ["| Variable | Importancia (media de 3 semillas, % del total) |", "|---|---|"]
    for a, v in imp.items():
        out.append(f"| `{a}` | {v:.1f} |")
    return out


def tabla_elegibles(res: Dict) -> List[str]:
    out = ["| k | Partición | Episodios | Con seguimiento a 10 | a 12 | a 14 |", "|---|---|---|---|---|---|"]
    for k in res["ks"]:
        ev = res["por_k"][str(k)]
        for s in ("valid", "test"):
            e = ev[s]["__elegibles"]
            out.append(f"| {k} | {s} | {miles(ev[s]['__n'])} | {miles(e['10'])} | {miles(e['12'])} | {miles(e['14'])} |")
        e = ev["posterior"]["__elegibles"]
        out.append(f"| {k} | posterior (horizontes 8 y 10) | {miles(ev['posterior']['__n'])} | a 8: {miles(e['8'])} | a 10: {miles(e['10'])} | — |")
    return out


def tabla_mejor(res: Dict) -> List[str]:
    out = ["| k | Mejor modelo clásico en valid (IBS) | IBS valid | Mejor red en valid (IBS) | IBS valid |", "|---|---|---|---|---|"]
    for k in res["ks"]:
        ev = res["por_k"][str(k)]
        ib = ev["ibs_valid"]
        redes = {m: v for m, v in ib.items() if m.startswith("nn_")}
        mr = min(redes, key=redes.get)
        mc = ev["mejor_clasico_valid"]
        out.append(f"| {k} | {NOMBRES[mc]} | {ib[mc]:.4f} | {NOMBRES[mr]} | {ib[mr]:.4f} |")
    return out


def tabla_cambios(res: Dict) -> List[str]:
    """Before / after of the stage B rebuild (mm_* + admission test instead of pct_*): test metrics of T3 at k = 2 and 4."""
    prev = CB.cargar_previo("resultados_t3")
    if prev is None:
        return CB.sin_previo()
    filas = []
    for k in ("2", "4"):
        a, b = prev["por_k"][k]["test"], res["por_k"][k]["test"]
        for m in ("km_programa", "cox_agg", "dt_cb_agg", "nn_gru"):
            if m in a and m in b:
                filas.append((f"k = {k}: IBS de test, {NOMBRES.get(m, m)}", a[m]["ibs"], b[m]["ibs"], 4))
        for m in ("dt_cb_agg", "nn_gru"):
            if m in a and m in b:
                filas.append((f"k = {k}: C de test a 12 semestres, {NOMBRES.get(m, m)}", a[m]["c_12"], b[m]["c_12"], 3))
    out = CB.tabla(filas)
    out.append("")
    out.append("Mejor clásico en valid: " + "; ".join(f"k = {k}: {NOMBRES.get(prev['por_k'][k]['mejor_clasico_valid'], prev['por_k'][k]['mejor_clasico_valid'])} → "
                                                      f"{NOMBRES.get(res['por_k'][k]['mejor_clasico_valid'], res['por_k'][k]['mejor_clasico_valid'])}" for k in ("2", "4")) + ".")
    return out


def bloques(res: Dict) -> Dict[str, str]:
    nl = "\n"
    b: Dict[str, str] = {
        "embudo": nl.join(tabla_embudo(res)), "consistencia": nl.join(tabla_consistencia(res)),
        "split": nl.join(tabla_split(res)), "cohorte": nl.join(tabla_cohorte(res)),
        "incidencia": nl.join(tabla_incidencia(res)), "salida": nl.join(tabla_salida(res)),
        "duracion": nl.join(tabla_duracion(res)), "tiempos": nl.join(tabla_tiempos(res)),
        "semillas": nl.join(tabla_semillas(res)), "elegibles": nl.join(tabla_elegibles(res)),
        "mejor": nl.join(tabla_mejor(res)), "union": nl.join(tabla_union(res)),
        "plan_comun": nl.join(tabla_plan_comun(res)), "cambios": nl.join(tabla_cambios(res)),
    }
    nom = nombres_programa()
    for k in res["ks"]:
        k = str(k)
        ev = res["por_k"][k]
        b[f"importancia.{k}"] = nl.join(tabla_importancia(res, k))
        for sp in ("valid", "test", "posterior"):
            b[f"rank.{k}.{sp}"] = nl.join(tabla_rank(ev, sp))
            b[f"brier.{k}.{sp}"] = nl.join(tabla_brier(ev, sp))
            b[f"deltas.{k}.{sp}"] = nl.join(tabla_deltas(ev, sp, ev["pares"]))
            b[f"ablacion.{k}.{sp}"] = nl.join(tabla_ablacion(ev, sp))
        b[f"calibracion.{k}.12"] = nl.join(tabla_calibracion(ev, "12", ["km_programa", "cox_agg" if k != "0" else "cox_adm",
                                                                         "dt_cb_agg" if k != "0" else "dt_cb_adm",
                                                                         "nn_gru" if k != "0" else "nn_mlp_adm"]))
        b[f"incidencia_media.{k}"] = nl.join(tabla_incidencia_media(ev))
        b[f"sexo.{k}"] = nl.join(tabla_sexo(ev))
        for g in ("programa", "programa_n150", "via", "duracion_nominal", "cohorte", "plan_comun"):
            b[f"sub.{k}.{g}"] = nl.join(tabla_grupo(ev, ev["modelos_subgrupo"][:3] + ev["modelos_subgrupo"][-1:], g, 40, nom))
    return b


def _valor(res: Dict, ruta: str, tipo: str) -> str:
    if tipo == "d":
        k, split, a, b, metrica = ruta.split(".")
        m = res["por_k"][k][split][f"__delta__{a}__{b}"][metrica]
    else:
        k, split, modelo, metrica = ruta.split(".")
        m = res["por_k"][k][split][modelo][metrica]
    d = dec(metrica)
    return coma(con_ic(m, d) if tipo in ("ic", "d") else f"{m['punto']:.{d}f}")


def _ruta(res: Dict, ruta: str):
    x = res
    for p in ruta.split("."):
        x = x[int(p)] if isinstance(x, list) else x[p]
    return x


_DATOS_BEN: Dict = {}


def datos_ben() -> Dict:
    if not _DATOS_BEN:
        _DATOS_BEN.update(IB3.cargar())
    return _DATOS_BEN


def documento() -> str:
    res = json.loads((ART / "resultados_t3.json").read_text(encoding="utf-8"))
    blq = bloques(res)
    plantilla = (RAIZ / "tools" / "plantilla_t3.md").read_text(encoding="utf-8")

    def sustituir(m) -> str:
        clave = m.group(1)
        tipo, _, ruta = clave.partition(":")
        if tipo == "meta":
            return {"snapshot_hash": res["snapshot_hash"], "version_codigo": res["version_codigo"],
                    "ram": f"{res['ram_pico_mb']:.0f}", "segundos": f"{res['segundos_totales']:.0f}",
                    "minutos": f"{res['segundos_totales'] / 60:.0f}", "cierre": res["periodo_cierre"],
                    "gpu": str(res.get("gpu"))}[ruta]
        if tipo in IB3.TIPOS:                       # section 11 "Beneficios (16-11-2026)"
            return IB3.valor(clave, datos_ben())
        if tipo == "tabla":
            return blq[ruta]
        if tipo == "x":
            v = _ruta(res, ruta)
            return coma(f"{v:.3f}") if isinstance(v, float) else miles(v) if isinstance(v, int) else str(v)
        if tipo == "pct":
            return pct(float(_ruta(res, ruta)))
        if tipo in ("v", "ic", "d"):
            return _valor(res, ruta, tipo)
        raise KeyError(clave)

    return re.sub(r"\{\{([^}]+)\}\}", sustituir, plantilla)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["--doc"]:
        (RAIZ / "docs" / "10_benchmark_t3.md").write_text(documento(), encoding="utf-8")
        print("escrito docs/10_benchmark_t3.md")
        return 0
    res = json.loads((ART / "resultados_t3.json").read_text(encoding="utf-8"))
    for nombre, texto in bloques(res).items():
        print(f"\n<!--{{{{tabla:{nombre}}}}}-->\n{texto}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
