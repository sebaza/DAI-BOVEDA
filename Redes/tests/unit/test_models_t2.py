"""T2 models on synthetic data: course graph, GraphSAGE shapes/determinism, link prediction learns structure,
end-to-end net trains and respects the leakage guards of the preprocessing. No database."""
import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
torch = pytest.importorskip("torch")
pytest.importorskip("sklearn")

from models import t2_data as TD   # noqa: E402
from models import t2_grafo as G    # noqa: E402


def _grafo(n=60, seed=0):
    """Two clusters of courses; prerequisite edges only inside a cluster, attributes correlated with the cluster."""
    rng = np.random.default_rng(seed)
    nodos = pd.Index([f"C{i}" for i in range(n)])
    clus = np.arange(n) % 2
    malla = pd.DataFrame({"cod_programa": "P", "codigo_asignatura": nodos, "semestre": 1 + (np.arange(n) // 12),
                          "creditos": 6.0 + clus, "depto": np.where(clus == 0, "X", "Y"), "formacion": "f"})
    edges = []
    for i in range(n):
        for j in range(i + 2, n, 2):
            if rng.random() < 0.25:
                edges.append((nodos[i], nodos[j]))
    pre = pd.DataFrame(edges, columns=["codigo_requisito", "codigo_asignatura"])
    pre["cod_programa"], pre["catalogo"] = "P", "1"
    stats = pd.DataFrame({"codigo": nodos, "n": 100, "aprob": 80})
    return G.construir_datos(nodos, malla, pre, stats)


def test_graph_data_shapes_and_edges():
    d = _grafo()
    assert d.x_num.shape[0] == 60 and d.x_cat.shape == (60, 2) and len(d.cards) == 2
    assert d.aristas.shape[1] == 2 and (d.aristas[:, 0] != d.aristas[:, 1]).all()
    assert np.isfinite(d.x_num).all()


def test_adjacencies_are_row_normalised_means():
    d = _grafo()
    adj = G.adyacencias(d.aristas, np.zeros((0, 2), "int64"), 60, torch.device("cpu"), usar_co=False)
    assert len(adj) == 2
    sums = torch.sparse.sum(adj[0], dim=1).to_dense().numpy()
    assert set(np.round(sums[sums > 0], 5)) == {1.0}


def test_coenrollment_pairs_respect_the_minimum_count():
    g = np.repeat(np.arange(40), 2)
    nodo = np.tile([0, 1], 40)
    assert G.pares_coinscripcion(g, nodo, minimo=30).tolist() == [[0, 1]]
    assert len(G.pares_coinscripcion(g, nodo, minimo=41)) == 0


def test_link_prediction_learns_the_structure_and_is_deterministic():
    d = _grafo()
    r1 = G.entrenar_enlaces(d, semilla=1, epocas=120, usar_co=False)
    r2 = G.entrenar_enlaces(d, semilla=1, epocas=120, usar_co=False)
    assert r1["embeddings"].shape == (60, 32)
    assert r1["ap_enlaces"] > 0.6 and r1["auc_enlaces"] > 0.6
    assert np.allclose(r1["embeddings"], r2["embeddings"], atol=1e-5)


def test_end_to_end_net_trains_and_modes_differ_only_by_the_graph():
    d = _grafo()
    rng = np.random.default_rng(0)
    n = 1200
    nodo = rng.integers(0, 60, n)
    num = rng.normal(size=(n, 5)).astype("float32")
    cat = rng.integers(0, 3, (n, 2))
    y = ((num[:, 0] + (nodo % 2) + rng.normal(0, .5, n)) > 1).astype("int8")
    c = G.ConjuntoT2(num, cat, nodo, y)
    cpu = torch.device("cpu")
    for modo in ("gnn", "mlp", "ninguno"):
        r = G.entrenar(c, c, [3, 3], d, modo, semilla=0, device=cpu, usar_co=False, max_epocas=4)
        p = G.predecir(r["model"], c, r["grafo_t"], r["adj"], cpu)
        assert p.shape == (n,) and ((0 <= p) & (p <= 1)).all() and r["n_parametros"] > 0
        assert r["ap_valid"] > y.mean()                                   # learns something
    assert len(G.entrenar(c, c, [3, 3], d, "gnn", 0, cpu, usar_co=False, max_epocas=1)["adj"]) == 2


def test_preprocessor_is_fitted_on_train_only_and_rejects_forbidden_columns():
    tr = pd.DataFrame({"a": [1.0, 2.0, 3.0, None], "c": ["x", "x", "y", None]})
    te = pd.DataFrame({"a": [100.0, None], "c": ["z", "x"]})
    p = TD.PreprocesadorT2(["a"], ["c"], min_count=2).fit(tr)
    assert p.medianas["a"] == 2.0 and p.vocab["c"] == ["x"]
    x = p.transform_num(te)
    assert x.shape == (2, 2) and x[1, 1] == 1.0                           # missing indicator of the second row
    assert p.transform_cat_codes(te).tolist() == [[0], [1]]               # unseen category -> 0
    with pytest.raises(ValueError):
        TD.PreprocesadorT2(["y"], [])
    with pytest.raises(ValueError):
        TD.PreprocesadorT2(["a"], ["sexo_equidad"])


def test_feature_sets_are_nested_and_exclude_sex_and_labels():
    a, b, c, d = (set(TD.CONJUNTOS[k][0]) for k in "abcd")
    assert a < b < c < d
    for num, cat in TD.CONJUNTOS.values():
        assert not TD.PRIOR_OUTCOME & (set(num) | set(cat))
