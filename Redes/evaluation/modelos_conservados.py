"""Rebuild and persistence of the kept models (plan 2026-11-18, Task 2).

No fitted model is persisted by the benchmark runners (each trains in memory and saves only predictions), yet the projection of
the current students (scoring) and the permutation importance need the models themselves. This module refits each KEPT model with
the validated configuration (same training window, same seeds ``(0, 1, 2)``, predictions = seed mean), persists it under
``artefactos/modelos/`` and, every time it hands one out, checks that its test predictions reproduce the saved ones
(max |dp| <= ``TOL``, aligned by episode / attempt id, never by row order). A model that does not reproduce raises
``ReproduccionFallida``: nothing downstream may publish from it.

``python -m evaluation.modelos_conservados --verificar-todo`` does it for every key and prints ``tarea k nombre max|dp|=...``.

Kept models (docs/00_plan.md): T1 ``cb_acad`` (k=1), ``cb_ben_pit`` (k=1, cohorts >= 2024), ``lr_acad`` (k=2); T2 ``cb_c_nuevas``;
T3 ``dt_lr_adm`` (k=0), ``nn_gru`` (k=2, 4); T5 ``gru_adm`` (k=2), ``gru_agg`` (k=4). Models are fitted by the same primitives the
runners call (``run_beneficios_cargas_t1.ajustar_modelos``, ``run_t2.cb_ajustar``, ``t3_discreto``, ``t3_redes``, ``gru``).
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd

from models import data as D
from models import seguimiento as S
from pipelines.snapshots.rules import TRAIN_DESDE_OFICIAL

SEMILLAS = (0, 1, 2)
TOL = 1e-4
CLAVES: Tuple[Tuple[str, int, str], ...] = (
    ("t1", 1, "cb_acad"), ("t1", 1, "cb_ben_pit"), ("t1", 2, "lr_acad"), ("t2", 0, "cb_c_nuevas"),
    ("t3", 0, "dt_lr_adm"), ("t3", 2, "nn_gru"), ("t3", 4, "nn_gru"), ("t5", 2, "gru_adm"), ("t5", 4, "gru_agg"))
TIPO_DE = {("t1", "cb_acad"): "t1_cb", ("t1", "cb_ben_pit"): "t1_cb", ("t1", "lr_acad"): "t1_lr", ("t2", "cb_c_nuevas"): "t2_cb",
           ("t3", "dt_lr_adm"): "t3_lr", ("t3", "nn_gru"): "t3_nn", ("t5", "gru_adm"): "t5_gru", ("t5", "gru_agg"): "t5_gru"}
TIPOS_TORCH = ("t3_nn", "t5_gru")
GRUPO_T3_NN = "adm+agg"
GRUPO_T5 = {"gru_adm": "adm", "gru_agg": "adm+agg"}
OBJETIVO_T5 = "y5"                                          # T5 (eliminacion)


class ReproduccionFallida(RuntimeError):
    """A rebuilt model whose test predictions differ from the saved ones by more than the tolerance."""


class ModeloConservado:
    """One fitted kept model. ``predecir`` is the only scoring entry point:

    * T1 / T2 / T5: probability of the event of the task (T1 ``no_continua``, T2 ``no_aprueba``, T5 ``eliminacion``);
    * T3: cumulative incidence of egress ``[n, U]`` with ``U = 20 - k`` semesters after the cut.

    ``filas`` carries the model's input columns; ``sem`` (semester rows with ``episodio_id`` and ``j``) is needed by the networks only.
    """

    def __init__(self, tarea: str, k: int, nombre: str, tipo: str, componentes: Dict[str, Any]):
        self.tarea, self.k, self.nombre, self.tipo, self.componentes = tarea, int(k), nombre, tipo, componentes
        self._redes: Optional[List[Any]] = None

    def __repr__(self) -> str:
        return f"ModeloConservado({self.tarea}, k={self.k}, {self.nombre})"

    def __getstate__(self) -> Dict[str, Any]:
        return {**self.__dict__, "_redes": None}              # torch modules are rebuilt from the state dicts

    def predecir(self, filas: pd.DataFrame, sem: Optional[pd.DataFrame] = None, secuencias: Optional[np.ndarray] = None) -> np.ndarray:
        c = self.componentes
        if self.tipo == "t1_lr":
            return c["lr"].predict_proba(c["prep"].transform(filas))[:, 1]
        if self.tipo == "t1_cb":
            from models import catboost_modelo

            X = c["prep"].transform_catboost(filas)
            return np.mean([catboost_modelo.predecir(m, X, c["prep"].cat_cols) for m in c["cbs"]], axis=0)
        if self.tipo == "t2_cb":
            from evaluation.run_t2 import cb_predecir

            X = c["prep"].transform_catboost(filas)
            return np.mean([cb_predecir(m, X, list(c["prep"].cat_cols)) for m in c["cbs"]], axis=0)
        if self.tipo == "t3_lr":
            from models import t3_discreto as DT

            return DT.logistica_cif(c["lr"], c["prep"], filas, self.k)
        if self.tipo == "t3_nn":
            return self._predecir_red_t3(filas, sem)
        if self.tipo == "t5_gru":
            return self._predecir_gru_t5(filas, sem, secuencias)
        raise ValueError(f"unknown model type {self.tipo!r}")

    # -- networks ------------------------------------------------------------------------------------------------
    def _dispositivo(self):
        import torch

        return torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _redes_cargadas(self, construir: Callable[[], Any]) -> List[Any]:
        if self._redes is None:
            dev = self._dispositivo()
            redes = []
            for estado in self.componentes["estados"]:
                red = construir().to(dev)
                red.load_state_dict(estado)
                red.eval()
                redes.append(red)
            self._redes = redes
        return self._redes

    def _predecir_red_t3(self, filas: pd.DataFrame, sem: Optional[pd.DataFrame]) -> np.ndarray:
        from models import t3_data as TD3
        from models import t3_redes as NR

        c, k = self.componentes, self.k
        if sem is None:
            raise ValueError("the T3 network needs the semester rows (sem)")
        prep, U = c["prep"], TD3.JMAX - k
        redes = self._redes_cargadas(lambda: NR.RedRiesgos(c["n_num"], prep.cardinalidades(), U, c["d_seq"]))
        conj = NR.ConjuntoT3(prep.transform_num(filas), prep.transform_cat_codes(filas), np.ones(len(filas), "int64"),
                             np.zeros(len(filas), "int64"), TD3.construir_secuencias_t3(filas, sem, k))
        dev = self._dispositivo()
        return np.mean([NR.predecir_cif(r, conj, dev) for r in redes], axis=0)

    def _predecir_gru_t5(self, filas: pd.DataFrame, sem: Optional[pd.DataFrame], secuencias: Optional[np.ndarray] = None) -> np.ndarray:
        from models import gru as G
        from models import t45_data as TD45

        c = self.componentes
        if sem is None and secuencias is None:
            raise ValueError("the T5 network needs the semester rows (sem)")
        prep = c["prep"]
        redes = self._redes_cargadas(lambda: G.RedGRU(c["d_seq"], c["n_num"], prep.cardinalidades()))
        conj = G.Conjunto(secuencias if secuencias is not None else TD45.construir_secuencias_t45(filas, sem, self.k), prep.transform_num(filas), prep.transform_cat_codes(filas))
        dev = self._dispositivo()
        return np.mean([G.predecir(r, conj, dev) for r in redes], axis=0)


# ---------------------------------------------------------------------------------------------------- persistence
def ruta_modelo(artefactos: Path, tarea: str, k: int, nombre: str) -> Path:
    """``artefactos/modelos/{tarea}_k{k}_{nombre}`` + ``.pt`` (torch) or ``.joblib`` (sklearn / CatBoost)."""
    ext = ".pt" if TIPO_DE.get((tarea, nombre)) in TIPOS_TORCH else ".joblib"
    return Path(artefactos) / "modelos" / f"{tarea}_k{k}_{nombre}{ext}"


def guardar(modelo: ModeloConservado, artefactos: Path) -> Path:
    ruta = ruta_modelo(artefactos, modelo.tarea, modelo.k, modelo.nombre)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if modelo.tipo in TIPOS_TORCH:
        import torch

        c = dict(modelo.componentes)
        buf = io.BytesIO()
        joblib.dump(c.pop("prep"), buf)
        torch.save({"meta": [modelo.tarea, modelo.k, modelo.nombre, modelo.tipo], "prep": buf.getvalue(), **c}, ruta)
    else:
        joblib.dump(modelo, ruta)
    return ruta


def cargar(ruta: Path) -> ModeloConservado:
    if Path(ruta).suffix == ".pt":
        import torch

        d = torch.load(ruta, map_location="cpu", weights_only=False)
        tarea, k, nombre, tipo = d.pop("meta")
        prep = joblib.load(io.BytesIO(d.pop("prep")))
        return ModeloConservado(tarea, k, nombre, tipo, {"prep": prep, **d})
    # the sklearn / CatBoost files were pickled while this module ran as ``__main__`` (``python -m evaluation.modelos_conservados``):
    # make that name resolvable whichever program loads them
    main = sys.modules["__main__"]
    if not hasattr(main, "ModeloConservado"):
        main.ModeloConservado = ModeloConservado
    return joblib.load(ruta)


# ---------------------------------------------------------------------------------------------------- data (cached per run)
_CACHE: Dict[str, Any] = {}


def limpiar_cache() -> None:
    _CACHE.clear()


def _en_cache(clave: str, construir: Callable[[], Any]) -> Any:
    if clave not in _CACHE:
        _CACHE[clave] = construir()
    return _CACHE[clave]


def snapshot_t1(conn) -> pd.DataFrame:
    """Every row of ``snapshot_t1`` (observed and censored), cached per run; the projection scores its censored rows."""
    return _en_cache("t1_snap", lambda: D.cargar_desde_db(conn)[0])


def snapshot_t3(conn) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """``(snapshot_t3, snapshot_t3_semestre)`` cached per run."""
    from models import t3_data as TD3

    return _en_cache("t3_datos", lambda: TD3.cargar(conn))


def snapshot_t5(conn) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """``(snapshot_t45, snapshot_t45_semestre)`` cached per run."""
    from models import t45_data as TD45

    return _en_cache("t5_datos", lambda: TD45.cargar(conn))


def _t1(conn, k: int) -> Dict[str, pd.DataFrame]:
    snap = snapshot_t1(conn)
    df = D.seleccionar_modelado(snap, k=k, train_desde=TRAIN_DESDE_OFICIAL)
    tr, va, te = (df[df["split"] == s].reset_index(drop=True) for s in D.SPLITS)
    return {"snap": snap, "train": tr, "valid": va, "test": te}


def _t1_pit(conn, snap: pd.DataFrame, k: int = 1, filas: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Rows of the cohorts >= 2024 with the point-in-time benefit features (the set where ``cb_ben_pit`` is evaluated, D112/D113).

    ``filas`` replaces the evaluation rows (the projection passes the censored rows of the current cohort); without it the
    every-row-has-load-history guard of the reproduction check applies."""
    from pipelines.snapshots import features_beneficios_cargas as FC

    from . import diagnostico_beneficios_cargas as DC
    from .run_beneficios_cargas_t1 import filas_de_evaluacion, sustituir_beneficios

    cargas, calendario, _ = _en_cache("t1_cargas", lambda: DC.cargar(conn))
    ev_final = filas_de_evaluacion(snap, k) if filas is None else filas.reset_index(drop=True)
    ev = sustituir_beneficios(ev_final, FC.features_beneficios_cargas(ev_final, cargas, calendario))
    if filas is None and not (ev["ben_sin_dato"] == 0).all():
        raise ReproduccionFallida("every point-in-time row must have load history at its cut")
    return ev


