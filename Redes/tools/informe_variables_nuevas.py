"""Markdown tables of the ablation of the new variables (``artefactos/ablacion_variables_<t3|t45|t6>.json``).

``python tools/informe_variables_nuevas.py t3|t45|t6`` prints the tables that ``docs/10``, ``11`` and ``12`` quote (aggregates
only). Numbers are never typed by hand: they come from the JSON written by ``evaluation.ablacion_variables``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Optional

RAIZ = Path(__file__).resolve().parents[1]


def _n(x: float, d: int = 3) -> str:
    return "-" if x is None or x != x else f"{x:.{d}f}".replace(".", ",")


def _ic(x: Optional[Dict[str, float]], d: int = 3, signo: bool = True) -> str:
    if not x:
        return "-"
    f = (lambda v: f"{v:+.{d}f}") if signo else (lambda v: f"{v:.{d}f}")
    return f"{f(x['punto'])} [{f(x['lo'])}; {f(x['hi'])}]".replace(".", ",")


def _si(b: bool) -> str:
    return "**sí**" if b else "no"


def tabla_t3(r: Dict) -> str:
    out = []
    for k, v in r.items():
        if not k.isdigit():
            continue
        kept = v["conservado"]
        out.append(f"\n**`k` = {k}** (conservado: `{kept}`; filas valid {v['n']['valid']}, test {v['n']['test']}; reproducción del conservado: "
                   f"diferencia máxima {max(v['reproduccion_max_abs'].values()):.1e}).\n")
        out.append("| Candidato | Columnas nuevas | C(12) valid | ΔC(12) valid (IC 95 %) | ΔIBS valid | C(12) test | ΔC(12) test | ΔC(12) valid sin P58 | ¿D114? |")
        out.append("|---|---|---|---|---|---|---|---|---|")
        out.append(f"| `{kept}` (conservado) | - | {_ic(v['valid'][kept]['c_12'], 3, False)} | - | - | {_ic(v['test'][kept]['c_12'], 3, False)} | - | - | - |")
        for c in v["candidatos"]:
            n = c["nombre"]
            lim = c.get("valid_sin_p58")
            out.append(f"| `{n}` | {c['n_columnas_nuevas']} | {_ic(v['valid'][n]['c_12'], 3, False)} | {_ic(c['delta_c12_valid'])} | "
                       f"{_ic(c['delta_ibs_valid'], 4)} | {_ic(v['test'][n]['c_12'], 3, False)} | {_ic(c['delta_c12_test'])} | "
                       f"{_ic(lim['delta_c12']) if lim else '-'} | {_si(c['gana'])} |")
        out.append(f"\nDecisión D114: **{v['adopta'] or 'sin cambio (se conserva ' + kept + ')'}**.")
    return "\n".join(out)


def tabla_t45(r: Dict) -> str:
    out = []
    for clave, v in r.items():
        if "_k" not in clave:
            continue
        kept = v["conservado"]
        n = v["n"]
        out.append(f"\n**{clave.replace('_k', ' `k` = ')}** (conservado: `{kept}`; valid {n['valid']['n']} filas y {n['valid']['eventos']} eventos, "
                   f"test {n['test']['n']} y {n['test']['eventos']}; diferencia máxima al reentrenar el conservado: "
                   f"{max(v['reproduccion_max_abs'].values()):.1e}).\n")
        out.append("| Candidato | Bloque | AP valid | ΔAP valid (IC 95 %) | ΔAP test (IC 95 %) | ΔAP valid sin P58 | ¿D114? |")
        out.append("|---|---|---|---|---|---|---|")
        out.append(f"| `{kept}` (conservado) | - | {_ic(v['valid'][kept]['ap'], 3, False)} | - | - | - | - |")
        for c in v["candidatos"]:
            lim = c.get("valid_sin_p58")
            gana = _si(c["gana"]) if c["bloque"] else "(referencia)"
            out.append(f"| `{c['nombre']}` | {c['bloque'] or '-'} | {_ic(v['valid'][c['nombre']]['ap'], 3, False)} | {_ic(c['delta_ap_valid'])} | "
                       f"{_ic(c['delta_ap_test'])} | {_ic(lim['delta_ap']) if lim else '-'} | {gana} |")
        out.append(f"\nDecisión D114: **{v['adopta'] or 'sin cambio (se conserva ' + kept + ')'}**.")
    return "\n".join(out)


def tabla_t6(r: Dict) -> str:
    kept = r["conservado"]
    out = [f"Horizonte {r['tau']} semestres; valid {r['valid']['n']} filas y {r['valid']['eventos']} eventos, test {r['test']['n']} y {r['test']['eventos']}; "
           f"eventos de entrenamiento {r['eventos_train']}.\n",
           "| Candidato | Bloque | AP valid | ΔAP valid (IC 95 %) | AP test | ΔAP test (IC 95 %) | ¿D114? |", "|---|---|---|---|---|---|---|",
           f"| `{kept}` (conservado) | - | {_ic(r['valid']['modelos'][kept]['ap'], 3, False)} | - | {_ic(r['test']['modelos'][kept]['ap'], 3, False)} | - | - |"]
    for c in r["candidatos"]:
        out.append(f"| `{c['nombre']}` | {c['bloque']} | {_ic(r['valid']['modelos'][c['nombre']]['ap'], 3, False)} | {_ic(c['delta_ap_valid'])} | "
                   f"{_ic(r['test']['modelos'][c['nombre']]['ap'], 3, False)} | {_ic(c['delta_ap_test'])} | {_si(c['gana'])} |")
    out.append(f"\nDecisión D114: **{r['adopta'] or 'sin cambio (se conserva ' + kept + ')'}**.")
    return "\n".join(out)


def main(argv=None) -> int:
    tarea = (argv or sys.argv[1:] or ["t3"])[0]
    r = json.loads((RAIZ / "artefactos" / f"ablacion_variables_{tarea}.json").read_text(encoding="utf-8"))
    print({"t3": tabla_t3, "t45": tabla_t45, "t6": tabla_t6}[tarea](r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
