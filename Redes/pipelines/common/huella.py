"""HMAC key fingerprint guard (``neural_meta.huella_clave``).

The table holds a single row with the fingerprint of the key used for the existing loads. A different key
would pseudonymize every RUT differently, so lookups would silently miss: the pipeline aborts instead.
Messages never contain the key or any fingerprint.
"""
from __future__ import annotations

from .pseudo import key_fingerprint

TABLE = "neural_meta.huella_clave"


class HuellaNoCoincide(RuntimeError):
    """The current key is not the one used for the existing loads."""


MENSAJE_NO_COINCIDE = (
    "La clave HMAC actual no coincide con la usada en las cargas existentes; "
    "recargar todo con --force-todo o restaurar la clave."
)


def _leer(conn):
    with conn.cursor() as cur:
        cur.execute(f"SELECT huella FROM {TABLE} WHERE id = 1")
        row = cur.fetchone()
    return row[0] if row else None


def registrar(conn, secret: str) -> str:
    """Insert the fingerprint only if the table is empty. Returns registrada | coincide | no_coincide."""
    actual = key_fingerprint(secret)
    guardada = _leer(conn)
    if guardada is None:
        with conn.cursor() as cur:
            cur.execute(f"INSERT INTO {TABLE} (id, huella) VALUES (1, %s) ON CONFLICT (id) DO NOTHING", (actual,))
        conn.commit()
        return "registrada"
    return "coincide" if guardada == actual else "no_coincide"


def verificar_o_registrar(conn, secret: str) -> str:
    """Register on first use; abort (``HuellaNoCoincide``) when the key differs. Returns registrada | coincide."""
    estado = registrar(conn, secret)
    if estado == "no_coincide":
        raise HuellaNoCoincide(MENSAJE_NO_COINCIDE)
    return estado


def reemplazar(conn, secret: str) -> None:
    """Overwrite the stored fingerprint with the current key's (only for a full reload, ``--force-todo``)."""
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {TABLE} (id, huella) VALUES (1, %s) "
            "ON CONFLICT (id) DO UPDATE SET huella = EXCLUDED.huella, registrada_en = now()",
            (key_fingerprint(secret),),
        )
    conn.commit()