def _t2(conn) -> Dict[str, pd.DataFrame]:
    from models import t2_data as TD2

    df = _en_cache("t2_df", lambda: TD2.cargar(conn))
    return _en_cache("t2_parts", lambda: TD2.particion(df))


def _t3(conn, k: int) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    from models import t3_data as TD3

    snap, sem = snapshot_t3(conn)
    return TD3.particion(snap, k), sem


def _t5(conn, k: int) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    from models import t45_data as TD45

    snap, sem = snapshot_t5(conn)
    return TD45.particion(snap, k), sem


# ---------------------------------------------------------------------------------------------------- fitting
def _dispositivo_entrenamiento():
    import torch

    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _estado_cpu(modelo) -> Dict[str, Any]:
    return {n: v.detach().cpu().clone() for n, v in modelo.state_dict().items()}


def _ajustar_t1(conn, k: int, nombre: str) -> ModeloConservado:
    from .run_beneficios_cargas_t1 import ajustar_modelos

    d = _t1(conn, k)
    if nombre == "cb_ben_pit":
        num, cat = D.GRUPOS_BENEFICIOS["pre_entry+academico+beneficios"]
    else:
        num, cat = D.GRUPOS["pre_entry+academico"]
    fam = nombre[:2]
    m = ajustar_modelos(d["train"], d["valid"], num, cat, SEMILLAS, familias=(fam,))
    comp = {"prep": m["prep"], "lr": m["lr"]} if fam == "lr" else {"prep": m["prep"], "cbs": m["cbs"]}
    return ModeloConservado("t1", k, nombre, TIPO_DE[("t1", nombre)], comp)


