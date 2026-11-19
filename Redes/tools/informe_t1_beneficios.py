"""Markdown blocks of the section "Beneficios (16-11-2026)" of docs/08_benchmark_t1.md.

Reads ``artefactos/resultados_t1_beneficios.json`` (the ablation, ``evaluation/run_beneficios_t1.py``), the official
``resultados_t1.json`` (for the reproduction check) and ``diagnostico_beneficios_t1.json`` (the leakage diagnostic). Aggregates
only. ``informe_t1.documento()`` calls ``bloques()`` and substitutes ``{{ben.<block>}}`` and ``{{b:v|ic:k2.test.cb_ben.ap}}``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

RAIZ = Path(__file__).resolve().parents[1]
ART = RAIZ / "artefactos"

NOMBRES = {
    "baseline_tasa": "Tasa histórica (programa, k)",
    "lr_acad": "Logística, ingreso + agregados",
    "lr_ben": "Logística, + beneficios",
    "lr_ben_perd": "Logística, + beneficios + pérdidas",
    "cb_acad": "CatBoost, ingreso + agregados",
    "cb_ben": "CatBoost, + beneficios",
    "cb_ben_perd": "CatBoost, + beneficios + pérdidas",
}
ORDEN = list(NOMBRES)
ETIQUETA_COLUMNA = {"tiene_fila": "Con fila de beneficio", "grat": "Con gratuidad", "cred": "Con crédito (CAE o FSCU)",
                    "s1_pos": "Monto 1.er semestre > 0", "s2_pos": "Monto 2.º semestre > 0"}


def coma(t: str) -> str:
    return t.replace(".", ",")


def pct(x: Optional[float], dec: int = 1) -> str:
    return "—" if x is None or x != x else coma(f"{100 * x:.{dec}f}") + " %"


def punto(x: Optional[float], dec: int = 3, signo: bool = False) -> str:
    if x is None or x != x:
        return "—"
    return coma(f"{x:+.{dec}f}" if signo else f"{x:.{dec}f}")


def con_ic(d: Optional[Dict], dec: int = 3, signo: bool = False) -> str:
    if not d:
        return "—"
    return f"{punto(d['punto'], dec, signo)} [{punto(d['lo'], dec, signo)}; {punto(d['hi'], dec, signo)}]"


def miles(n: Optional[int]) -> str:
    return "—" if n is None else f"{n:,}".replace(",", ".")


# ------------------------------------------------------------------------------------------------ result blocks
def tabla_modelos(res: Dict, split: str) -> str:
    out = ["| Modelo | AP | ROC-AUC | Brier | ECE |", "|---|---|---|---|---|"]
    for m in ORDEN:
        r = res[split].get(m)
        if r:
            out.append(f"| {NOMBRES[m]} | {con_ic(r['ap'])} | {con_ic(r['roc_auc'])} | {con_ic(r['brier'], 4)} | {con_ic(r['ece'])} |")
    return "\n".join(out)


def tabla_deltas(res: Dict, split: str) -> str:
    pares = [("lr_ben", "lr_acad"), ("cb_ben", "cb_acad"), ("lr_ben_perd", "lr_ben"), ("cb_ben_perd", "cb_ben"),
             ("lr_ben_perd", "lr_acad"), ("cb_ben_perd", "cb_acad")]
    out = ["| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier |", "|---|---|---|---|"]
    for a, b in pares:
        d = res[split].get(f"{a}__vs__{b}")
        if d:
            out.append(f"| {NOMBRES[a]} − {NOMBRES[b]} | {con_ic(d['ap'], 3, True)} | {con_ic(d['roc_auc'], 3, True)} | "
                       f"{con_ic(d['brier'], 4, True)} |")
    return "\n".join(out)


def tabla_seleccion(res: Dict) -> str:
    s = res["seleccion"]
    el = ", ".join(NOMBRES[m] for m in s["elegibles"])
    cert = "sí" if s["beneficios_certificables"] else "no (el corte es a mitad de año; §14.2)"
    return (f"- Modelos elegibles en valid: {el}.\n- ¿Se pueden elegir modelos con beneficios?: {cert}.\n"
            f"- **Modelo conservado (mayor AP en valid entre los elegibles): {NOMBRES[s['conservado']]}** "
            f"(AP de valid {punto(s['ap_valid'][s['conservado']])}).")


def tabla_antes_despues(res: Dict, oficial: Optional[Dict]) -> str:
    """Official model (CatBoost / logistic without benefits) against the same model with benefits, valid and test."""
    out = ["| Modelo | Partición | AP sin beneficios | AP con beneficios | ΔAP pareado | ROC-AUC sin → con | Brier sin → con | ECE sin → con |",
           "|---|---|---|---|---|---|---|---|"]
    for fam, nombre in (("cb", "CatBoost"), ("lr", "Logística")):
        for split in ("valid", "test"):
            a, b = res[split][f"{fam}_acad"], res[split][f"{fam}_ben"]
            d = res[split].get(f"{fam}_ben__vs__{fam}_acad")
            out.append(f"| {nombre} | {split} | {con_ic(a['ap'])} | {con_ic(b['ap'])} | {con_ic(d['ap'], 3, True) if d else '—'} | "
                       f"{punto(a['roc_auc']['punto'])} → {punto(b['roc_auc']['punto'])} | "
                       f"{punto(a['brier']['punto'], 4)} → {punto(b['brier']['punto'], 4)} | "
                       f"{punto(a['ece']['punto'])} → {punto(b['ece']['punto'])} |")
    return "\n".join(out)


def reproduccion(res: Dict, oficial: Optional[Dict], k: int) -> str:
    """The official run (``resultados_t1.json``) against the matched retraining of this run, same model without benefits."""
    if not oficial:
        return "—"
    o = oficial["resultados"][f"k{k}"]["test"]
    out = ["| Modelo (test) | AP corrida oficial | AP reentrenado en esta corrida | Diferencia |", "|---|---|---|---|"]
    for m in ("cb_acad", "lr_acad"):
        a, b = o[m]["ap"]["punto"], res["test"][m]["ap"]["punto"]
        out.append(f"| {NOMBRES[m]} | {punto(a)} | {punto(b)} | {punto(b - a, 3, True)} |")
    return "\n".join(out)


def tabla_importancia(res: Dict, modelo: str) -> str:
    imp = (res.get("importancia") or {}).get(modelo)
    if not imp:
        return "—"
    out = [f"{NOMBRES[modelo]}: promedio de {imp['semillas']} semillas; SHAP sobre {miles(imp['n_muestra_shap'])} filas de prueba "
           f"(aleatorias, semilla fija).", "",
           "| Rango | Variable | Importancia (%) | |SHAP| medio |", "|---|---|---|---|"]
    for r in imp["top"]:
        marca = " (beneficio)" if r["variable"] in _BEN else ""
        out.append(f"| {r['rango']} | `{r['variable']}`{marca} | {punto(r['importancia_pct'], 1)} | {punto(r['shap_medio_abs'], 3)} |")
    ya = {r["variable"] for r in imp["top"]}
    resto = [r for r in imp["beneficios"] if r["variable"] not in ya]
    if resto:
        out += ["", "Variables de beneficios fuera de las primeras posiciones:", "", "| Rango | Variable | Importancia (%) | |SHAP| medio |",
                "|---|---|---|---|"]
        out += [f"| {r['rango']} | `{r['variable']}` | {punto(r['importancia_pct'], 2)} | {punto(r['shap_medio_abs'], 3)} |" for r in resto]
    out += ["", f"Suma de la importancia de las variables de beneficios: {punto(imp['suma_pct_beneficios'], 1)} %."]
    return "\n".join(out)


_BEN = {"ben_sin_dato", "tiene_gratuidad", "tiene_credito", "tiene_beca_estatal", "tiene_beca_ucn", "merito_ingreso", "merito_e1",
        "expiro_gratuidad", "etapa_capstone", "n_beneficios", "monto_sem1", "banda_decil", "perdida_sin_dato", "perdio_gratuidad",
        "perdio_credito", "perdio_cualquier_beneficio", "obtuvo_gratuidad"}


def tabla_grupos(res: Dict, nivel: str, limite: int = 80) -> str:
    bloque = res["grupos"][nivel]
    filas = bloque["filas"][:limite]
    r = bloque["resumen"]
    out = [f"Modelo conservado: {NOMBRES[res['seleccion']['conservado']]}; prueba. Se listan {r['grupos_reportables']} de "
           f"{r['grupos_total']} grupos (n ≥ {r['n_min']} y ≥ {r['eventos_min']} eventos); los demás se suprimen.", "",
           "| Grupo | n | Eventos | Tasa observada | Riesgo medio | Brecha (predicho − observado) | AP |", "|---|---|---|---|---|---|---|"]
    for f in filas:
        nombre = f"{f['grupo']} {f['nombre']}" if f.get("nombre") and nivel == "programa" else (f.get("nombre") or f["grupo"])
        ap = punto(f["ap"]) if f["ap"] == f["ap"] else "—"
        out.append(f"| {nombre} | {miles(f['n'])} | {miles(f['eventos'])} | {pct(f['tasa_observada']['punto'])} | "
                   f"{pct(f['riesgo_medio']['punto'])} | {con_ic(f['brecha'], 3, True)} | {ap} |")
    if "mae_modelo" in r:
        out += ["", f"Error absoluto medio ponderado de la tasa del grupo: modelo {con_ic(r['mae_modelo'])}, tasa histórica "
                    f"{con_ic(r['mae_base'])}; correlación de Spearman entre riesgo medio y tasa observada: {con_ic(r['spearman_modelo'])}."]
    return "\n".join(out)


def tabla_equidad(res: Dict, columna: str) -> str:
    eq = res["equidad"][columna]
    out = ["| Grupo | Modelo | n | Tasa observada | Riesgo medio | Brecha de calibración | AP | Recall@10% |", "|---|---|---|---|---|---|---|---|"]
    for m in eq:
        for r in eq[m]:
            ap = punto(r["ap"]) if r["ap"] == r["ap"] else "—"
            rec = punto(r["recall_10"]) if r["recall_10"] == r["recall_10"] else "—"
            out.append(f"| {r['grupo']} | {NOMBRES[m]} | {miles(r['n'])} | {pct(r['tasa_observada'])} | {pct(r['riesgo_medio'])} | "
                       f"{punto(r['brecha_calibracion'], 3, True)} | {ap} | {rec} |")
    return "\n".join(out)


def resumen_n(res: Dict) -> str:
    return "; ".join(f"{s}: n = {miles(v['n'])}, eventos = {miles(v['eventos'])} ({pct(v['tasa'])})" for s, v in res["n"].items())


# ------------------------------------------------------------------------------------------------ diagnostic blocks
def diag_presencia(diag: Dict) -> str:
    cols = diag["columnas"]
    out = ["| k | Grupo | n | " + " | ".join(ETIQUETA_COLUMNA[c] for c in cols) + " |", "|---|---|---|" + "---|" * len(cols)]
    for r in diag["presencia_por_resultado"]:
        for nombre, etq in (("continua", "Continúa"), ("no_continua", "No continúa")):
            g = r[nombre]
            if g:
                out.append(f"| {r['k']} | {etq} | {miles(g['n'])} | " + " | ".join(pct(g[c]) for c in cols) + " |")
        if r["brecha"]:
            out.append(f"| {r['k']} | **Brecha (continúa − no continúa)** | | " + " | ".join(
                coma(f"{100 * r['brecha'][c]:+.1f}") + " pp" for c in cols) + " |")
    return "\n".join(out)


def diag_salida_anio(diag: Dict) -> str:
    s = diag["salida_en_el_anio"]
    cols = diag["columnas"]
    out = ["| Grupo (ingreso en el primer semestre, k = 1) | n | " + " | ".join(ETIQUETA_COLUMNA[c] for c in cols) + " |",
           "|---|---|" + "---|" * len(cols)]
    for nombre, etq in (("se_queda", "Sigue matriculado en el segundo semestre"), ("sale", "Sale durante el año de ingreso")):
        g = s[nombre]
        out.append(f"| {etq} | {miles(g['n']) if g else '< 30'} | " + (" | ".join(pct(g[c]) for c in cols) if g else "—") + " |")
    if s["brecha"]:
        out.append("| **Brecha** | | " + " | ".join(coma(f"{100 * s['brecha'][c]:+.1f}") + " pp" for c in cols) + " |")
    return "\n".join(out)


def diag_historia(diag: Dict) -> str:
    h = diag.get("historia_cargas")
    if not h:
        return "No disponible: el historial de cargas necesita acceso de solo lectura al almacén."
    out = ["| Año | Filas en la última carga | Filas cargadas al corte (fin 1.er semestre) | Filas que aún no estaban al corte | "
           "Filas retiradas después del corte | Filas agregadas después del corte | Filas retiradas después del cierre (nov.) | "
           "Montos del 2.º semestre anulados después del cierre |", "|---|---|---|---|---|---|---|---|"]
    for a, r in sorted(h.items()):
        c, z = r["cambios_desde_el_corte"], r["cambios_desde_el_cierre"]
        out.append(f"| {a} | {miles(r['filas_final'])} | {miles(r['filas_en_el_corte'])} ({r['fecha_corte']}) | "
                   f"{pct(r['filas_tardias_despues_del_corte'])} | {miles(c['retiradas'])} ({pct(c['retiradas'] / c['filas_a'])}) | "
                   f"{miles(c['agregadas'])} | {miles(z['retiradas'])} ({pct(z['retiradas'] / z['filas_a'])}) | "
                   f"{pct(r['sem2_anulado_despues_del_cierre'])} |")
    return "\n".join(out)


def diag_retiradas(diag: Dict) -> str:
    h = diag.get("historia_cargas")
    if not h:
        return "—"
    out = ["| Año | k | Con alguna fila retirada después del corte: n | No continuidad | Resto: n | No continuidad |", "|---|---|---|---|---|---|"]
    for a, r in sorted(h.items()):
        x = r["retiradas_y_continuidad"]
        for k in ("k1", "k2", "k4"):
            if k in x:
                c, o = x[k]["con_fila_retirada"], x[k]["resto"]
                out.append(f"| {a} | {k[1:]} | {miles(c['n'])} | {pct(c['tasa_no_continuidad'])} | {miles(o['n'])} | "
                           f"{pct(o['tasa_no_continuidad'])} |")
    return "\n".join(out)


def tabla_sensibilidad(sens: Dict, clave: str, ks: List[str]) -> str:
    out = ["| k | Entrenamiento | n train / valid / test | AP CatBoost sin → con beneficios (test) | ΔAP pareado CatBoost (valid) | "
           "ΔAP pareado CatBoost (test) | ΔAP pareado logística (test) |", "|---|---|---|---|---|---|---|"]
    for k in ks:
        r = (sens.get(clave) or {}).get(k)
        if not r:
            continue
        t, v = r["test"], r["valid"]
        n = " / ".join(miles(r["n"][s]["n"]) for s in ("train", "valid", "test"))
        etq = "cohortes desde 2017" if clave == "desde_2017" else "sin las salidas durante el año de ingreso"
        out.append(f"| {k[1:]} | {etq} | {n} | {punto(t['cb_acad']['ap']['punto'])} → {punto(t['cb_ben']['ap']['punto'])} | "
                   f"{con_ic(v.get('cb_ben__vs__cb_acad', {}).get('ap'), 3, True)} | "
                   f"{con_ic(t.get('cb_ben__vs__cb_acad', {}).get('ap'), 3, True)} | "
                   f"{con_ic(t.get('lr_ben__vs__lr_acad', {}).get('ap'), 3, True)} |")
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ assembly
def cargar() -> Dict:
    def leer(nombre: str) -> Optional[Dict]:
        p = ART / nombre
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    return {"ben": leer("resultados_t1_beneficios.json"), "oficial": leer("resultados_t1.json"),
            "diag": leer("diagnostico_beneficios_t1.json")}


def bloques(datos: Dict) -> Dict[str, str]:
    ben, oficial, diag = datos["ben"], datos["oficial"], datos["diag"]
    b: Dict[str, str] = {}
    if diag:
        b.update({"diag_presencia": diag_presencia(diag), "diag_salida_anio": diag_salida_anio(diag),
                  "diag_historia": diag_historia(diag), "diag_retiradas": diag_retiradas(diag)})
    if not ben:
        return b
    res = ben["resultados"]
    for k, r in res.items():
        b[f"{k}.n"] = resumen_n(r)
        b[f"{k}.test"], b[f"{k}.valid"] = tabla_modelos(r, "test"), tabla_modelos(r, "valid")
        b[f"{k}.delta_test"], b[f"{k}.delta_valid"] = tabla_deltas(r, "test"), tabla_deltas(r, "valid")
        b[f"{k}.seleccion"] = tabla_seleccion(r)
        b[f"{k}.antes_despues"] = tabla_antes_despues(r, oficial)
        if oficial and k in ("k1", "k2"):
            b[f"{k}.reproduccion"] = reproduccion(r, oficial, int(k[1:]))
        for m in ("cb_ben", "cb_ben_perd"):
            if m in (r.get("importancia") or {}):
                b[f"{k}.importancia.{m}"] = tabla_importancia(r, m)
        b[f"{k}.programa"], b[f"{k}.facultad"] = tabla_grupos(r, "programa"), tabla_grupos(r, "facultad")
        b[f"{k}.equidad_banda"], b[f"{k}.equidad_sexo"] = tabla_equidad(r, "banda_decil"), tabla_equidad(r, "sexo")
    ks = list(res)
    b["sens_2017"] = tabla_sensibilidad(ben["sensibilidad"], "desde_2017", ks)
    b["sens_sin_salidas"] = tabla_sensibilidad(ben["sensibilidad"], "sin_salidas_en_el_anio", ks)
    return b


def valor(ben: Dict, ruta: str, con_intervalo: bool) -> str:
    """``k2.test.cb_ben.ap`` -> a metric of the ablation JSON (``punto`` or ``punto [lo; hi]``, Spanish decimal comma)."""
    sens = {"sin_salidas": "sin_salidas_en_el_anio", "desde_2017": "desde_2017"}
    partes = ruta.split(".")
    if partes[0] in sens:                                   # ``sin_salidas.k1.test.<modelo>.<metrica>``
        bloque = ben["sensibilidad"][sens[partes[0]]]
        partes = partes[1:]
    else:
        bloque = ben["resultados"]
    k, split, modelo, metrica = partes
    m = bloque[k][split][modelo][metrica]
    dec = 4 if metrica == "brier" else 3
    signo = "__vs__" in modelo
    return con_ic(m, dec, signo) if con_intervalo else punto(m["punto"], dec, signo)
