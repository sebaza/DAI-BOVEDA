"""Course graph for T2: GraphSAGE (mean aggregator, written in plain torch; no torch_geometric) and the end-to-end net.

* Nodes: every ``codigo_asignatura`` of the snapshot, the malla and the prerequisite table (global, program free).
* Relations (row-normalised sparse adjacencies, mean aggregation): ``previo`` (messages from the prerequisites of a
  course), ``posterior`` (from the courses that require it) and, optionally, ``co`` (courses taken together in the same
  student-period, counted on TRAIN periods only, symmetric, min count).
* Node attributes carry no outcome of the modelled window: credits, malla-semester statistics, department and
  training area (categorical) and the pass rate of the course in the periods BEFORE 2015 (no train row can leak into it).
* Self-supervised use: link prediction on the prerequisite edges (10 % held out), then embeddings for CatBoost.
* Supervised use: ``RedT2`` trains the encoder end to end with the approval head; ``modo`` = ``gnn`` (message passing),
  ``mlp`` (same encoder without edges) or ``ninguno`` (no course representation).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from torch import nn

NUM_NODO = ["creditos_media", "sem_min", "sem_media", "sem_max", "n_programas", "log_n_malla", "grado_previo",
            "grado_posterior", "tasa_pre2015", "log_n_pre2015", "en_malla_g", "con_hist_pre2015"]
CAT_NODO = ["depto", "formacion"]
MIN_COOC = 30                                   # minimum number of train student-periods taking both courses


@dataclass
class DatosGrafo:
    nodos: pd.Index
    x_num: np.ndarray                            # (N, d) standardized node attributes
    x_cat: np.ndarray                            # (N, 2) int codes (0 = unknown)
    cards: List[int]
    aristas: np.ndarray                          # (E, 2) prerequisite edges (requisito -> asignatura), node indices
    co: np.ndarray = field(default_factory=lambda: np.zeros((0, 2), "int64"))    # co-enrollment pairs, i < j


def indices(nodos: pd.Index, codigos) -> np.ndarray:
    return nodos.get_indexer(codigos).astype("int64")


def construir_datos(nodos: pd.Index, malla: pd.DataFrame, prereq: pd.DataFrame, stats_pre: pd.DataFrame,
                    co: Optional[np.ndarray] = None) -> DatosGrafo:
    """Node table from the malla, the prerequisite edges and the pre-2015 pass rates (``codigo``, ``n``, ``aprob``)."""
    n = len(nodos)
    m = malla.copy()
    m["i"] = indices(nodos, m["codigo_asignatura"])
    m = m[m["i"] >= 0]
    g = m.groupby("i")
    num = pd.DataFrame(index=np.arange(n))
    num["creditos_media"] = g["creditos"].mean()
    num["sem_min"], num["sem_media"], num["sem_max"] = g["semestre"].min(), g["semestre"].mean(), g["semestre"].max()
    num["n_programas"] = g["cod_programa"].nunique()
    num["log_n_malla"] = np.log1p(g.size())
    pr = prereq.drop_duplicates(["codigo_requisito", "codigo_asignatura"])
    u, v = indices(nodos, pr["codigo_requisito"]), indices(nodos, pr["codigo_asignatura"])
    ok = (u >= 0) & (v >= 0) & (u != v)
    aristas = np.unique(np.stack([u[ok], v[ok]], axis=1), axis=0)
    num["grado_previo"] = pd.Series(np.bincount(aristas[:, 1], minlength=n), index=np.arange(n)).astype(float)
    num["grado_posterior"] = pd.Series(np.bincount(aristas[:, 0], minlength=n), index=np.arange(n)).astype(float)
    sp = stats_pre.copy()
    sp["i"] = indices(nodos, sp["codigo"])
    sp = sp[sp["i"] >= 0].set_index("i")
    prior = float(sp["aprob"].sum() / max(sp["n"].sum(), 1)) if len(sp) else 0.8
    n_ = sp["n"].reindex(np.arange(n)).fillna(0.0)
    a_ = sp["aprob"].reindex(np.arange(n)).fillna(0.0)
    num["tasa_pre2015"] = (a_ + 10.0 * prior) / (n_ + 10.0)
    num["log_n_pre2015"] = np.log1p(n_)
    num["en_malla_g"] = num["creditos_media"].notna().astype(float)
    num["con_hist_pre2015"] = (n_ > 0).astype(float)
    num = num[NUM_NODO]
    medias = num.median().fillna(0.0)
    z = num.fillna(medias)
    z = (z - z.mean()) / z.std(ddof=0).replace(0.0, 1.0).fillna(1.0)
    x_num = np.hstack([z.to_numpy("float32"), num[["creditos_media", "tasa_pre2015"]].isna().to_numpy("float32")])
    cats, cards = [], []
    for c in CAT_NODO:
        modo = m.groupby("i")[c].agg(lambda s: s.dropna().mode().iloc[0] if s.notna().any() else None)
        vocab = {v: j + 1 for j, v in enumerate(sorted(modo.dropna().unique()))}
        cats.append(modo.map(vocab).reindex(np.arange(n)).fillna(0).astype("int64").to_numpy())
        cards.append(len(vocab) + 1)
    return DatosGrafo(nodos, x_num, np.stack(cats, axis=1), cards, aristas,
                      np.zeros((0, 2), "int64") if co is None else co)


def pares_coinscripcion(grupo: np.ndarray, nodo: np.ndarray, minimo: int = MIN_COOC) -> np.ndarray:
    """Pairs (i < j) of courses taken together by at least ``minimo`` student-periods (rows of TRAIN only)."""
    df = pd.DataFrame({"g": grupo, "n": nodo}).drop_duplicates()
    df = df[df["n"] >= 0]
    pares = df.merge(df, on="g")
    pares = pares[pares["n_x"] < pares["n_y"]]
    cuenta = pares.groupby(["n_x", "n_y"]).size()
    cuenta = cuenta[cuenta >= minimo]
    return np.stack([cuenta.index.get_level_values(0).to_numpy(), cuenta.index.get_level_values(1).to_numpy()],
                    axis=1).astype("int64") if len(cuenta) else np.zeros((0, 2), "int64")


def _normalizada(filas: np.ndarray, cols: np.ndarray, n: int, device) -> torch.Tensor:
    """Sparse row-normalised adjacency: row i averages the messages of its sources ``cols``."""
    if len(filas) == 0:
        return torch.sparse_coo_tensor(torch.zeros((2, 0), dtype=torch.long), torch.zeros(0), (n, n)).to(device)
    deg = np.bincount(filas, minlength=n).astype("float32")
    val = 1.0 / deg[filas]
    idx = torch.as_tensor(np.stack([filas, cols]), dtype=torch.long)
    return torch.sparse_coo_tensor(idx, torch.as_tensor(val), (n, n)).coalesce().to(device)


def adyacencias(aristas: np.ndarray, co: np.ndarray, n: int, device, usar_co: bool = True) -> List[torch.Tensor]:
    """[previo, posterior(, co)]: previo[i] = mean over the prerequisites of i; posterior[i] = mean over courses that
    require i; co = symmetric co-enrollment."""
    adj = [_normalizada(aristas[:, 1], aristas[:, 0], n, device), _normalizada(aristas[:, 0], aristas[:, 1], n, device)]
    if usar_co:
        both = np.concatenate([co, co[:, ::-1]]) if len(co) else co
        adj.append(_normalizada(both[:, 0] if len(both) else np.zeros(0, "int64"),
                                both[:, 1] if len(both) else np.zeros(0, "int64"), n, device))
    return adj


class CapaSage(nn.Module):
    """h' = W_self h + sum_r W_r mean_{j in N_r(i)} h_j  (GraphSAGE with the mean aggregator, one weight per relation)."""

    def __init__(self, d_in: int, d_out: int, n_rel: int):
        super().__init__()
        self.propio = nn.Linear(d_in, d_out)
        self.rel = nn.ModuleList([nn.Linear(d_in, d_out, bias=False) for _ in range(n_rel)])

    def forward(self, h: torch.Tensor, adj: Sequence[torch.Tensor]) -> torch.Tensor:
        out = self.propio(h)
        for lin, a in zip(self.rel, adj):
            out = out + lin(torch.sparse.mm(a, h))
        return out