def _ajustar_t2(conn, k: int, nombre: str) -> ModeloConservado:
    from models import t2_data as TD2

    from .run_t2 import cb_ajustar

    parts = _t2(conn)
    tr, va = parts["train"], parts["valid"]
    num, cat = TD2.CONJUNTOS["c_nuevas"][0], TD2.CONJUNTOS["c"][1]
    prep = TD2.PreprocesadorT2(num, cat).fit(tr)
    Ctr, Cva = prep.transform_catboost(tr), prep.transform_catboost(va)
    cbs = [cb_ajustar(Ctr, tr["y"].to_numpy(), Cva, va["y"].to_numpy(), cat, s) for s in SEMILLAS]
    return ModeloConservado("t2", k, nombre, "t2_cb", {"prep": prep, "cbs": cbs})


def _ajustar_t3(conn, k: int, nombre: str) -> ModeloConservado:
    from models import t3_data as TD3
    from models import t3_discreto as DT

    parts, sem = _t3(conn, k)
    tr, va = parts["train"], parts["valid"]
    if nombre == "dt_lr_adm":
        num, cat = TD3.GRUPOS["adm"]
        TD3.verificar_sin_fuga(num, cat)
        prep = D.Preprocesador(num, cat).fit(tr)
        lr, _ = DT.logistica_ajustar(prep, tr, va, k)
        return ModeloConservado("t3", k, nombre, "t3_lr", {"prep": prep, "lr": lr})
    from models import t3_redes as NR

    num, cat = TD3.GRUPOS[GRUPO_T3_NN]
    TD3.verificar_sin_fuga(num, cat)
    prep = D.Preprocesador(num, cat).fit(tr)
    seq = {s: TD3.construir_secuencias_t3(parts[s], sem, k) for s in ("train", "valid")}

    def conj(d, s):
        return NR.ConjuntoT3(prep.transform_num(d), prep.transform_cat_codes(d), d["u"].to_numpy(), d["causa"].to_numpy(), seq[s])

    ctr, cva = conj(tr, "train"), conj(va, "valid")
    dev, U, estados = _dispositivo_entrenamiento(), TD3.JMAX - k, []
    for s in SEMILLAS:
        r = NR.entrenar(ctr, cva, prep.cardinalidades(), U, s, dev)
        estados.append(_estado_cpu(r["model"]))
        del r
    return ModeloConservado("t3", k, nombre, "t3_nn", {"prep": prep, "estados": estados, "n_num": int(ctr.num.shape[1]),
                                                       "d_seq": int(ctr.seq.shape[2])})


