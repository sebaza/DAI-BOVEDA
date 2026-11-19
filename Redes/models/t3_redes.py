"""Neural discrete-time competing-risks models of T3: an MLP and a GRU over the semester sequence up to the cut.

Both emit, for every semester after the cut ``u = 1 .. U``, the logits of a 3-way softmax {survives, egress, exit}: the
cause-specific discrete hazards (a "cause-specific softmax" head, i.e. the likelihood of the person-period models but in
one pass per episode). The loss is the exact discrete-time likelihood with censoring: an episode contributes the
semesters ``1 .. obs`` (class 0 until the last one, whose class is its cause). It is NOT DeepHit (no joint softmax over
(time, cause), no ranking loss). Early stopping on the validation negative log-likelihood, several seeds, GPU.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional, Sequence

import numpy as np
import torch
from torch import nn
from torch.nn import functional as Fn

from models.t3_data import cif_desde_riesgos

HIDDEN = (128, 64)
GRU_HIDDEN = 48
EMB_MAX = 8
BATCH = 256
MAX_EPOCHS = 120
PACIENCIA = 12
LR = 2e-3
WD = 1e-4


class RedRiesgos(nn.Module):
    def __init__(self, n_num: int, cardinalidades: Sequence[int], U: int, d_seq: Optional[int] = None,
                 hidden: Sequence[int] = HIDDEN, dropout: float = 0.2, gru_hidden: int = GRU_HIDDEN):
        super().__init__()
        self.U = U
        self.embs = nn.ModuleList([nn.Embedding(c, min(EMB_MAX, max(2, (c + 1) // 2))) for c in cardinalidades])
        d_in = n_num + sum(e.embedding_dim for e in self.embs)
        capas, d = [], d_in
        for h in hidden[:-1]:
            capas += [nn.Linear(d, h), nn.ReLU(), nn.Dropout(dropout)]
            d = h
        self.tronco = nn.Sequential(*capas)
        self.gru = nn.GRU(d_seq, gru_hidden, batch_first=True) if d_seq else None
        d_cab = d + (gru_hidden if d_seq else 0)
        self.cabeza = nn.Sequential(nn.Linear(d_cab, hidden[-1]), nn.ReLU(), nn.Dropout(dropout),
                                    nn.Linear(hidden[-1], U * 3))

    def forward(self, num, cats, seq=None):
        x = torch.cat([num, *[e(cats[:, i]) for i, e in enumerate(self.embs)]], dim=1)
        h = self.tronco(x)
        if self.gru is not None:
            _, g = self.gru(seq)
            h = torch.cat([h, g[-1]], dim=1)
        return self.cabeza(h).view(-1, self.U, 3)


@dataclass
class ConjuntoT3:
    num: np.ndarray
    cats: np.ndarray
    u: np.ndarray                       # semesters observed after the cut (1..U)
    causa: np.ndarray                   # 0 censored, 1 egress, 2 exit
    seq: Optional[np.ndarray] = None


def _tensores(c: ConjuntoT3, device):
    t = lambda a, dt: torch.as_tensor(a, dtype=dt, device=device)          # noqa: E731
    seq = t(c.seq, torch.float32) if c.seq is not None else None
    return t(c.num, torch.float32), t(c.cats, torch.int64), seq, t(c.u, torch.int64), t(c.causa, torch.int64)


def nll(logits: torch.Tensor, u: torch.Tensor, causa: torch.Tensor) -> torch.Tensor:
    """Mean discrete-time negative log-likelihood per episode (semesters ``1..u``, class = cause in the last one)."""
    B, U, _ = logits.shape
    pos = torch.arange(1, U + 1, device=logits.device)[None, :]
    objetivo = torch.where(pos == u[:, None], causa[:, None], torch.zeros_like(pos.expand(B, U)))
    perdida = Fn.cross_entropy(logits.reshape(-1, 3), objetivo.reshape(-1), reduction="none").view(B, U)
    return (perdida * (pos <= u[:, None])).sum(dim=1).mean()


@torch.no_grad()
def predecir_cif(model: RedRiesgos, c: ConjuntoT3, device, lote: int = 4096) -> np.ndarray:
    model.eval()
    num, cats, seq, _, _ = _tensores(c, device)
    h1, h2 = [], []
    for i in range(0, len(num), lote):
        p = torch.softmax(model(num[i:i + lote], cats[i:i + lote], None if seq is None else seq[i:i + lote]), dim=2)
        h1.append(p[:, :, 1].double().cpu().numpy())
        h2.append(p[:, :, 2].double().cpu().numpy())
    return cif_desde_riesgos(np.concatenate(h1), np.concatenate(h2))["F1"]


@torch.no_grad()
def _nll_valid(model, c: ConjuntoT3, device) -> float:
    model.eval()
    num, cats, seq, u, causa = _tensores(c, device)
    total = 0.0
    for i in range(0, len(num), 4096):
        sl = slice(i, i + 4096)
        lg = model(num[sl], cats[sl], None if seq is None else seq[sl])
        total += float(nll(lg, u[sl], causa[sl])) * len(lg)
    return total / len(num)


def entrenar(train: ConjuntoT3, valid: ConjuntoT3, cardinalidades: Sequence[int], U: int, seed: int, device=None) -> Dict:
    """Train one seed. Returns the model, the best epoch, valid NLL, time and peak GPU memory (MB)."""
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(seed)
    np.random.seed(seed)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
        torch.cuda.manual_seed_all(seed)
    d_seq = None if train.seq is None else train.seq.shape[2]
    model = RedRiesgos(train.num.shape[1], cardinalidades, U, d_seq).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WD)
    num, cats, seq, u, causa = _tensores(train, device)
    gen = torch.Generator(device="cpu").manual_seed(seed)
    mejor = {"nll": float("inf"), "epoca": 0, "estado": None}
    t0 = time.perf_counter()
    for epoca in range(1, MAX_EPOCHS + 1):
        model.train()
        perm = torch.randperm(len(u), generator=gen).to(device)
        for i in range(0, len(u), BATCH):
            b = perm[i:i + BATCH]
            opt.zero_grad(set_to_none=True)
            loss = nll(model(num[b], cats[b], None if seq is None else seq[b]), u[b], causa[b])
            loss.backward()
            opt.step()
        v = _nll_valid(model, valid, device)
        if v < mejor["nll"]:
            mejor = {"nll": v, "epoca": epoca, "estado": {k: x.detach().clone() for k, x in model.state_dict().items()}}
        elif epoca - mejor["epoca"] >= PACIENCIA:
            break
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    segundos = time.perf_counter() - t0
    model.load_state_dict(mejor["estado"])
    return {"model": model, "nll_valid": mejor["nll"], "mejor_epoca": mejor["epoca"], "epocas_corridas": epoca,
            "segundos": segundos,
            "gpu_pico_mb": (torch.cuda.max_memory_allocated(device) / 2 ** 20) if device.type == "cuda" else 0.0,
            "dispositivo": str(device), "n_parametros": int(sum(p.numel() for p in model.parameters()))}