class CodificadorGrafo(nn.Module):
    """Node attributes -> 2 GraphSAGE layers -> ``d_out`` embedding. Without relations it is a plain MLP."""

    def __init__(self, d_num: int, cards: Sequence[int], n_rel: int, d_hid: int = 64, d_out: int = 32,
                 dropout: float = 0.1):
        super().__init__()
        self.emb = nn.ModuleList([nn.Embedding(c, 8) for c in cards])
        self.entrada = nn.Linear(d_num + 8 * len(cards), d_hid)
        self.c1, self.c2 = CapaSage(d_hid, d_hid, n_rel), CapaSage(d_hid, d_out, n_rel)
        self.drop = nn.Dropout(dropout)

    def forward(self, x_num: torch.Tensor, x_cat: torch.Tensor, adj: Sequence[torch.Tensor]) -> torch.Tensor:
        h = torch.cat([x_num] + [e(x_cat[:, i]) for i, e in enumerate(self.emb)], dim=1)
        h = self.drop(torch.relu(self.entrada(h)))
        h = self.drop(torch.relu(self.c1(h, adj)))
        return self.c2(h, adj)


class EnlacesAuto(nn.Module):
    """Self-supervised link predictor: bilinear score of (prerequisite, course) over the encoder embeddings."""

    def __init__(self, d_num, cards, n_rel, d_out=32):
        super().__init__()
        self.enc = CodificadorGrafo(d_num, cards, n_rel, d_out=d_out)
        self.w = nn.Parameter(torch.eye(d_out) + 0.01 * torch.randn(d_out, d_out))

    def puntaje(self, z: torch.Tensor, u: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
        return ((z[u] @ self.w) * z[v]).sum(dim=1)


def _tensores(d: DatosGrafo, device):
    return (torch.as_tensor(d.x_num, device=device), torch.as_tensor(d.x_cat, device=device))


def entrenar_enlaces(d: DatosGrafo, semilla: int = 0, device=None, epocas: int = 300, usar_co: bool = True,
                     d_out: int = 32, fraccion_val: float = 0.1) -> Dict:
    """Link prediction on the prerequisite edges; returns embeddings (all nodes, message passing over ALL edges) and the
    AP / AUC on the held-out 10 % of edges against an equal number of random non-edges."""
    device = device or torch.device("cpu")
    torch.manual_seed(semilla)
    rng = np.random.default_rng(semilla)
    n = len(d.nodos)
    e = d.aristas[rng.permutation(len(d.aristas))]
    nv = max(1, int(len(e) * fraccion_val))
    val, tr = e[:nv], e[nv:]
    existentes = set(map(tuple, d.aristas.tolist()))

    def negativos(m):
        out = []
        while len(out) < m:
            u, v = int(rng.integers(0, n)), int(rng.integers(0, n))
            if u != v and (u, v) not in existentes:
                out.append((u, v))
        return np.array(out, dtype="int64")

    neg_val = negativos(len(val))
    adj_tr = adyacencias(tr, d.co, n, device, usar_co)
    adj_all = adyacencias(d.aristas, d.co, n, device, usar_co)
    x_num, x_cat = _tensores(d, device)
    model = EnlacesAuto(x_num.shape[1], d.cards, len(adj_tr), d_out).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=5e-3, weight_decay=1e-5)
    pos_t = torch.as_tensor(tr, device=device)
    t0 = time.perf_counter()
    for _ in range(epocas):
        model.train()
        z = model.enc(x_num, x_cat, adj_tr)
        neg = torch.as_tensor(negativos(len(tr)), device=device)
        s_pos, s_neg = model.puntaje(z, pos_t[:, 0], pos_t[:, 1]), model.puntaje(z, neg[:, 0], neg[:, 1])
        loss = nn.functional.binary_cross_entropy_with_logits(
            torch.cat([s_pos, s_neg]), torch.cat([torch.ones_like(s_pos), torch.zeros_like(s_neg)]))
        opt.zero_grad()
        loss.backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        z_tr = model.enc(x_num, x_cat, adj_tr)
        uv = np.concatenate([val, neg_val])
        s = model.puntaje(z_tr, torch.as_tensor(uv[:, 0], device=device), torch.as_tensor(uv[:, 1], device=device))
        y = np.r_[np.ones(len(val)), np.zeros(len(neg_val))]
        sc = s.cpu().numpy()
        z_all = model.enc(x_num, x_cat, adj_all).cpu().numpy()
    deg_out = np.bincount(tr[:, 0], minlength=n) + 1.0
    deg_in = np.bincount(tr[:, 1], minlength=n) + 1.0
    grado = deg_out[uv[:, 0]] * deg_in[uv[:, 1]]                       # popularity baseline (train degrees only)
    return {"embeddings": z_all, "ap_enlaces": float(average_precision_score(y, sc)),
            "ap_grado": float(average_precision_score(y, grado)), "auc_grado": float(roc_auc_score(y, grado)),
            "auc_enlaces": float(roc_auc_score(y, sc)), "n_aristas": int(len(d.aristas)), "n_val": int(len(val)),
            "segundos": time.perf_counter() - t0}


