"""Model 4: small GRU over the semester vectors 1..k plus an embedding of the static pre-entry profile.

The sequence carries the academic history; the static branch carries only pre-entry facts. Hidden size <= 64, early
stopping on the validation AP, several seeds. Training time and peak GPU memory are measured.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional, Sequence

import numpy as np
import torch
from sklearn.metrics import average_precision_score
from torch import nn

HIDDEN = 48
STATIC_DIM = 32
EMB_MAX = 8
BATCH = 512
MAX_EPOCHS = 60
PACIENCIA = 8
LR = 2e-3
WD = 1e-4


class RedGRU(nn.Module):
    def __init__(self, d_seq: int, n_num: int, cardinalidades: Sequence[int], hidden: int = HIDDEN,
                 static_dim: int = STATIC_DIM, dropout: float = 0.2):
        super().__init__()
        self.embs = nn.ModuleList([nn.Embedding(c, min(EMB_MAX, max(2, (c + 1) // 2))) for c in cardinalidades])
        d_emb = sum(e.embedding_dim for e in self.embs)
        self.estatico = nn.Sequential(nn.Linear(n_num + d_emb, static_dim), nn.ReLU(), nn.Dropout(dropout))
        self.gru = nn.GRU(d_seq, hidden, batch_first=True)
        self.cabeza = nn.Sequential(nn.Linear(hidden + static_dim, 64), nn.ReLU(), nn.Dropout(dropout),
                                    nn.Linear(64, 1))

    def forward(self, seq, num, cats):
        emb = [e(cats[:, i]) for i, e in enumerate(self.embs)]
        s = self.estatico(torch.cat([num, *emb], dim=1))
        _, h = self.gru(seq)
        return self.cabeza(torch.cat([h[-1], s], dim=1)).squeeze(1)


@dataclass
class Conjunto:
    seq: np.ndarray
    num: np.ndarray
    cats: np.ndarray
    y: Optional[np.ndarray] = None


def _tensores(c: Conjunto, device):
    return (torch.as_tensor(c.seq, device=device), torch.as_tensor(c.num, device=device),
            torch.as_tensor(c.cats, device=device))


@torch.no_grad()
def predecir(model: RedGRU, c: Conjunto, device, lote: int = 4096) -> np.ndarray:
    model.eval()
    seq, num, cats = _tensores(c, device)
    out = [torch.sigmoid(model(seq[i:i + lote], num[i:i + lote], cats[i:i + lote])).float().cpu().numpy()
           for i in range(0, len(seq), lote)]
    return np.concatenate(out).astype("float64")


def entrenar(train: Conjunto, valid: Conjunto, cardinalidades: Sequence[int], seed: int, device=None) -> Dict:
    """Train one seed. Returns the model, the best epoch, valid AP, time and peak GPU memory (MB)."""
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(seed)
    np.random.seed(seed)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
        torch.cuda.manual_seed_all(seed)
    model = RedGRU(train.seq.shape[2], train.num.shape[1], cardinalidades).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WD)
    loss_fn = nn.BCEWithLogitsLoss()
    seq, num, cats = _tensores(train, device)
    y = torch.as_tensor(train.y.astype("float32"), device=device)
    gen = torch.Generator(device="cpu").manual_seed(seed)
    mejor = {"ap": -1.0, "epoca": 0, "estado": None}
    t0 = time.perf_counter()
    for epoca in range(1, MAX_EPOCHS + 1):
        model.train()
        perm = torch.randperm(len(y), generator=gen).to(device)
        for i in range(0, len(y), BATCH):
            b = perm[i:i + BATCH]
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(seq[b], num[b], cats[b]), y[b])
            loss.backward()
            opt.step()
        ap = float(average_precision_score(valid.y, predecir(model, valid, device)))
        if ap > mejor["ap"]:
            mejor = {"ap": ap, "epoca": epoca,
                     "estado": {k: v.detach().clone() for k, v in model.state_dict().items()}}
        elif epoca - mejor["epoca"] >= PACIENCIA:
            break
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    segundos = time.perf_counter() - t0
    model.load_state_dict(mejor["estado"])
    return {
        "model": model, "ap_valid": mejor["ap"], "mejor_epoca": mejor["epoca"], "epocas_corridas": epoca,
        "segundos": segundos,
        "gpu_pico_mb": (torch.cuda.max_memory_allocated(device) / 2**20) if device.type == "cuda" else 0.0,
        "dispositivo": str(device), "n_parametros": int(sum(p.numel() for p in model.parameters())),
    }
