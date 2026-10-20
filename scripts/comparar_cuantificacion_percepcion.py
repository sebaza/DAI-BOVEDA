"""El indice de Percepcion es PCC. Esto mide cuanto le cuesta eso, en puntos.

QUE ES ESTO
El indice `50 + 50*(Sum p_pos - Sum p_neg)/n` es una transformacion afin de
**Probabilistic Classify and Count** (Bella, Ferri, Hernandez-Orallo &
Ramirez-Quintana, IEEE ICDM 2010), un metodo del subcampo de *quantification*
(estimacion de prevalencia). No es un diseno propio, y la literatura lo reporta
como sesgado: Moreo & Sebastiani (PLOS ONE 2022) miden que "PCC always performs
worse than CC in our experiments, on all datasets and for both performance
measures".

Este script contrasta PCC contra los cuatro metodos de referencia usando las
anotaciones humanas como verdad, y reporta el error en PUNTOS DE INDICE, que es
la unidad en la que alguien decide algo.

  CC    Classify and Count: contar etiquetas duras.
  PCC   Probabilistic CC. EL METODO ACTUAL.
  ACC   Adjusted CC (Forman 2008): corrige con la matriz de confusion.
  PACC  Probabilistic Adjusted CC (Bella et al. 2010).
  SLD   Saerens, Latinne & Decaestecker (2002): EM sobre el prior de test.

Se implementan a mano y no con QuaPy a proposito: son cinco funciones cortas, y
no vale meter una dependencia nueva en el venv que corre produccion para esto.

TRES TRAMPAS DEL DATO, APRENDIDAS CONTRA LA BASE REAL
  1. `percepcion_correccion.prob_*_orig` NO sirve como entrada: esas
     probabilidades estan desincronizadas de su propia etiqueta (argmax coincide
     con `valor_original` solo el 69% de las veces). Se usan las de
     `percepcion_score`, que son las que el indice realmente consume.
  2. Hay que EXCLUIR los scores con `correccion_manual` en el nombre del modelo:
     ahi la etiqueta humana fue escrita de vuelta al score, asi que evaluar
     contra ella es circular. Son 277 de 632 anotaciones.
  3. Solo `origen_muestra='aleatorio'`. Las colas `adversos`, `duda` y
     `estratificado` estan dirigidas: incluirlas sesga la prevalencia medida.

Correr con:
    backend\\.venv\\Scripts\\python.exe scripts/comparar_cuantificacion_percepcion.py

Lee la base del worker en SOLO LECTURA. No escribe nada.
"""
from __future__ import annotations

import sqlite3

import numpy as np

DB = "../Sentiment_Analisys_University/percepcion_real.db"
CLASES = ["NEG", "NEU", "POS"]
IDX = {c: i for i, c in enumerate(CLASES)}
I_NEG, I_POS = 0, 2


def cargar():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    filas = con.execute(
        """
        SELECT k.valor_nuevo, s.prob_neg, s.prob_neu, s.prob_pos
        FROM percepcion_correccion k
        JOIN percepcion_score s ON s.comentario_id = k.comentario_id
        WHERE k.campo = 'sentimiento'
          AND k.autor_tipo = 'humano'
          AND k.origen_muestra = 'aleatorio'
          AND k.valor_nuevo IN ('NEG','NEU','POS')
          AND s.prob_pos IS NOT NULL
          AND s.modelo NOT LIKE '%correccion_manual%'
        """
    ).fetchall()
    con.close()
    P = np.array([[f[1], f[2], f[3]] for f in filas], dtype=float)
    P /= P.sum(axis=1, keepdims=True)
    y = np.array([IDX[f[0]] for f in filas], dtype=int)
    return P, y


def indice(prev):
    return 50.0 + 50.0 * (prev[I_POS] - prev[I_NEG])


def _simplex(v):
    v = np.clip(v, 0.0, None)
    s = v.sum()
    return v / s if s > 0 else np.full(len(v), 1.0 / len(v))


def cc(P):
    return np.bincount(P.argmax(axis=1), minlength=3) / len(P)


def pcc(P):
    return P.mean(axis=0)


def _M(Ptr, ytr, blanda):
    M = np.zeros((3, 3))
    dur = None if blanda else Ptr.argmax(axis=1)
    for k in range(3):
        sel = ytr == k
        if sel.sum():
            M[:, k] = Ptr[sel].mean(axis=0) if blanda else \
                np.bincount(dur[sel], minlength=3) / sel.sum()
    return M


def _ajustar(M, obs):
    try:
        p = np.linalg.solve(M, obs)
    except np.linalg.LinAlgError:
        p = np.linalg.lstsq(M, obs, rcond=None)[0]
    return _simplex(p)


def sld(P, prior_tr, iters=1000, tol=1e-8):
    prior_tr = np.clip(prior_tr, 1e-12, None)
    prior = prior_tr.copy()
    for _ in range(iters):
        num = P * (prior / prior_tr)
        post = num / np.clip(num.sum(axis=1, keepdims=True), 1e-12, None)
        nuevo = post.mean(axis=0)
        if np.abs(nuevo - prior).max() < tol:
            return _simplex(nuevo)
        prior = nuevo
    return _simplex(prior)