# ---------------------------------------------------------------------------------------------
# end-to-end approval network
# ---------------------------------------------------------------------------------------------
HIDDEN = (256, 128)
BATCH = 4096
LR = 2e-3
WD = 1e-5
MAX_EPOCAS = 30
PACIENCIA = 4


class RedT2(nn.Module):
    def __init__(self, d_num: int, cards: Sequence[int], d_nodo_num: int, cards_nodo: Sequence[int], n_rel: int,
                 modo: str = "gnn", d_emb: int = 32, dropout: float = 0.2):
        super().__init__()
        assert modo in ("gnn", "mlp", "ninguno")
        self.modo = modo
        self.emb = nn.ModuleList([nn.Embedding(c, min(8, c // 2 + 1)) for c in cards])
        d_cat = sum(min(8, c // 2 + 1) for c in cards)
        self.enc = (CodificadorGrafo(d_nodo_num, cards_nodo, n_rel if modo == "gnn" else 0, d_out=d_emb)
                    if modo != "ninguno" else None)
        d_in = d_num + d_cat + (d_emb if modo != "ninguno" else 0)
        self.mlp = nn.Sequential(nn.Linear(d_in, HIDDEN[0]), nn.ReLU(), nn.Dropout(dropout),
                                 nn.Linear(HIDDEN[0], HIDDEN[1]), nn.ReLU(), nn.Dropout(dropout),
                                 nn.Linear(HIDDEN[1], 1))

    def nodos(self, x_num_n, x_cat_n, adj):
        return self.enc(x_num_n, x_cat_n, adj if self.modo == "gnn" else [])

    def forward(self, xnum, xcat, nodo, z_nodos=None):
        parts = [xnum] + [e(xcat[:, i]) for i, e in enumerate(self.emb)]
        if self.enc is not None:
            parts.append(z_nodos[nodo])
        return self.mlp(torch.cat(parts, dim=1)).squeeze(1)


@dataclass
class ConjuntoT2:
    num: np.ndarray
    cat: np.ndarray
    nodo: np.ndarray
    y: np.ndarray


def predecir(model: RedT2, c: ConjuntoT2, grafo_t: Tuple, adj, device, lote: int = 32768) -> np.ndarray:
    model.eval()
    out = []
    with torch.no_grad():
        z = model.nodos(grafo_t[0], grafo_t[1], adj) if model.enc is not None else None
        for i in range(0, len(c.y), lote):
            s = slice(i, i + lote)
            logit = model(torch.as_tensor(c.num[s], device=device), torch.as_tensor(c.cat[s], device=device),
                          torch.as_tensor(c.nodo[s], device=device), z)
            out.append(torch.sigmoid(logit).cpu().numpy())
    return np.concatenate(out).astype("float64")


def entrenar(tr: ConjuntoT2, va: ConjuntoT2, cards: Sequence[int], d: DatosGrafo, modo: str, semilla: int, device,
             usar_co: bool = True, max_epocas: int = MAX_EPOCAS, eval_cada: Optional[int] = None,
             paciencia: int = PACIENCIA) -> Dict:
    """``eval_cada``: evaluate on valid every that many optimizer steps (default: once per epoch); early stopping
    counts evaluations without improvement (``paciencia``)."""
    torch.manual_seed(semilla)
    np.random.seed(semilla)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    n = len(d.nodos)
    adj = adyacencias(d.aristas, d.co, n, device, usar_co) if modo == "gnn" else []
    grafo_t = _tensores(d, device)
    model = RedT2(tr.num.shape[1], cards, d.x_num.shape[1], d.cards, len(adj), modo).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=WD)
    xnum, xcat = torch.as_tensor(tr.num, device=device), torch.as_tensor(tr.cat, device=device)
    xnodo, y = torch.as_tensor(tr.nodo, device=device), torch.as_tensor(tr.y.astype("float32"), device=device)
    gen = torch.Generator(device="cpu").manual_seed(semilla)
    mejor, mejor_estado, mejor_ep, sin_mejora, hist, pasos = -1.0, None, 0.0, 0, [], 0
    pasos_por_epoca = math.ceil(len(y) / BATCH)
    cada = eval_cada or pasos_por_epoca
    t0 = time.perf_counter()
    parar = False

    def evaluar_valid():
        nonlocal mejor, mejor_ep, sin_mejora, mejor_estado, parar
        p = predecir(model, va, grafo_t, adj, device)
        ap = float(average_precision_score(va.y, p))
        hist.append(ap)
        if ap > mejor + 1e-5:
            mejor, mejor_ep, sin_mejora = ap, pasos / pasos_por_epoca, 0
            mejor_estado = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            sin_mejora += 1
            parar = sin_mejora >= paciencia
        model.train()

    for ep in range(max_epocas):
        model.train()
        perm = torch.randperm(len(y), generator=gen).to(device)
        for i in range(0, len(y), BATCH):
            idx = perm[i:i + BATCH]
            z = model.nodos(grafo_t[0], grafo_t[1], adj) if model.enc is not None else None
            loss = nn.functional.binary_cross_entropy_with_logits(model(xnum[idx], xcat[idx], xnodo[idx], z), y[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            pasos += 1
            if pasos % cada == 0:
                evaluar_valid()
                if parar:
                    break
        if parar:
            break
    if not hist or pasos % cada != 0 and not parar:
        evaluar_valid()
    model.load_state_dict(mejor_estado)
    seg = time.perf_counter() - t0
    gpu = (torch.cuda.max_memory_allocated(device) / 2 ** 20) if device.type == "cuda" else 0.0
    return {"model": model, "grafo_t": grafo_t, "adj": adj, "ap_valid": mejor, "mejor_epoca": mejor_ep,
            "epocas": pasos / pasos_por_epoca, "evaluaciones": len(hist), "hist_ap": hist, "segundos": seg, "gpu_pico_mb": gpu,
            "n_parametros": int(sum(p.numel() for p in model.parameters()))}