def _ajustar_t5(conn, k: int, nombre: str) -> ModeloConservado:
    from models import gru as G
    from models import t45_data as TD45

    parts, sem = _t5(conn, k)
    tr, va = parts["train"], parts["valid"]
    num, cat = TD45.GRUPOS[GRUPO_T5[nombre]]
    TD45.verificar_sin_fuga(num, cat)
    prep = D.Preprocesador(num, cat).fit(tr)

    def conj(d):
        return G.Conjunto(TD45.construir_secuencias_t45(d, sem, k), prep.transform_num(d), prep.transform_cat_codes(d), d[OBJETIVO_T5].to_numpy())

    ctr, cva = conj(tr), conj(va)
    dev, estados = _dispositivo_entrenamiento(), []
    for s in SEMILLAS:
        r = G.entrenar(ctr, cva, prep.cardinalidades(), seed=s, device=dev)
        estados.append(_estado_cpu(r["model"]))
        del r
    return ModeloConservado("t5", k, nombre, "t5_gru", {"prep": prep, "estados": estados, "n_num": int(ctr.num.shape[1]),
                                                        "d_seq": int(ctr.seq.shape[2])})


_AJUSTADORES = {"t1": _ajustar_t1, "t2": _ajustar_t2, "t3": _ajustar_t3, "t5": _ajustar_t5}


