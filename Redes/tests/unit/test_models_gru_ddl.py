"""GRU shapes/determinism and static checks on migration 011 (no database)."""
import re
from pathlib import Path

import pytest

from pipelines.migrate import validate_sql

DDL = Path(__file__).resolve().parents[2] / "sql" / "core" / "011_snapshot_t1.sql"


def test_migration_011_passes_the_schema_guard_and_only_creates():
    statements = validate_sql(DDL.read_text(encoding="utf-8"), DDL.name)
    assert statements and all(s.upper().startswith("CREATE") for s in statements)


def test_snapshot_ddl_keeps_sex_for_fairness_only_and_has_no_personal_columns():
    text = DDL.read_text(encoding="utf-8")
    cols = set(re.findall(r"^\s+(\w+)\s+(?:text|integer|bigint|numeric|boolean)\b", text, re.M))
    assert "sexo_equidad" in cols and "sexo" not in cols
    for bad in ("rut", "nombre", "correo", "email", "telefono", "nacimiento"):
        assert bad not in cols


def test_gru_forward_shapes_and_seed_determinism():
    torch = pytest.importorskip("torch")
    np = pytest.importorskip("numpy")
    pytest.importorskip("sklearn")
    from models import gru as G

    rng = np.random.default_rng(0)
    n, k, d = 256, 2, 13
    c = G.Conjunto(rng.random((n, k, d), dtype="float32"), rng.random((n, 6), dtype="float32"),
                   rng.integers(0, 3, (n, 2)), (rng.random(n) < 0.3).astype("int8"))
    cpu = torch.device("cpu")
    r1 = G.entrenar(c, c, [3, 3], seed=1, device=cpu)
    p1 = G.predecir(r1["model"], c, cpu)
    assert p1.shape == (n,) and ((0 <= p1) & (p1 <= 1)).all()
    assert r1["n_parametros"] > 0 and G.HIDDEN <= 64
    r2 = G.entrenar(c, c, [3, 3], seed=1, device=cpu)
    np.testing.assert_allclose(G.predecir(r2["model"], c, cpu), p1, rtol=1e-5, atol=1e-6)
