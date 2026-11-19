"""Markdown blocks of the section "Beneficios (16-11-2026)" of docs/10_benchmark_t3.md.

Reads ``artefactos/resultados_t3_beneficios.json`` (``evaluation/run_beneficios_t3.py``), ``diagnostico_beneficios_t3.json`` (the
leakage diagnostic) and the official ``resultados_t3.json`` (reproduction check). Aggregates only; groups of fewer than 10 are
never printed (the runner already suppressed them).

``python tools/informe_t3_beneficios.py --doc`` renders section 11 of ``tools/plantilla_t3.md`` and splices it into
``docs/10_benchmark_t3.md`` (replacing a previous copy of the section), leaving the rest of the document untouched.
``informe_t3.documento()`` substitutes ``{{ben:<block>}}`` with the same blocks.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

RAIZ = Path(__file__).resolve().parents[1]
ART = RAIZ / "artefactos"
MARCA_SECCION = "## 11. Beneficios (16-11-2026)"

FAMILIA = {"lr": "Logística persona-período", "cb": "CatBoost persona-período", "gru": "Red GRU de riesgos discretos"}
BLOQUE = {"acad": "ingreso + agregados (oficial)", "fin": "+ financiamiento", "expcap": "+ expiración y Capstone", "todo": "+ beneficios (todo)"}
REGLA = {"previo": "años anteriores al del corte (regla por defecto)", "con_t": "incluye el año del corte en cortes de fin de año (sensibilidad)"}
CORTE = {"2": "k = 2", "4": "k = 4", "8": "k = 8 (extensión)", "10": "k = 10 (extensión)"}
TIPO_CORTE = {"mitad_de_anio": "mitad de año (AAAA10)", "fin_de_anio": "fin de año (AAAA20)"}
CLASE = {"egreso_siguiente": "egreso en el semestre siguiente", "egreso_posterior": "egreso posterior", "salida": "salida definitiva",
         "censura": "sigue matriculado / censurado"}
TAU = "12"


def coma(t: str) -> str:
    return t.replace(".", ",")


def pct(x: Optional[float], dec: int = 1) -> str:
    return "—" if x is None or x != x else coma(f"{100 * x:.{dec}f}") + " %"


def pp(x: Optional[float], dec: int = 1) -> str:
    return "—" if x is None or x != x else coma(f"{100 * x:+.{dec}f}") + " pp"


def num(x: Optional[float], dec: int = 3, signo: bool = False) -> str:
    if x is None or x != x:
        return "—"
    return coma(f"{x:+.{dec}f}" if signo else f"{x:.{dec}f}")


def ic(d: Optional[Dict], dec: int = 3, signo: bool = False) -> str:
    if not d:
        return "—"
    return f"{num(d['punto'], dec, signo)} [{num(d['lo'], dec, signo)}; {num(d['hi'], dec, signo)}]"


def miles(n) -> str:
    return "—" if n is None else f"{int(n):,}".replace(",", ".")


def nombre(m: str) -> str:
    fam, _, resto = m.partition("_")
    if resto == "acad":
        return f"{FAMILIA[fam]}: {BLOQUE['acad']}"
    regla, _, bloque = resto.rpartition("_")
    return f"{FAMILIA[fam]}: {BLOQUE[bloque]} ({'previo' if regla == 'previo' else 'con año t'})"


def _tabla(cabecera: List[str], filas: List[List[str]]) -> str:
    out = ["| " + " | ".join(cabecera) + " |", "|" + "---|" * len(cabecera)]
    out += ["| " + " | ".join(f) + " |" for f in filas]
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ diagnostic
def tabla_brechas(diag: Dict) -> str:
    """Gap (definitive exit minus still enrolled) in the share with a row / gratuity, year t against year t - 1."""
    filas = []
    for clave, v in diag["por_corte"].items():
        k, _, tipo = clave.partition("_")
        b = v["brecha_salida_menos_censura"]
        if not b:
            continue
        filas.append([CORTE[k[1:]], TIPO_CORTE[tipo], miles(v["n"]),
                      pp(b["fila"]["anio_t"]), pp(b["fila"]["anio_t_menos_1"]), pp(b["gratuidad"]["anio_t"]), pp(b["gratuidad"]["anio_t_menos_1"])])
    return _tabla(["Corte", "Tipo de corte", "Cortes comparables", "Fila de beneficio: brecha año t", "Fila: brecha año t − 1",
                   "Gratuidad: brecha año t", "Gratuidad: brecha año t − 1"], filas)


def tabla_prevalencias(diag: Dict, claves: List[str]) -> str:
    filas = []
    for clave in claves:
        v = diag["por_corte"].get(clave)
        if not v:
            continue
        k, _, tipo = clave.partition("_")
        for clase in ("egreso_siguiente", "egreso_posterior", "salida", "censura"):
            t, t1 = v["anio_t"].get(clase), v["anio_t_menos_1"].get(clase)
            if not t:
                continue
            filas.append([CORTE[k[1:]], TIPO_CORTE[tipo], CLASE[clase], miles(t["n"]), pct(t["expiro"]), pct(t1["expiro"]),
                          pct(t["capstone"]), pct(t1["capstone"])])
    return _tabla(["Corte", "Tipo", "Desenlace posterior", "n", "Expiración, año t", "Expiración, año t − 1", "Capstone, año t",
                   "Capstone, año t − 1"], filas)


def tabla_distribucion(diag: Dict) -> str:
    """Person-year rows with the expiry / Capstone flag by years since admission (9 = nine or more)."""
    d = diag["banderas_por_anios_desde_admision"]
    filas = []
    for a in range(0, 10):
        filas.append([f"{a}" if a < 9 else "9 o más", miles(d["expiro"].get(str(a), 0)), miles(d["capstone"].get(str(a), 0))])
    return _tabla(["Años desde el año de admisión", "Filas con expiración de gratuidad", "Filas con Capstone"], filas)


def tabla_banderas(diag: Dict) -> str:
    filas = []
    for clave, v in diag["por_corte"].items():
        k, _, tipo = clave.partition("_")
        for flag, r in v["bandera_con_monto_anio_t"].items():
            filas.append([CORTE[k[1:]], TIPO_CORTE[tipo], "Expiración de gratuidad" if flag == "expiro" else "Capstone", miles(r["n"]),
                          pct(r["con_monto_sem1"]), pct(r["con_monto_sem2"])])
    return _tabla(["Corte", "Tipo", "Bandera del año t", "Cortes con la bandera", "Con monto en el 1.er semestre", "Con monto en el 2.º semestre"], filas)


# ------------------------------------------------------------------------------------------------ ablation
def tabla_cobertura(res: Dict) -> str:
    filas = []
    for k in res["ks"]:
        r = res["por_k"][str(k)]
        for regla in r["reglas"]:
            c = r["cobertura"][regla]
            filas.append([CORTE[str(k)], regla, miles(r["n"]["train"]), miles(r["n"]["valid"]), miles(r["n"]["test"]), pct(c["train"]),
                          pct(c["valid"]), pct(c["test"]), "no aplicable" if regla in r["no_aplicable"] else "evaluada"])
    return _tabla(["Corte", "Regla", "n train", "n valid", "n test", "Con dato (train)", "Con dato (valid)", "Con dato (test)", "Estado"], filas)


def _modelos(r: Dict, regla: str) -> List[str]:
    out = []
    for fam in r["familias"]:
        out.append(f"{fam}_acad")
        out += [f"{fam}_{regla}_{b}" for b in r["bloques"] if f"{fam}_{regla}_{b}" in r["valid"]]
    return out


def tabla_ablacion(res: Dict, k: str, regla: str) -> str:
    r = res["por_k"][k]
    if regla in r["no_aplicable"]:
        return "_No aplicable: casi ninguna fila del corte tiene datos de beneficios bajo esta regla._"
    filas = []
    for m in _modelos(r, regla):
        filas.append([nombre(m), ic(r["valid"][m][f"c_{TAU}"]), ic(r["test"][m][f"c_{TAU}"]), ic(r["valid"][m]["ibs"], 4), ic(r["test"][m]["ibs"], 4)])
    return _tabla(["Modelo", "C(12) valid", "C(12) test", "IBS valid", "IBS test"], filas)


def tabla_deltas(res: Dict, k: str, regla: str) -> str:
    r = res["por_k"][k]
    if regla in r["no_aplicable"]:
        return "_No aplicable._"
    filas = []
    for fam in r["familias"]:
        base = f"{fam}_acad"
        for b in r["bloques"]:
            m = f"{fam}_{regla}_{b}"
            clave = f"__delta__{m}__{base}"
            if clave not in r["valid"]:
                continue
            cumple = r["decisiones"].get(f"{m}__vs__{base}", {}).get("adopta")
            adoptable = regla == "previo" and int(k) in (2, 4)
            veredicto = "no" if not cumple else ("sí" if adoptable else "sí (solo sensibilidad; no adoptable)")
            filas.append([FAMILIA[fam], BLOQUE[b], ic(r["valid"][clave][f"c_{TAU}"], 3, True), ic(r["valid"][clave]["ibs"], 4, True),
                          ic(r["test"][clave][f"c_{TAU}"], 3, True), ic(r["test"][clave]["ibs"], 4, True), veredicto])
    return _tabla(["Modelo", "Bloque", "ΔC(12) valid", "ΔIBS valid", "ΔC(12) test", "ΔIBS test", "Cumple el criterio estadístico"], filas)


def tabla_decision(res: Dict) -> str:
    """Primary comparison: default rule, the official cuts, every family, blocks 'todo' and 'expcap'."""
    filas = []
    for k in (str(x) for x in res["ks"] if str(x) in ("2", "4")):
        r = res["por_k"][k]
        if "previo" in r["no_aplicable"]:
            filas.append([CORTE[k], "—", "—", "—", "—", "—", "no aplicable (sin datos de beneficios previos al corte)"])
            continue
        for fam in r["familias"]:
            for b in ("todo", "expcap"):
                m, base = f"{fam}_previo_{b}", f"{fam}_acad"
                clave = f"__delta__{m}__{base}"
                if clave not in r["valid"]:
                    continue
                dec = r["decisiones"][f"{m}__vs__{base}"]
                filas.append([CORTE[k], FAMILIA[fam], BLOQUE[b], ic(r["valid"][clave][f"c_{TAU}"], 3, True), ic(r["valid"][clave]["ibs"], 4, True),
                              ic(r["test"][clave][f"c_{TAU}"], 3, True), "adopta" if dec["adopta"] else "no adopta"])
    return _tabla(["Corte", "Modelo", "Bloque", "ΔC(12) valid", "ΔIBS valid", "ΔC(12) test", "Decisión"], filas)


def tabla_reproduccion(res: Dict, oficial: Optional[Dict]) -> str:
    if not oficial:
        return "_Resultados oficiales no disponibles._"
    mapa = {"cb": "dt_cb_agg", "lr": "dt_lr_agg", "gru": "nn_gru"}
    filas = []
    for k in (str(x) for x in res["ks"] if str(x) in ("2", "4")):
        r = res["por_k"][k]
        for fam in r["familias"]:
            a, o = r["test"][f"{fam}_acad"], oficial["por_k"][k]["test"][mapa[fam]]
            filas.append([CORTE[k], FAMILIA[fam], num(o[f"c_{TAU}"]["punto"]), num(a[f"c_{TAU}"]["punto"]), num(o["ibs"]["punto"], 4), num(a["ibs"]["punto"], 4)])
    return _tabla(["Corte", "Modelo", "C(12) test oficial", "C(12) test reentrenado", "IBS test oficial", "IBS test reentrenado"], filas)


def tabla_incidencia(res: Dict, k: str, regla: str) -> str:
    r = res["por_k"][k]
    filas = []
    for tau, v in r["incidencia_media_test"].items():
        fam = "gru" if "gru" in r["familias"] else r["familias"][0]
        m = f"{fam}_{regla}_todo"
        filas.append([f"{tau} semestres", miles(v["n"]), pct(v["observada"]), pct(v.get(f"{fam}_acad")), pct(v.get(m)) if m in v else "—"])
    return _tabla(["Horizonte (desde la admisión)", "n", "Observada", "Predicha, sin beneficios", "Predicha, con beneficios"], filas)


# ------------------------------------------------------------------------------------------------ groups
def tabla_grupos(res: Dict, k: str, regla: str, tipo: str, limite: int = 40) -> str:
    g = res["por_k"][k].get("grupos", {}).get(regla)
    if not g:
        return "_No aplicable._"
    t = g[tipo]
    r = t["resumen"]
    filas = []
    for f in t["filas"][:limite]:
        etiqueta = f.get("nombre", f["grupo"]) if tipo == "programa" else f["grupo"]
        if tipo == "programa":
            etiqueta = f"{f['grupo']} {etiqueta}"
        filas.append([etiqueta, miles(f["n"]), miles(f["eventos"]), pct(f["observada"]), pct(f["predicha_base"]), pct(f["predicha_ben"]),
                      num(f["c_base"]), num(f["c_ben"]), num(f["c_ben"] - f["c_base"], 3, True)])
    cab = ["Grupo", "n", "Egresos ≤ 12", "Observada", "Predicha sin beneficios", "Predicha con beneficios", "C(12) sin", "C(12) con", "ΔC(12)"]
    nota = ("\n\n" + f"Grupos: {r['grupos']}; publicados (n ≥ 100 y al menos 10 egresos): {r['visibles']}; bajo el umbral, no publicados: "
            f"{r['bajo_umbral']}; con menos de 10 episodios, suprimidos: {r['suprimidos_n_menor_10']}.")
    return _tabla(cab, filas) + nota


def bloques(res: Dict, diag: Dict, oficial: Optional[Dict] = None) -> Dict[str, str]:
    b = {"cobertura": tabla_cobertura(res), "diag.brechas": tabla_brechas(diag),
         "diag.prevalencias": tabla_prevalencias(diag, ["k8_fin_de_anio", "k10_fin_de_anio", "k10_mitad_de_anio", "k8_mitad_de_anio"]),
         "diag.banderas": tabla_banderas(diag), "diag.distribucion": tabla_distribucion(diag), "decision": tabla_decision(res), "reproduccion": tabla_reproduccion(res, oficial)}
    for k in (str(x) for x in res["ks"]):
        for regla in res["reglas"]:
            b[f"ablacion.{k}.{regla}"] = tabla_ablacion(res, k, regla)
            b[f"deltas.{k}.{regla}"] = tabla_deltas(res, k, regla)
            b[f"incidencia.{k}.{regla}"] = tabla_incidencia(res, k, regla) if regla not in res["por_k"][k]["no_aplicable"] else "_No aplicable._"
            for tipo in ("programa", "facultad", "sexo", "banda_decil"):
                b[f"grupos.{k}.{regla}.{tipo}"] = tabla_grupos(res, k, regla, tipo)
    return b


def cargar() -> Dict:
    res = json.loads((ART / "resultados_t3_beneficios.json").read_text(encoding="utf-8"))
    diag = json.loads((ART / "diagnostico_beneficios_t3.json").read_text(encoding="utf-8"))
    ruta = ART / "resultados_t3.json"
    oficial = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None
    return {"res": res, "diag": diag, "oficial": oficial}


def valor(clave: str, datos: Dict, blq: Optional[Dict[str, str]] = None) -> str:
    """Value of one marker ``tipo:ruta`` of the template (``ben``, ``bmeta``, ``bd``, ``bv``, ``bdiag``)."""
    res = datos["res"]
    tipo, _, ruta = clave.partition(":")
    if tipo == "ben":
        blq = blq or bloques(res, datos["diag"], datos["oficial"])
        return blq[ruta]
    if tipo == "bmeta":
        return {"hash_beneficios": res["hash_beneficios"], "hash_ext": res["hash_snapshot_ext"],
                "minutos": f"{res['segundos_totales'] / 60:.0f}"}[ruta]
    if tipo == "bd":                       # paired difference: bd:k.split.a.b.metrica
        k, split, a, c, metrica = ruta.split(".")
        return ic(res["por_k"][k][split][f"__delta__{a}__{c}"][metrica], 4 if metrica == "ibs" else 3, True)
    if tipo == "bv":                       # model metric: bv:k.split.modelo.metrica
        k, split, modelo, metrica = ruta.split(".")
        return ic(res["por_k"][k][split][modelo][metrica], 4 if metrica == "ibs" else 3)
    if tipo == "bdiag":                    # diagnostic value: bdiag:corte.anio.clase.indicador
        corte, anio, clase, ind = ruta.split(".")
        return pct(datos["diag"]["por_corte"][corte][anio][clase][ind])
    raise KeyError(clave)


TIPOS = ("ben", "bmeta", "bd", "bv", "bdiag")


def sustituir(texto: str, datos: Dict) -> str:
    blq = bloques(datos["res"], datos["diag"], datos["oficial"])
    return re.sub(r"\{\{((?:%s):[^}]+)\}\}" % "|".join(TIPOS), lambda m: valor(m.group(1), datos, blq), texto)


def seccion_desde_plantilla(datos: Dict) -> str:
    plantilla = (RAIZ / "tools" / "plantilla_t3.md").read_text(encoding="utf-8")
    i = plantilla.index(MARCA_SECCION)
    return sustituir(plantilla[i:], datos).rstrip() + "\n"


def insertar_en_documento(doc: str, seccion: str) -> str:
    """Replace a previous copy of the section (up to the next level-2 heading or the end) or append it."""
    if MARCA_SECCION in doc:
        i = doc.index(MARCA_SECCION)
        m = re.search(r"^## (?!11\.)", doc[i + 3:], re.M)
        j = i + 3 + m.start() if m else len(doc)
        return doc[:i] + seccion + ("\n" + doc[j:] if m else "")
    return doc.rstrip() + "\n\n" + seccion


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    datos = cargar()
    if sys.argv[1:2] == ["--doc"]:
        ruta = RAIZ / "docs" / "10_benchmark_t3.md"
        ruta.write_text(insertar_en_documento(ruta.read_text(encoding="utf-8"), seccion_desde_plantilla(datos)), encoding="utf-8")
        print("seccion 11 escrita en docs/10_benchmark_t3.md")
        return 0
    for nombre_, texto in bloques(datos["res"], datos["diag"], datos["oficial"]).items():
        print(f"\n<!--{{{{ben:{nombre_}}}}}-->\n{texto}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
