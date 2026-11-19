"""Ablation of the new variables of T3-T6 under the selection rule D114 (docs/00_plan.md).

``python -m evaluation.ablacion_variables --tarea t3|t45|t6`` retrains, for every task and cut, the family of the KEPT model
with its same inputs plus a pre-specified block of new variables (``models.vars_nuevas_data.BLOQUES``) and compares it with the
kept model's SAVED predictions on VALID (paired bootstrap; T3 episodes, T4 / T5 / T6 persons). D114: a candidate replaces the
kept model only if its paired valid difference in the headline metric (T3: C(12), with an IBS that is not worse with an
interval above zero; T4, T5, T6: AP) has an interval that excludes zero in its favour; test only confirms; ties keep the
simpler model. Besides the formal rule, every candidate is also evaluated on the valid rows WITHOUT a semester in the periods
without recorded failures (P58): the failure-based variables are lower bounds there, so a gain that only exists on the exposed
rows is not trusted.

Never writes ``artefactos/preds/t*_k*`` (the kept predictions): candidates go to ``artefactos/preds/abl_*.npz`` and the
aggregates to ``artefactos/ablacion_variables_<tarea>.json`` (gitignored). Dev DB credentials in ``DEV_*``.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from evaluation import metrics_t3 as M3
from evaluation import metrics_t45 as M45
from evaluation import metrics_t6 as M6
from models import seguimiento as S
from models import vars_nuevas_data as VD
from models.data import Preprocesador

SEMILLAS = (0, 1, 2)
BOOT = 1000


# ---------------------------------------------------------------------------------------------
# D114 decision helpers (pure)
# ---------------------------------------------------------------------------------------------
def _num(x: Optional[Dict[str, float]], clave: str) -> float:
    return float("nan") if not x else float(x.get(clave, float("nan")))


def decidir_ap(delta: Optional[Dict[str, float]]) -> bool:
    """The candidate wins only if the interval of the paired difference lies above zero."""
    lo = _num(delta, "lo")
    return bool(lo == lo and lo > 0)


def decidir_t3(delta_c: Optional[Dict[str, float]], delta_ibs: Optional[Dict[str, float]]) -> bool:
    """T3: C(12) interval above zero and an IBS that is NOT worse with an interval above zero (lower IBS is better)."""
    if not decidir_ap(delta_c):
        return False
    lo_ibs = _num(delta_ibs, "lo")
    return not (lo_ibs == lo_ibs and lo_ibs > 0)


def elegir(candidatos: Sequence[Dict]) -> Optional[Dict]:
    """Among the winning candidates the one with the best valid point estimate (``None`` if no one wins)."""
    g = [c for c in candidatos if c["gana"]]
    return max(g, key=lambda c: c["valid_punto"]) if g else None


_BLOQUE = {"t4": 0, "reg_alc": 0, "cred": 0, "alc": 0, "tit": 0, "t3": 1, "todo": 2}


def complejidad(nombre: str):
    """Order of simplicity of a candidate ``<family>_<group>+<block>`` (D114: logistic < CatBoost < network, then the block)."""
    base, _, bloque = nombre.partition("+")
    familia = 2 if ("gru" in base or base.startswith("nn_")) else 1 if "cb" in base else 0
    return (familia, _BLOQUE.get(bloque, 3))


def refinar_por_simplicidad(mejor: str, ganadores: Sequence[str], delta: Callable[[str, str], Optional[Dict[str, float]]]) -> str:
    """D114, ties to the simpler: starting from the best winner on valid, move to a SIMPLER winner whenever the paired valid
    difference ``best - simpler`` does not have an interval above zero. ``delta(a, b)`` is the paired difference ``a - b``."""
    actual = mejor
    for s in sorted((g for g in ganadores if complejidad(g) < complejidad(mejor)), key=complejidad):
        if complejidad(s) < complejidad(actual) and not decidir_ap(delta(actual, s)):
            actual = s
    return actual


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def _alinear(ids: np.ndarray, z, clave: str) -> np.ndarray:
    pos = pd.Series(np.arange(len(z["episodio_id"])), index=z["episodio_id"]).reindex(ids)
    if pos.isna().any():
        raise RuntimeError("saved predictions do not cover the rows: rerun the benchmark runner")
    return z[clave][pos.to_numpy().astype(int)]


def _conservado(ruta: str, ids: np.ndarray, clave: str) -> np.ndarray:
    z = np.load(S.ARTEFACTOS / "preds" / ruta)
    return _alinear(ids, z, clave).astype("float64")


def _guardar(nombre: str, ids: np.ndarray, datos: Dict[str, np.ndarray]) -> None:
    (S.ARTEFACTOS / "preds").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(S.ARTEFACTOS / "preds" / f"abl_{nombre}.npz", episodio_id=ids,
                        **{k: v.astype("float32") for k, v in datos.items()})


def _cols(tr: pd.DataFrame, bloque: str) -> List[str]:
    cols = VD.columnas_validas(tr, VD.BLOQUES[bloque])
    VD.verificar_sin_fuga_nuevas(cols)
    return cols


# ---------------------------------------------------------------------------------------------
# T3
# ---------------------------------------------------------------------------------------------
KEPT_T3 = {0: ("dt_lr_adm", "lr", "adm"), 2: ("nn_gru", "gru", "adm+agg"), 4: ("nn_gru", "gru", "adm+agg")}
BLOQUES_T3 = ("t3", "cred", "alc", "tit")


def _entrenar_t3(familia: str, num: List[str], cat: List[str], parts, sem, k: int, seeds, dev) -> Dict[str, np.ndarray]:
    from models import t3_data as TD
    from models import t3_discreto as DT
    from models import t3_redes as NR

    tr, va = parts["train"], parts["valid"]
    prep = Preprocesador(num, cat).fit(tr)
    if familia == "lr":
        m, _ = DT.logistica_ajustar(prep, tr, va, k)
        return {s: DT.logistica_cif(m, prep, parts[s], k) for s in ("valid", "test")}
    U = TD.JMAX - k
    seq = {s: TD.construir_secuencias_t3(parts[s], sem, k) for s in ("train", "valid", "test")}

    def conj(d, s):
        return NR.ConjuntoT3(prep.transform_num(d), prep.transform_cat_codes(d), d["u"].to_numpy(), d["causa"].to_numpy(), seq[s])

    ctr, cva = conj(tr, "train"), conj(va, "valid")
    cjs = {s: conj(parts[s], s) for s in ("valid", "test")}
    acc = {s: [] for s in cjs}
    for sd in seeds:
        r = NR.entrenar(ctr, cva, prep.cardinalidades(), U, sd, dev)
        for s in cjs:
            acc[s].append(NR.predecir_cif(r["model"], cjs[s], dev))
        del r
    return {s: np.mean(v, axis=0) for s, v in acc.items()}


def _evaluar_t3(parts, k: int, preds: Dict[str, Dict[str, np.ndarray]], kept: str, nombres: List[str], boot: int,
                filas_limpias: Optional[Dict[str, np.ndarray]] = None) -> Dict:
    from models import t3_data as TD   # noqa: F401
    from evaluation.run_t3 import HORIZONTES, IBS_HASTA

    slots = np.arange(k + 1, 20 + 1)
    out: Dict = {}
    for sp in ("valid", "test"):
        d = parts[sp]
        idx = np.arange(len(d)) if filas_limpias is None else np.flatnonzero(filas_limpias[sp])
        if len(idx) == 0:
            continue
        pares = [(c, kept) for c in nombres]
        import torch

        dispositivo = "cuda" if torch.cuda.is_available() else None       # the numpy backend is too slow for 1000 resamples
        ev = M3.Evaluador(d["tiempo"].to_numpy()[idx], d["causa"].to_numpy()[idx], d["seguimiento_max"].to_numpy()[idx], slots,
                          {m: preds[sp][m][idx] for m in [kept, *nombres]}, HORIZONTES[sp], IBS_HASTA[sp],
                          backend="torch" if dispositivo else "numpy", device=dispositivo)
        out[sp] = ev.bootstrap(n_boot=boot, seed=7, pares=pares)
        out[sp]["__n"] = int(len(idx))
    return out


def ablacion_t3(conn, boot: int, seeds, log: Callable[[str], None]) -> Dict:
    import torch

    from models import t3_data as TD

    snap, sem = TD.cargar(conn)
    v3, _ = VD.cargar_nuevas(conn)
    snap = VD.unir(snap, v3)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    res: Dict = {}
    for k, (kept, familia, grupo) in KEPT_T3.items():
        t0 = time.perf_counter()
        parts = TD.particion(snap, k)
        num0, cat = TD.GRUPOS[grupo]
        TD.verificar_sin_fuga(num0, cat)
        ids = {s: parts[s]["episodio_id"].to_numpy() for s in ("valid", "test")}
        preds: Dict[str, Dict[str, np.ndarray]] = {s: {kept: _conservado(f"t3_k{k}_{s}.npz", ids[s], kept)} for s in ("valid", "test")}
        base = _entrenar_t3(familia, list(num0), list(cat), parts, sem, k, seeds, dev)
        for s in ("valid", "test"):
            preds[s][f"{kept}__reentrenado"] = base[s]
        reprod = {s: float(np.nanmax(np.abs(preds[s][f"{kept}__reentrenado"] - preds[s][kept]))) for s in ("valid", "test")}
        log(f"T3 k={k}: {kept} reentrenado, diferencia maxima con lo guardado {reprod}")
        nombres = []
        info: Dict[str, Dict] = {}
        for bloque in BLOQUES_T3:
            extra = _cols(parts["train"], bloque)
            if not extra:
                continue
            nombre = f"{kept}+{bloque}"
            F = _entrenar_t3(familia, [*num0, *extra], list(cat), parts, sem, k, seeds, dev)
            for s in ("valid", "test"):
                preds[s][nombre] = F[s]
            nombres.append(nombre)
            info[nombre] = {"bloque": bloque, "familia": familia, "n_columnas_nuevas": len(extra), "columnas": extra}
            log(f"T3 k={k}: {nombre} listo ({time.perf_counter() - t0:.0f} s)")
        ev = _evaluar_t3(parts, k, preds, kept, nombres, boot)
        limpio = {s: (parts[s]["n_sem_sin_reprobacion"].to_numpy() == 0) for s in ("valid", "test")}
        ev_limpio = _evaluar_t3(parts, k, preds, kept, nombres, boot, limpio)
        cands = []
        for n in nombres:
            dC = ev["valid"][f"__delta__{n}__{kept}"]["c_12"]
            dI = ev["valid"][f"__delta__{n}__{kept}"]["ibs"]
            gana = decidir_t3(dC, dI)
            lim = ev_limpio.get("valid", {}).get(f"__delta__{n}__{kept}")
            cands.append({"nombre": n, **info[n], "gana": gana, "valid_punto": ev["valid"][n]["c_12"]["punto"],
                          "delta_c12_valid": dC, "delta_ibs_valid": dI,
                          "delta_c12_test": ev["test"][f"__delta__{n}__{kept}"]["c_12"],
                          "delta_ibs_test": ev["test"][f"__delta__{n}__{kept}"]["ibs"],
                          "valid_sin_p58": None if lim is None else {"n": ev_limpio["valid"]["__n"], "delta_c12": lim["c_12"], "delta_ibs": lim["ibs"]}})
        elegido = elegir(cands)
        res[str(k)] = {"conservado": kept, "reproduccion_max_abs": reprod,
                       "valid": {kept: ev["valid"][kept], **{n: ev["valid"][n] for n in nombres}},
                       "test": {kept: ev["test"][kept], **{n: ev["test"][n] for n in nombres}},
                       "candidatos": cands, "adopta": None if elegido is None else elegido["nombre"],
                       "n": {s: int(len(parts[s])) for s in ("train", "valid", "test")}, "segundos": time.perf_counter() - t0}
        for s in ("valid", "test"):
            _guardar(f"t3_k{k}_{s}", ids[s], {n: preds[s][n] for n in nombres})
        log(f"T3 k={k}: adopta={res[str(k)]['adopta']}")
    return res


# ---------------------------------------------------------------------------------------------
# T4 / T5
# ---------------------------------------------------------------------------------------------
KEPT_T45 = {("T4", 2): ("lr_agg", "lr", "adm+agg"), ("T4", 4): ("cb_agg", "cb", "adm+agg"),
            ("T5", 2): ("gru_adm", "gru", "adm"), ("T5", 4): ("gru_agg", "gru", "adm+agg")}
BLOQUES_T45 = {"T4": ("t4", "todo"), "T5": ("reg_alc", "todo")}
FAMILIAS_EXTRA = (("lr_agg", "lr", "adm+agg"), ("cb_agg", "cb", "adm+agg"))


def _entrenar_t45(familia: str, num: List[str], cat: List[str], parts, sem, k: int, col: str, seeds, dev) -> Dict[str, np.ndarray]:
    from models import catboost_modelo, gru as G, logistica
    from models import t45_data as TD

    tr, va, te = parts["train"], parts["valid"], parts["test"]
    ytr, yva = tr[col].to_numpy(), va[col].to_numpy()
    prep = Preprocesador(num, cat).fit(tr)
    if familia == "lr":
        m, _ = logistica.ajustar(prep.transform(tr), ytr, prep.transform(va), yva)
        return {"valid": m.predict_proba(prep.transform(va))[:, 1], "test": m.predict_proba(prep.transform(te))[:, 1]}
    if familia == "cb":
        Ctr, Cva, Cte = (prep.transform_catboost(x) for x in (tr, va, te))
        av, at = [], []
        for s in seeds:
            cb, _ = catboost_modelo.ajustar(Ctr, ytr, Cva, yva, cat, seed=s)
            av.append(catboost_modelo.predecir(cb, Cva, cat))
            at.append(catboost_modelo.predecir(cb, Cte, cat))
        return {"valid": np.mean(av, axis=0), "test": np.mean(at, axis=0)}
    seqs = [TD.construir_secuencias_t45(x, sem, k) for x in (tr, va, te)]
    conj = [G.Conjunto(s_, prep.transform_num(x), prep.transform_cat_codes(x), x[col].to_numpy()) for s_, x in zip(seqs, (tr, va, te))]
    av, at = [], []
    for s in seeds:
        r = G.entrenar(conj[0], conj[1], prep.cardinalidades(), seed=s, device=dev)
        av.append(G.predecir(r["model"], conj[1], dev))
        at.append(G.predecir(r["model"], conj[2], dev))
        del r
    return {"valid": np.mean(av, axis=0), "test": np.mean(at, axis=0)}


def ablacion_t45(conn, boot: int, seeds, log: Callable[[str], None]) -> Dict:
    import torch

    from models import t45_data as TD

    snap, sem = TD.cargar(conn)
    v3, _ = VD.cargar_nuevas(conn)
    snap = VD.unir(snap, v3)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    res: Dict = {}
    for (tgt, k), (kept, fam_k, grupo_k) in KEPT_T45.items():
        t0 = time.perf_counter()
        parts = TD.particion(snap, k)
        col = TD.TARGETS[tgt][0]
        va, te = parts["valid"], parts["test"]
        ids = {"valid": va["episodio_id"].to_numpy(), "test": te["episodio_id"].to_numpy()}
        y = {"valid": va[col].to_numpy(), "test": te[col].to_numpy()}
        pk = {s: _conservado(f"t45_k{k}_{s}.npz", ids[s], f"{tgt}__{kept}") for s in ("valid", "test")}
        familias = [(kept, fam_k, grupo_k), *[f for f in FAMILIAS_EXTRA if f[0] != kept]]
        preds: Dict[str, Dict[str, np.ndarray]] = {"valid": {kept: pk["valid"]}, "test": {kept: pk["test"]}}
        # the kept model retrained as a reproducibility check (valid)
        num0, cat = TD.GRUPOS[grupo_k]
        TD.verificar_sin_fuga(num0, cat)
        base = _entrenar_t45(fam_k, list(num0), list(cat), parts, sem, k, col, seeds, dev)
        reprod = {s: float(np.max(np.abs(base[s] - pk[s]))) for s in ("valid", "test")}
        log(f"{tgt} k={k}: {kept} reentrenado, diferencia maxima con lo guardado {reprod}")
        info: Dict[str, Dict] = {}
        nombres: List[str] = []
        for (fam_n, fam, grupo) in familias:
            num_b, cat_b = TD.GRUPOS[grupo]
            # the reference of the same family WITHOUT the block (only for the families that are not the kept one)
            if fam_n != kept:
                F0 = _entrenar_t45(fam, list(num_b), list(cat_b), parts, sem, k, col, seeds, dev)
                n0 = f"{fam_n}"
                for s in ("valid", "test"):
                    preds[s][n0] = F0[s]
                nombres.append(n0)
                info[n0] = {"bloque": None, "familia": fam}
            for bloque in BLOQUES_T45[tgt]:
                extra = _cols(parts["train"], bloque)
                nombre = f"{fam_n}+{bloque}"
                F = _entrenar_t45(fam, [*num_b, *extra], list(cat_b), parts, sem, k, col, seeds, dev)
                for s in ("valid", "test"):
                    preds[s][nombre] = F[s]
                nombres.append(nombre)
                info[nombre] = {"bloque": bloque, "familia": fam, "n_columnas_nuevas": len(extra), "columnas": extra}
                log(f"{tgt} k={k}: {nombre} listo ({time.perf_counter() - t0:.0f} s)")
        idx = {s: M45.remuestreos(parts[s]["persona_key"].to_numpy(), boot, seed=7) for s in ("valid", "test")}
        ev = {s: M45.bootstrap_agrupado(y[s], {m: preds[s][m] for m in [kept, *nombres]}, idx[s], [(n, kept) for n in nombres])
              for s in ("valid", "test")}
        limpio = {s: parts[s]["n_sem_sin_reprobacion"].to_numpy() == 0 for s in ("valid", "test")}
        ev_l = {}
        if limpio["valid"].sum() >= 100 and y["valid"][limpio["valid"]].sum() >= 10:
            m_ = limpio["valid"]
            idx_l = M45.remuestreos(va["persona_key"].to_numpy()[m_], boot, seed=13)
            ev_l = M45.bootstrap_agrupado(y["valid"][m_], {m: preds["valid"][m][m_] for m in [kept, *nombres]}, idx_l,
                                          [(n, kept) for n in nombres])
        cands = []
        for n in nombres:
            d = ev["valid"][f"{n}__vs__{kept}"]["ap"]
            lim = ev_l.get(f"{n}__vs__{kept}", {}).get("ap")
            cands.append({"nombre": n, **info[n], "gana": decidir_ap(d), "valid_punto": ev["valid"][n]["ap"]["punto"],
                          "delta_ap_valid": d, "delta_ap_test": ev["test"][f"{n}__vs__{kept}"]["ap"],
                          "valid_sin_p58": None if lim is None else {"n": int(limpio["valid"].sum()), "eventos": int(y["valid"][limpio["valid"]].sum()), "delta_ap": lim}})
        elegido = elegir([c for c in cands if c["bloque"] is not None])
        res[f"{tgt}_k{k}"] = {"conservado": kept, "reproduccion_max_abs": reprod,
                              "valid": {m: ev["valid"][m] for m in [kept, *nombres]}, "test": {m: ev["test"][m] for m in [kept, *nombres]},
                              "candidatos": cands, "adopta": None if elegido is None else elegido["nombre"],
                              "n": {s: {"n": int(len(parts[s])), "eventos": int(parts[s][col].sum())} for s in ("train", "valid", "test")},
                              "segundos": time.perf_counter() - t0}
        for s in ("valid", "test"):
            _guardar(f"t45_{tgt}_k{k}_{s}", ids[s], {n: preds[s][n] for n in nombres})
        log(f"{tgt} k={k}: adopta={res[f'{tgt}_k{k}']['adopta']}")
    return res


def alias_publicado(nombre: str) -> str:
    """Key under which an adopted candidate is stored next to the kept models (``lr_agg+t4`` -> ``lr_agg_t4``)."""
    return nombre.replace("+", "_")


def _publicar_t45(tgt: str, k: int, nombre: str, parts, abl) -> str:
    """Add the key ``<tgt>__<alias>`` to ``t45_k{k}_{valid,test}.npz``; the arrays already there must stay bit-identical."""
    alias = alias_publicado(nombre)
    for s, d in (("valid", parts["valid"]), ("test", parts["test"])):
        ruta = S.ARTEFACTOS / "preds" / f"t45_k{k}_{s}.npz"
        z = dict(np.load(ruta))
        original = {n: v.copy() for n, v in z.items()}
        z[f"{tgt}__{alias}"] = _alinear(d["episodio_id"].to_numpy(), abl[s], nombre).astype("float32")
        if not np.array_equal(z["episodio_id"], d["episodio_id"].to_numpy()):       # same rows, same order as the snapshot
            raise RuntimeError(f"{ruta.name}: row order differs from the snapshot")
        np.savez_compressed(ruta, **z)
        nuevo = np.load(ruta)
        if any(not np.array_equal(nuevo[n], original[n]) for n in original):
            raise RuntimeError(f"{ruta.name}: an array that was already there changed")
    return f"{tgt}__{alias}"


def final_t45(conn, boot: int, log: Callable[[str], None], publicar: bool = True) -> Dict:
    """D114 'ties to the simpler' among the winning candidates of ``ablacion_t45`` and, for the adopted ones, the publication of
    their predictions next to the kept models in ``artefactos/preds/t45_k{k}_{valid,test}.npz`` (new keys ``T?__<alias>``; the
    arrays already there are left untouched and verified)."""
    from models import t45_data as TD

    previo = json.loads((S.ARTEFACTOS / "ablacion_variables_t45.json").read_text(encoding="utf-8"))
    snap, _ = TD.cargar(conn)
    out: Dict = {}
    for (tgt, k) in KEPT_T45:
        r = previo[f"{tgt}_k{k}"]
        parts = TD.particion(snap, k)
        col = TD.TARGETS[tgt][0]
        va, te = parts["valid"], parts["test"]
        abl = {s: np.load(S.ARTEFACTOS / "preds" / f"abl_t45_{tgt}_k{k}_{s}.npz") for s in ("valid", "test")}
        ganadores = [c["nombre"] for c in r["candidatos"] if c["gana"] and c["bloque"]]
        info = {"conservado": r["conservado"], "ganadores_d114": ganadores, "adopta": None}
        if ganadores:
            idx = M45.remuestreos(va["persona_key"].to_numpy(), boot, seed=7)
            yv = va[col].to_numpy()

            def delta(a: str, b: str) -> Optional[Dict[str, float]]:
                ev = M45.bootstrap_agrupado(yv, {a: _alinear(va["episodio_id"].to_numpy(), abl["valid"], a),
                                                 b: _alinear(va["episodio_id"].to_numpy(), abl["valid"], b)}, idx, [(a, b)])
                return ev[f"{a}__vs__{b}"]["ap"]

            mejor = max(ganadores, key=lambda n: next(c["valid_punto"] for c in r["candidatos"] if c["nombre"] == n))
            final = refinar_por_simplicidad(mejor, ganadores, delta)
            c = next(c for c in r["candidatos"] if c["nombre"] == final)
            t = c["delta_ap_test"]
            info.update({"mejor_valid": mejor, "adopta": final, "delta_ap_valid": c["delta_ap_valid"], "delta_ap_test": t,
                         "prueba": ("confirma" if t["lo"] > 0 else "contradice" if t["hi"] < 0 else "no contradice (IC incluye el cero)"),
                         "valid_sin_p58": c.get("valid_sin_p58"),
                         "pares_entre_ganadores": {f"{a}__vs__{b}": delta(a, b) for a in ganadores for b in ganadores
                                                   if a != b and complejidad(b) < complejidad(a)}})
            if publicar:
                info["publicado_como"] = [_publicar_t45(tgt, k, n, parts, abl) for n in dict.fromkeys([final, mejor])]
        out[f"{tgt}_k{k}"] = info
        log(f"{tgt} k={k}: ganadores {ganadores} -> adopta {info['adopta']}")
    return out


# ---------------------------------------------------------------------------------------------
# T6
# ---------------------------------------------------------------------------------------------
def ablacion_t6(conn, boot: int, log: Callable[[str], None]) -> Dict:
    from evaluation.run_t6 import PARES, TAU_PRINCIPAL, TAUS
    from models import t6_data as TD
    from models import t6_modelos as MD
    from pipelines.snapshots import rules_t6 as R6

    snap = TD.cargar(conn)
    _, v6 = VD.cargar_nuevas(conn)
    n0 = len(snap)
    snap = snap.merge(v6, on="episodio_id", how="left", validate="one_to_one")
    assert len(snap) == n0
    parts = TD.particion(snap)
    tr, va, te = parts["train"], parts["valid"], parts["test"]
    j0 = list(TAUS).index(TAU_PRINCIPAL)

    def ajustar(num: List[str], cat: List[str]) -> Dict[str, np.ndarray]:
        TD.verificar_sin_fuga(num, cat)
        prep = Preprocesador(num, cat).fit(tr)
        X = {s: prep.transform(d).astype("float64") for s, d in (("train", tr), ("valid", va), ("test", te))}
        m, _ = MD.ajustar_cox(TAUS, X["train"], tr["tiempo"].to_numpy(), tr["evento"].to_numpy(), X["valid"],
                              va["tiempo"].to_numpy(), va["evento"].to_numpy(), tau=4)
        return {s: m.predict(X[s])[:, j0] for s in ("valid", "test")}

    num_p, cat_p = TD.GRUPOS["perfil"]
    num_a, cat_a = TD.GRUPOS["perfil+academico"]
    kept = "cox_perfil"
    ids = {"valid": va["episodio_id"].to_numpy(), "test": te["episodio_id"].to_numpy()}
    base = ajustar(list(num_p), list(cat_p))
    # the saved T6 predictions come from an earlier build of snapshot_t6 (7-8 rows fewer per split): the comparator is the kept
    # model RETRAINED on the current snapshot, and the saved ones only serve as a reproducibility check on the common rows
    reprod = {}
    for s in ("valid", "test"):
        z = np.load(S.ARTEFACTOS / "preds" / f"t6_{s}.npz")
        pos = pd.Series(np.arange(len(z["episodio_id"])), index=z["episodio_id"]).reindex(ids[s])
        ok = pos.notna().to_numpy()
        gs = z[f"{kept}__tau{TAU_PRINCIPAL}"][pos[ok].to_numpy().astype(int)].astype("float64")
        reprod[s] = {"filas_comunes": int(ok.sum()), "filas": int(len(ok)), "max_abs": float(np.max(np.abs(base[s][ok] - gs)))}
    log(f"T6: {kept} reentrenado sobre el snapshot actual; contra lo guardado {reprod}")
    preds = {"valid": {kept: base["valid"]}, "test": {kept: base["test"]}}
    info: Dict[str, Dict] = {}
    for (nombre_base, num_b, cat_b) in ((kept, num_p, cat_p), ("cox_agg", num_a, cat_a)):
        for bloque, (num_x, cat_x) in VD.T6_BLOQUES.items():
            if nombre_base == "cox_agg" and bloque != "todo":
                continue
            nm = f"{nombre_base}+{bloque}"
            F = ajustar([*num_b, *VD.columnas_validas(tr, num_x)], [*cat_b, *cat_x])
            for s in ("valid", "test"):
                preds[s][nm] = F[s]
            info[nm] = {"bloque": bloque, "base": nombre_base, "columnas": [*num_x, *cat_x]}
            log(f"T6: {nm} listo")
    nombres = list(info)
    ev = {}
    for s, d in (("valid", va), ("test", te)):
        ev[s] = M6.evaluar_horizonte(d["tiempo"], d["evento"], d["seguimiento"], {m: preds[s][m] for m in [kept, *nombres]},
                                     TAU_PRINCIPAL, d["persona_key"].to_numpy(), boot, [(n, kept) for n in nombres])
    cands = []
    for n in nombres:
        d = ev["valid"]["pares"].get(f"{n}__vs__{kept}", {}).get("ap")
        cands.append({"nombre": n, **info[n], "gana": decidir_ap(d), "valid_punto": ev["valid"]["modelos"][n]["ap"]["punto"],
                      "delta_ap_valid": d, "delta_ap_test": ev["test"]["pares"].get(f"{n}__vs__{kept}", {}).get("ap")})
    elegido = elegir(cands)
    el_v, y_v = R6.resultado_horizonte(va["tiempo"], va["evento"], va["seguimiento"], TAU_PRINCIPAL)
    _guardar("t6_valid", ids["valid"], {n: preds["valid"][n] for n in nombres})
    _guardar("t6_test", ids["test"], {n: preds["test"][n] for n in nombres})
    return {"conservado": kept, "tau": TAU_PRINCIPAL, "reproduccion_max_abs": reprod,
            "valid": {"n": ev["valid"]["n"], "eventos": ev["valid"]["eventos"], "modelos": ev["valid"]["modelos"]},
            "test": {"n": ev["test"]["n"], "eventos": ev["test"]["eventos"], "modelos": ev["test"]["modelos"]},
            "candidatos": cands, "adopta": None if elegido is None else elegido["nombre"],
            "n_split": {s: int(len(p)) for s, p in parts.items()},
            "eventos_train": int(tr["evento"].sum()), "cobertura": {c: float(snap[c].notna().mean()) for c in (*VD.T6_NUM, "area_conocimiento")}}


def parsear(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Ablation of the new variables under D114.")
    ap.add_argument("--tarea", choices=("t3", "t45", "t45-final", "t6"), required=True)
    ap.add_argument("--boot", type=int, default=BOOT)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--sin-publicar", action="store_true", help="t45-final: decide but do not write the adopted predictions")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parsear(argv)
    try:
        from pipelines.common.db import dev_connection

        t0 = time.perf_counter()
        log = lambda m: print(m, flush=True)   # noqa: E731
        seeds = SEMILLAS[: args.seeds]
        with dev_connection() as conn:
            if args.tarea == "t3":
                out = ablacion_t3(conn, args.boot, seeds, log)
            elif args.tarea == "t45":
                out = ablacion_t45(conn, args.boot, seeds, log)
            elif args.tarea == "t45-final":
                out = final_t45(conn, args.boot, log, publicar=not args.sin_publicar)
            else:
                out = ablacion_t6(conn, args.boot, log)
        out["segundos_totales"] = time.perf_counter() - t0
        S.ARTEFACTOS.mkdir(exist_ok=True)
        (S.ARTEFACTOS / f"ablacion_variables_{args.tarea.replace('-', '_')}.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
        print(f"escrito artefactos/ablacion_variables_{args.tarea}.json ({out['segundos_totales']:.0f} s)")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