def ajustar(conn, tarea: str, k: int, nombre: str) -> ModeloConservado:
    """Refit one kept model with the validated configuration (training window, seeds and hyper-parameters of its runner)."""
    if (tarea, k, nombre) not in CLAVES:
        raise ValueError(f"{(tarea, k, nombre)} is not a kept model; expected one of {CLAVES}")
    return _AJUSTADORES[tarea](conn, k, nombre)


# ---------------------------------------------------------------------------------------------------- reproduction check
def _filas_de_verificacion(modelo, conn) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """The rows whose predictions were saved (test split; for ``cb_ben_pit`` the cohorts >= 2024) and the semester rows if needed."""
    t, k, n = modelo.tarea, modelo.k, modelo.nombre
    if t == "t1":
        d = _t1(conn, k)
        return (_t1_pit(conn, d["snap"], k) if n == "cb_ben_pit" else d["test"]), None
    if t == "t2":
        return _t2(conn)["test"], None
    parts, sem = (_t3 if t == "t3" else _t5)(conn, k)
    return parts["test"], sem


def archivo_predicciones(tarea: str, k: int, nombre: str, artefactos: Path) -> Path:
    """File of ``artefactos/preds`` holding the saved test predictions of one kept model (what its reproduction is checked against)."""
    pr = Path(artefactos) / "preds"
    if tarea == "t1" and nombre == "cb_ben_pit":
        return pr / "t1_nuevas_pit_k1.npz"
    if tarea == "t1":
        return pr / f"t1_nuevas_k{k}.npz"
    if tarea == "t2":
        return pr / "t2_nuevas_test.npz"
    if tarea == "t3":
        return pr / f"t3_k{k}_test.npz"
    return pr / f"t45_k{k}_test.npz"


def _predicciones_guardadas(modelo, artefactos: Path) -> Tuple[np.ndarray, np.ndarray]:
    """``(ids, predictions)`` saved by the runner that produced the model (``artefactos/preds/*.npz``)."""
    t, k, n = modelo.tarea, modelo.k, modelo.nombre
    z = np.load(archivo_predicciones(t, k, n, artefactos))
    if t == "t1" and n == "cb_ben_pit":
        return z["episodio"], z["pit__cb_ben_pit"]
    if t == "t1":
        return z["episodio_test"], z[f"test__{n}"]
    if t == "t2":
        return z["intento_id"], z[n]
    if t == "t3":
        return z["episodio_id"], z[n]
    return z["episodio_id"], z[f"T5__{n}"]


