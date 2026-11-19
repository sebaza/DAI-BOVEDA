"""Render the markdown tables of docs/08_benchmark_t1.md from the gitignored aggregate JSON files.

``python tools/informe_t1.py [resultados_t1] > tablas.md`` prints the named blocks of one run;
``python tools/informe_t1.py --doc`` assembles ``docs/08_benchmark_t1.md`` from ``tools/plantilla_t1.md`` (hand-written text) and
the aggregate JSON of the official run (``resultados_t1.json``, train from cohort 2015) and of the all-years sensitivity run
(``resultados_t1_todos_anios.json``). Markers in the template: ``{{o.k1.test}}`` (block of the official run, ``s.`` =
sensitivity), ``{{pares.o.k1.test}}``, ``{{subpoblacion}}``, ``{{v:o.k1.test.cb_acad.ap}}`` (point value, Spanish
decimal comma) and ``{{ic:o.k1.test.cb_acad.ap}}`` (point and 95 % interval). Reads ``artefactos/*.json`` and the
gitignored predictions; prints aggregates only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cambios_etapa_b as CB  # noqa: E402
import informe_t1_beneficios as IB  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
ART = RAIZ / "artefactos"

NOMBRES = {
    "baseline_tasa": "Tasa histórica (programa, k)",
    "lr_pre": "Logística, solo ingreso",
    "lr_acad": "Logística, ingreso + agregados",
    "cb_pre": "CatBoost, solo ingreso",
    "cb_acad": "CatBoost, ingreso + agregados",
    "gru_seq": "GRU, ingreso + secuencia",
}
ORDEN = list(NOMBRES)


def f3(v: float) -> str:
    return f"{v:.3f}"


def con_ic(d: Dict[str, float], dec: int = 3) -> str:
    return f"{d['punto']:.{dec}f} [{d['lo']:.{dec}f}; {d['hi']:.{dec}f}]"


def tabla_modelos(res: Dict, split: str) -> List[str]:
    out = ["| Modelo | AP | ROC-AUC | Brier | ECE | Recall@10% | Precision@10% |", "|---|---|---|---|---|---|---|"]
    for m in ORDEN:
        r = res[split][m]
        out.append(f"| {NOMBRES[m]} | {con_ic(r['ap'])} | {con_ic(r['roc_auc'])} | {con_ic(r['brier'], 4)} | "
                   f"{con_ic(r['ece'])} | {con_ic(r['recall_10'])} | {con_ic(r['precision_10'])} |")
    return out


def tabla_delta(res: Dict, split: str) -> List[str]:
    out = ["| Comparación (diferencia pareada) | ΔAP | ΔROC-AUC | ΔBrier |", "|---|---|---|---|"]
    for m in ORDEN[1:]:
        d = res[split].get(f"__delta__{m}")
        if d:
            out.append(f"| {NOMBRES[m]} − {NOMBRES['baseline_tasa']} | {con_ic(d['ap'])} | {con_ic(d['roc_auc'])} | "
                       f"{con_ic(d['brier'], 4)} |")
    d = res[split].get("__delta_gru_vs_cb_acad")
    if d:
        out.append(f"| {NOMBRES['gru_seq']} − {NOMBRES['cb_acad']} | {con_ic(d['ap'])} | {con_ic(d['roc_auc'])} | "
                   f"{con_ic(d['brier'], 4)} |")
    return out


def tabla_semillas(res: Dict, split: str) -> List[str]:
    out = ["| Modelo (3 semillas) | AP | ROC-AUC | Brier | Recall@10% |", "|---|---|---|---|---|"]
    for m, v in res["semillas"].items():
        s = v[split]
        out.append(f"| {NOMBRES[m]} | {s['ap']['media']:.3f} ± {s['ap']['sd']:.3f} | {s['roc_auc']['media']:.3f} ± "
                   f"{s['roc_auc']['sd']:.3f} | {s['brier']['media']:.4f} ± {s['brier']['sd']:.4f} | "
                   f"{s['recall_10']['media']:.3f} ± {s['recall_10']['sd']:.3f} |")
    return out


def tabla_calibracion(res: Dict, modelos: List[str]) -> List[str]:
    out = ["| Decil de riesgo | " + " | ".join(f"{NOMBRES[m]}: predicho / observado" for m in modelos) + " |",
           "|---|" + "---|" * len(modelos)]
    filas = {m: res["calibracion_test"][m] for m in modelos}
    for i in range(10):
        celdas = []
        for m in modelos:
            t = filas[m]
            r = next((x for x in t if x["decil"] == i + 1), None)
            celdas.append(f"{r['riesgo_medio']:.3f} / {r['tasa_observada']:.3f} (n={r['n']})" if r else "—")
        out.append(f"| {i + 1} | " + " | ".join(celdas) + " |")
    return out


def nombres_programa() -> Dict[str, str]:
    """Program names (institutional catalog, not personal data) from the dev DB; empty if unavailable."""
    try:
        sys.path.insert(0, str(RAIZ))
        from pipelines.common.db import dev_connection

        with dev_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT cod_programa, nombre_programa FROM neural_core.programa")
            return {c: (n or "") for c, n in cur.fetchall()}
    except Exception:
        return {}


PROGRAMAS = nombres_programa()


def tabla_grupo(res: Dict, modelo: str, grupo: str, limite: int = 40) -> List[str]:
    filas = res["subgrupos_test"][modelo][grupo][:limite]
    out = ["| Grupo | n | Tasa observada | Riesgo medio | Brecha calibración | AP | ROC-AUC | Recall@10% | ECE |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in filas:
        etiqueta = f"{r['grupo']} {PROGRAMAS.get(r['grupo'], '')}".strip() if grupo == "programa" else r["grupo"]
        if r["roc_auc"] != r["roc_auc"]:           # no events in the group: ranking metrics undefined
            out.append(f"| {etiqueta} | {r['n']} | {r['tasa_observada']:.3f} | {r['riesgo_medio']:.3f} | "
                       f"{r['brecha_calibracion']:+.3f} | — | — | — | {r['ece']:.3f} |")
            continue
        out.append(f"| {etiqueta} | {r['n']} | {r['tasa_observada']:.3f} | {r['riesgo_medio']:.3f} | "
                   f"{r['brecha_calibracion']:+.3f} | {r['ap']:.3f} | {r['roc_auc']:.3f} | {r['recall_10']:.3f} | "
                   f"{r['ece']:.3f} |")
    return out


def tabla_sexo(res: Dict) -> List[str]:
    out = ["| Modelo | Tasa F | Tasa M | AP F | AP M | ΔAP (F−M) | Recall@10% F−M | Brecha calibración F−M | ECE F−M |",
           "|---|---|---|---|---|---|---|---|---|"]
    for m in ORDEN:
        t = {r["grupo"]: r for r in res["subgrupos_test"][m]["sexo"]}
        g = res["brecha_sexo_test"][m]
        if "F" not in t or "M" not in t:
            continue
        out.append(f"| {NOMBRES[m]} | {t['F']['tasa_observada']:.3f} | {t['M']['tasa_observada']:.3f} | "
                   f"{t['F']['ap']:.3f} | {t['M']['ap']:.3f} | {g['ap']:+.3f} | {g['recall_10']:+.3f} | "
                   f"{g['brecha_calibracion']:+.3f} | {g['ece']:+.3f} |")
    return out


def tabla_ablacion(res: Dict) -> List[str]:
    out = ["| Escalón | Logística AP | CatBoost AP | GRU AP | Logística ROC-AUC | CatBoost ROC-AUC | GRU ROC-AUC |",
           "|---|---|---|---|---|---|---|"]
    t = res["test"]
    g = t["gru_seq"]
    filas = [
        ("1. Solo perfil de ingreso", "lr_pre", "cb_pre", None),
        ("2. + agregados académicos al corte", "lr_acad", "cb_acad", None),
        ("3. + secuencia por semestre (GRU)", None, None, "gru_seq"),
    ]
    for nombre, lr, cb, gr in filas:
        c = [con_ic(t[lr]["ap"]) if lr else "—", con_ic(t[cb]["ap"]) if cb else "—", con_ic(g["ap"]) if gr else "—",
             con_ic(t[lr]["roc_auc"]) if lr else "—", con_ic(t[cb]["roc_auc"]) if cb else "—",
             con_ic(g["roc_auc"]) if gr else "—"]
        out.append(f"| {nombre} | " + " | ".join(c) + " |")
    return out


def tabla_tiempos(res: Dict) -> List[str]:
    out = ["| Modelo | Tiempo de entrenamiento (s) | Notas |", "|---|---|---|"]
    for m in ORDEN:
        nota = ""
        if m == "gru_seq":
            runs = res["info"]["gru_seq"]["semillas"]
            nota = (f"{runs[0]['n_parametros']} parámetros; {runs[0]['dispositivo']}; pico de memoria GPU "
                    f"{max(r['gpu_pico_mb'] for r in runs):.0f} MB; épocas óptimas "
                    f"{[r['mejor_epoca'] for r in runs]}")
        elif m.startswith("cb_"):
            nota = f"3 semillas; iteraciones óptimas {res['info'][m]['mejores_iteraciones']}"
        elif m.startswith("lr_"):
            i = res["info"][m]
            nota = f"C = {i['C']}, class_weight = {i['class_weight']}, {i['n_variables']} columnas"
        out.append(f"| {NOMBRES[m]} | {res['tiempos_s'][m]:.1f} | {nota} |")
    return out


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def bloques(res: Dict, ganador: str) -> Dict[str, str]:
    """Named markdown blocks of one k (used to assemble docs/08_benchmark_t1.md)."""
    nl = "\n"
    b = {
        "n": "; ".join(f"{s}: n = {miles(v['n'])}, eventos = {miles(v['eventos'])} ({100 * v['tasa']:.1f} %)"
                       for s, v in res["n"].items()),
        "test": nl.join(tabla_modelos(res, "test")), "valid": nl.join(tabla_modelos(res, "valid")),
        "delta_test": nl.join(tabla_delta(res, "test")), "delta_valid": nl.join(tabla_delta(res, "valid")),
        "semillas": nl.join(tabla_semillas(res, "test")), "ablacion": nl.join(tabla_ablacion(res)),
        "calibracion": nl.join(tabla_calibracion(res, ["baseline_tasa", "lr_acad", "cb_acad", "gru_seq"])),
        "sexo": nl.join(tabla_sexo(res)), "tiempos": nl.join(tabla_tiempos(res)),
    }
    for g in ("cohorte", "via", "programa"):
        b[g] = nl.join(tabla_grupo(res, ganador, g, limite=60))
    return b


def _coma(texto: str) -> str:
    return texto.replace(".", ",")


def _valor(res: Dict, ruta: str, con_ic_: bool) -> str:
    """``k1.test.cb_acad.ap`` -> metric dict of the aggregate JSON, formatted."""
    _, split, modelo, metrica = ruta.split(".")
    m = res[split]["__delta_gru_vs_cb_acad"][metrica] if modelo == "delta_gru_cb" else res[split][modelo][metrica]
    dec = 4 if metrica == "brier" else 3
    return _coma(con_ic(m, dec) if con_ic_ else f"{m['punto']:.{dec}f}")


def cambios_t1(runs: Dict) -> str:
    """Before / after of the stage B rebuild (admission scores mm_* + test instead of the pct_* percentiles): test metrics of
    the official configuration (train from 2015) and of the sensitivity run (all cohorts)."""
    prev_o, prev_s = CB.cargar_previo("resultados_t1"), CB.cargar_previo("resultados_t1_todos_anios")
    if prev_o is None:       # the stage-B previous results were deleted: keep the table rendered while they existed
        guardado = Path(__file__).resolve().parent / "cambios_t1_etapa_b.md"
        return guardado.read_text(encoding="utf-8").rstrip("\n") if guardado.exists() else "\n".join(CB.sin_previo())
    filas = []
    for etq, previo, nuevo in (("oficial (train desde 2015)", prev_o, runs["o"]), ("sensibilidad (todas las cohortes)", prev_s, runs["s"])):
        if previo is None:
            continue
        for k in ("k1", "k2"):
            a, b = previo["resultados"][k]["test"], nuevo["resultados"][k]["test"]
            for m in ("baseline_tasa", "cb_pre", "lr_acad", "cb_acad", "gru_seq"):
                filas.append((f"{etq}, {k.replace('k', 'k = ')}: AP de test, {NOMBRES[m]}", a[m]["ap"], b[m]["ap"], 3))
            filas.append((f"{etq}, {k.replace('k', 'k = ')}: ROC-AUC de test, {NOMBRES['cb_acad']}", a["cb_acad"]["roc_auc"], b["cb_acad"]["roc_auc"], 3))
            filas.append((f"{etq}, {k.replace('k', 'k = ')}: GRU − CatBoost, ΔAP pareado", a["__delta_gru_vs_cb_acad"]["ap"], b["__delta_gru_vs_cb_acad"]["ap"], 3))
    return "\n".join(CB.tabla(filas))


def documento() -> str:
    import re

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from pares_t1 import tablas as tablas_pares
    from subpoblacion_t1 import tabla as tabla_subpoblacion

    runs = {"o": json.loads((ART / "resultados_t1.json").read_text(encoding="utf-8")),
            "s": json.loads((ART / "resultados_t1_todos_anios.json").read_text(encoding="utf-8"))}
    blq = {(r, k): bloques(runs[r]["resultados"][k], "cb_acad") for r in runs for k in ("k1", "k2")}
    pares = {"o": tablas_pares(""), "s": tablas_pares("_todos_anios")}
    plantilla = (RAIZ / "tools" / "plantilla_t1.md").read_text(encoding="utf-8")
    datos_ben = IB.cargar()
    blq_ben = IB.bloques(datos_ben)

    def sustituir(m) -> str:
        clave = m.group(1)
        if clave.startswith("ben."):                       # section "Beneficios (16-11-2026)"
            return blq_ben[clave[4:]]
        if clave.startswith(("b:v:", "b:ic:")):
            _, tipo, ruta = clave.split(":", 2)
            return IB.valor(datos_ben["ben"], ruta, tipo == "ic")
        if clave.startswith("meta:"):
            return {"snapshot_hash": runs["o"]["snapshot_hash"], "version_codigo": runs["o"]["version_codigo"]}[clave[5:]]
        if clave.startswith(("v:", "ic:")):
            tipo, ruta = clave.split(":", 1)
            r, rest = ruta.split(".", 1)
            return _valor(runs[r]["resultados"][rest.split(".")[0]], rest, tipo == "ic")
        if clave == "cambios":
            return cambios_t1(runs)
        if clave == "subpoblacion":
            return tabla_subpoblacion()
        partes = clave.split(".")
        if partes[0] == "pares":
            return pares[partes[1]][(int(partes[2][1]), partes[3])]
        return blq[(partes[0], partes[1])][partes[2]]

    return re.sub(r"\{\{([^}]+)\}\}", sustituir, plantilla)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["--doc"]:
        (RAIZ / "docs" / "08_benchmark_t1.md").write_text(documento(), encoding="utf-8")
        print("escrito docs/08_benchmark_t1.md")
        return 0
    nombre = sys.argv[1] if len(sys.argv) > 1 else "resultados_t1"
    ganador = sys.argv[2] if len(sys.argv) > 2 else "cb_acad"
    datos = json.loads((ART / f"{nombre}.json").read_text(encoding="utf-8"))
    for clave, res in datos["resultados"].items():
        for nombre_bloque, texto in bloques(res, ganador).items():
            print(f"\n<!--{{{{{clave}.{nombre_bloque}}}}}-->\n{texto}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
