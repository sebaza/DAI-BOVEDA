"""Rebuild and persistence of the kept models (evaluation/modelos_conservados.py): the reproduction gate and the round trip."""
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from evaluation import modelos_conservados as MC


class Falso:
    """Stub model: returns what it is told for the rows it is given."""
    tarea, k, nombre = "t1", 1, "cb_acad"

    def __init__(self, devuelve):
        self.devuelve = devuelve

    def predecir(self, filas, sem=None):
        return self.devuelve


@pytest.fixture
def guardadas(tmp_path, monkeypatch):
    """Saved predictions of one key, in a different row order than the rows the model scores."""
    ids = np.array([11, 12, 13, 14])
    p = np.array([0.1, 0.4, 0.7, 0.9])
    monkeypatch.setattr(MC, "_filas_de_verificacion", lambda modelo, conn: (pd.DataFrame({"episodio_id": ids[::-1]}), None))
    monkeypatch.setattr(MC, "_predicciones_guardadas", lambda modelo, artefactos: (ids, p))
    return tmp_path, p[::-1]


def test_verificar_raises_when_predictions_differ(guardadas):
    tmp, p = guardadas
    with pytest.raises(MC.ReproduccionFallida):
        MC.verificar(Falso(p + 0.01), None, tmp)


def test_verificar_passes_on_identical_predictions(guardadas):
    tmp, p = guardadas                       # rows are reversed on purpose: the alignment is by id, not by position
    assert MC.verificar(Falso(p), None, tmp) == 0.0


def test_verificar_rejects_rows_that_are_not_the_saved_ones(guardadas, monkeypatch):
    tmp, p = guardadas
    monkeypatch.setattr(MC, "_filas_de_verificacion", lambda modelo, conn: (pd.DataFrame({"episodio_id": [11, 12, 13, 99]}), None))
    with pytest.raises(MC.ReproduccionFallida):
        MC.verificar(Falso(p), None, tmp)


def test_claves_match_the_kept_models_of_the_plan():
    assert MC.CLAVES == (("t1", 1, "cb_acad"), ("t1", 1, "cb_ben_pit"), ("t1", 2, "lr_acad"), ("t2", 0, "cb_c_nuevas"),
                         ("t3", 0, "dt_lr_adm"), ("t3", 2, "nn_gru"), ("t3", 4, "nn_gru"), ("t5", 2, "gru_adm"), ("t5", 4, "gru_agg"))


def test_unknown_key_is_refused():
    with pytest.raises(ValueError):
        MC.ajustar(None, "t1", 9, "no_existe")


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_persisted_model_round_trips(tmp_path, monkeypatch):
    """Tiny logistic fit: saved once, then ``cargar_o_ajustar`` reloads it without refitting and the predictions are identical."""
    rng = np.random.default_rng(0)
    x = rng.normal(size=(200, 3))
    y = (x[:, 0] + rng.normal(size=200) > 0).astype(int)
    prep = MC.D.Preprocesador(["a", "b", "c"], []).fit(pd.DataFrame(x, columns=list("abc")))
    lr = LogisticRegression().fit(prep.transform(pd.DataFrame(x, columns=list("abc"))), y)
    modelo = MC.ModeloConservado("t1", 2, "lr_acad", "t1_lr", {"prep": prep, "lr": lr})
    MC.guardar(modelo, tmp_path)
    assert (tmp_path / "modelos" / "t1_k2_lr_acad.joblib").exists()

    def no_ajustar(*a, **k):
        raise AssertionError("must not refit")

    visto = []
    monkeypatch.setattr(MC, "ajustar", no_ajustar)
    monkeypatch.setattr(MC, "verificar", lambda m, conn, artefactos, tol=1e-4: visto.append(m) or 0.0)
    cargado = MC.cargar_o_ajustar(None, "t1", 2, "lr_acad", tmp_path)
    assert visto == [cargado], "verificar must always run before returning"
    filas = pd.DataFrame(x, columns=list("abc"))
    assert np.array_equal(cargado.predecir(filas, None), modelo.predecir(filas, None))


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_missing_file_fits_saves_and_verifies(tmp_path, monkeypatch):
    prep = MC.D.Preprocesador(["a"], []).fit(pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0]}))
    lr = LogisticRegression().fit(prep.transform(pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0]})), [0, 0, 1, 1])
    hechos = []
    monkeypatch.setattr(MC, "ajustar", lambda conn, t, k, n: hechos.append("ajustar") or MC.ModeloConservado(t, k, n, "t1_lr", {"prep": prep, "lr": lr}))
    monkeypatch.setattr(MC, "verificar", lambda m, conn, artefactos, tol=1e-4: hechos.append("verificar") or 0.0)
    MC.cargar_o_ajustar(None, "t1", 2, "lr_acad", tmp_path)
    assert hechos == ["ajustar", "verificar"] and (tmp_path / "modelos" / "t1_k2_lr_acad.joblib").exists()


def test_verificar_fails_closed_on_nan_in_saved_or_computed_predictions(guardadas, monkeypatch):
    tmp, p = guardadas
    ids = np.array([11, 12, 13, 14])
    guardadas_nan = np.array([0.1, np.nan, 0.7, 0.9])
    monkeypatch.setattr(MC, "_predicciones_guardadas", lambda modelo, artefactos: (ids, guardadas_nan))
    with pytest.raises(MC.ReproduccionFallida):
        MC.verificar(Falso(p), None, tmp)
    monkeypatch.setattr(MC, "_predicciones_guardadas", lambda modelo, artefactos: (ids, p[::-1]))
    with pytest.raises(MC.ReproduccionFallida):
        MC.verificar(Falso(np.where(p > 0.5, np.nan, p)), None, tmp)