def verificar(modelo, conn, artefactos: Path, tol: float = TOL) -> float:
    """Max |dp| between the model's predictions and the saved test predictions, aligned by id. Above ``tol`` -> ``ReproduccionFallida``."""
    filas, sem = _filas_de_verificacion(modelo, conn)
    ids_guardados, guardadas = _predicciones_guardadas(modelo, artefactos)
    col = "intento_id" if modelo.tarea == "t2" else "episodio_id"
    ids = filas[col].to_numpy()
    pos = pd.Index(ids_guardados).get_indexer(ids)
    clave = f"{modelo.tarea} k={modelo.k} {modelo.nombre}"
    if len(ids) != len(ids_guardados) or (pos < 0).any() or len(set(pos.tolist())) != len(ids_guardados):
        raise ReproduccionFallida(f"{clave}: the rows to score are not the rows of the saved predictions "
                                  f"({len(ids)} vs {len(ids_guardados)}, {int((pos < 0).sum())} unmatched)")
    p = np.asarray(modelo.predecir(filas, sem), dtype="float64")
    g = np.asarray(guardadas, dtype="float64")[pos]
    if p.shape != g.shape or not np.isfinite(p).all() or not np.isfinite(g).all():
        raise ReproduccionFallida(f"{clave}: prediction shape {p.shape} vs saved {g.shape}, or non-finite values")
    delta = float(np.max(np.abs(p - g)))
    if not delta <= tol:
        raise ReproduccionFallida(f"{clave}: max|dp|={delta:.3g} exceeds the tolerance {tol:g}; the model does not reproduce the saved predictions")
    return delta


def _obtener(conn, tarea: str, k: int, nombre: str, artefactos: Path) -> ModeloConservado:
    """The persisted model; if absent, refit it, persist it and read it back (so the file itself is what gets verified)."""
    ruta = ruta_modelo(artefactos, tarea, k, nombre)
    if not ruta.exists():
        guardar(ajustar(conn, tarea, k, nombre), artefactos)
    return cargar(ruta)


def cargar_o_ajustar(conn, tarea: str, k: int, nombre: str, artefactos: Path) -> ModeloConservado:
    """Persisted model if present, else refit and persist it; either way the reproduction check runs before returning."""
    modelo = _obtener(conn, tarea, k, nombre, artefactos)
    verificar(modelo, conn, artefactos)
    return modelo


# ---------------------------------------------------------------------------------------------------- command line
def verificar_todo(conn, artefactos: Path, log=print, claves: Sequence[Tuple[str, int, str]] = CLAVES) -> bool:
    """Every key: load or fit, persist, verify; one line per key. Returns True when all reproduce within tolerance."""
    ok, previa = True, None
    for tarea, k, nombre in claves:
        if previa is not None and tarea != previa:
            limpiar_cache()                          # one task's snapshot at a time (T2 is large)
        previa = tarea
        try:
            modelo = _obtener(conn, tarea, k, nombre, artefactos)
            log(f"{tarea} {k} {nombre} max|dp|={verificar(modelo, conn, artefactos):.3e}")
        except ReproduccionFallida as exc:
            ok = False
            log(f"{tarea} {k} {nombre} FALLA: {exc}")
    return ok


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Rebuild, persist and verify the kept models.")
    ap.add_argument("--verificar-todo", action="store_true", required=True)
    ap.add_argument("--artefactos", default=str(S.ARTEFACTOS))
    args = ap.parse_args(argv)
    from pipelines.common.db import dev_connection

    try:
        with dev_connection() as conn:
            ok = verificar_todo(conn, Path(args.artefactos), log=lambda m: print(m, flush=True))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
