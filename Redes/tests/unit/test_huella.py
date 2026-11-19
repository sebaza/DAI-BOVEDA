"""Key fingerprint guard: the current HMAC key must match the one used for the existing loads."""
import pytest

from pipelines.common import huella as H
from pipelines.common.pseudo import key_fingerprint


class FakeCursor:
    def __init__(self, store):
        self.store = store
        self._row = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        s = " ".join(sql.split()).lower()
        if s.startswith("select huella"):
            self._row = (self.store["huella"],) if self.store["huella"] else None
        elif s.startswith("insert into"):
            self.store["huella"] = params[0]
            self.store["inserts"] += 1

    def fetchone(self):
        return self._row


class FakeConn:
    def __init__(self, huella=None):
        self.store = {"huella": huella, "inserts": 0}
        self.commits = 0

    def cursor(self):
        return FakeCursor(self.store)

    def commit(self):
        self.commits += 1


def test_empty_table_registers_the_fingerprint():
    conn = FakeConn()
    assert H.verificar_o_registrar(conn, "k1") == "registrada"
    assert conn.store["huella"] == key_fingerprint("k1") and conn.commits == 1


def test_matching_fingerprint_is_ok_and_writes_nothing():
    conn = FakeConn(key_fingerprint("k1"))
    assert H.verificar_o_registrar(conn, "k1") == "coincide"
    assert conn.store["inserts"] == 0


def test_mismatch_aborts_with_a_clear_message_and_does_not_write():
    conn = FakeConn(key_fingerprint("k1"))
    with pytest.raises(H.HuellaNoCoincide) as exc:
        H.verificar_o_registrar(conn, "otra-clave")
    assert "no coincide" in str(exc.value) and "--force-todo" in str(exc.value)
    assert "otra-clave" not in str(exc.value) and key_fingerprint("otra-clave") not in str(exc.value)
    assert conn.store["inserts"] == 0


def test_registrar_only_inserts_when_empty():
    conn = FakeConn()
    assert H.registrar(conn, "k1") == "registrada"
    assert H.registrar(conn, "k1") == "coincide"
    assert H.registrar(FakeConn(key_fingerprint("k1")), "otra") == "no_coincide"
    assert conn.store["inserts"] == 1


def test_runner_aborts_before_any_extraction_when_the_key_differs():
    from pipelines.extract import runner

    class Dev(FakeConn):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def wh_factory():  # must never be opened
        raise AssertionError("extraction started despite a key mismatch")

    dev = Dev(key_fingerprint("k1"))
    with pytest.raises(H.HuellaNoCoincide):
        runner.run(secret="otra", wh_factory=wh_factory, dev_factory=lambda: dev, out=lambda _m: None)
    assert dev.store["inserts"] == 0


class _Wh:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_runner_force_todo_replaces_the_fingerprint_then_extracts():
    from pipelines.extract import runner

    class Dev(FakeConn):
        replaced = 0

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    opened = []

    def wh_factory():
        opened.append(1)
        return _Wh()  # any use fails inside the per-source try: recorded as an error result

    dev = Dev(key_fingerprint("k1"))
    seen = []
    orig = H.reemplazar
    H.reemplazar = lambda conn, secret: seen.append(secret)
    try:
        runner.run(only=["ban_tipo_admision"], force_todo=True, secret="otra", wh_factory=wh_factory,
                   dev_factory=lambda: dev, out=lambda _m: None)
    finally:
        H.reemplazar = orig
    assert seen == ["otra"] and opened