def calibracion(P, y, bins=10):
    conf, pred = P.max(axis=1), P.argmax(axis=1)
    acierto = (pred == y).astype(float)
    bordes = np.linspace(0, 1, bins + 1)
    ece, det = 0.0, []
    for b in range(bins):
        lo, hi = bordes[b], bordes[b + 1]
        sel = (conf > lo) & (conf <= hi) if b else (conf >= lo) & (conf <= hi)
        if sel.sum():
            cm, am = conf[sel].mean(), acierto[sel].mean()
            ece += sel.sum() / len(y) * abs(cm - am)
            det.append((lo, hi, int(sel.sum()), cm, am))
    oh = np.zeros_like(P)
    oh[np.arange(len(y)), y] = 1.0
    return ece, ((P - oh) ** 2).sum(axis=1).mean(), acierto.mean(), det


def grilla(paso=0.1):
    v = np.round(np.arange(0, 1 + 1e-9, paso), 6)
    out = []
    for a in v:
        for b in v:
            c = round(1.0 - a - b, 6)
            if c >= -1e-9:
                out.append(_simplex(np.array([a, b, max(c, 0.0)])))
    return out


def evaluar(P, y, n, prevs, repes, semilla=20260922):
    rng = np.random.default_rng(semilla)
    folds = np.array_split(rng.permutation(len(y)), 5)
    err = {m: [] for m in ("CC", "PCC", "ACC", "PACC", "SLD")}
    err_i = {m: [] for m in err}
    sesgo_i = {m: [] for m in err}
    for f in range(5):
        te = folds[f]
        tr = np.concatenate([folds[j] for j in range(5) if j != f])
        Ptr, ytr, Pte, yte = P[tr], y[tr], P[te], y[te]
        Md, Mb = _M(Ptr, ytr, False), _M(Ptr, ytr, True)
        prior = np.bincount(ytr, minlength=3) / len(ytr)
        porc = [np.where(yte == k)[0] for k in range(3)]
        if min(len(v) for v in porc) == 0:
            continue
        for prev in prevs:
            for _ in range(repes):
                cu = rng.multinomial(n, prev)
                sel = np.concatenate([rng.choice(porc[k], q, replace=True)
                                      for k, q in enumerate(cu) if q])
                Ps, ys = Pte[sel], yte[sel]
                real = np.bincount(ys, minlength=3) / len(ys)
                for m, p in (("CC", cc(Ps)), ("PCC", pcc(Ps)),
                             ("ACC", _ajustar(Md, cc(Ps))), ("PACC", _ajustar(Mb, pcc(Ps))),
                             ("SLD", sld(Ps, prior))):
                    err[m].append(np.abs(p - real).mean())
                    err_i[m].append(abs(indice(p) - indice(real)))
                    sesgo_i[m].append(indice(p) - indice(real))
    return err, err_i, sesgo_i


def tabla(titulo, err, err_i, sesgo_i):
    print(f"\n{titulo}")
    print(f"  {'metodo':6s} {'AE':>8s} {'|err| idx':>10s} {'sesgo idx':>10s} {'p95 idx':>9s}")
    for m in sorted(err, key=lambda k: np.mean(err_i[k])):
        marca = "   <- ACTUAL" if m == "PCC" else ""
        print(f"  {m:6s} {np.mean(err[m]):8.4f} {np.mean(err_i[m]):10.2f} "
              f"{np.mean(sesgo_i[m]):+10.2f} {np.percentile(err_i[m], 95):9.2f}{marca}")


def main():
    P, y = cargar()
    real = np.bincount(y, minlength=3) / len(y)
    print(f"Set de evaluacion LIMPIO (humano + aleatorio, sin correccion_manual): {len(y)}")
    print(f"  NEG {np.sum(y==0)}  NEU {np.sum(y==1)}  POS {np.sum(y==2)}")
    print(f"  verdad humana   -> indice {indice(real):.2f}   {np.round(real,3)}")
    print(f"  PCC (actual)    -> indice {indice(pcc(P)):.2f}   {np.round(pcc(P),3)}")
    print(f"  CC              -> indice {indice(cc(P)):.2f}   {np.round(cc(P),3)}")

    ece, brier, ac, det = calibracion(P, y)
    print(f"\n=== CALIBRACION ===  accuracy {ac:.4f}   ECE {ece:.4f}   Brier {brier:.4f}")
    print(f"  {'bin':>10s} {'n':>5s} {'confianza':>10s} {'acierto':>9s} {'gap':>8s}")
    for lo, hi, k, cm, am in det:
        print(f"  {lo:.1f}-{hi:.1f}{'':2s} {k:5d} {cm:10.3f} {am:9.3f} {cm-am:+8.3f}")

    g = grilla(0.1)
    for n in (40, 100):
        tabla(f"=== APP (prior shift), n={n}, {len(g)} prevalencias x 20 ===",
              *evaluar(P, y, n, g, 20))
    for n in (40, 100):
        tabla(f"=== PREVALENCIA NATURAL, n={n} (el caso real) ===",
              *evaluar(P, y, n, [real], 400))


main()
