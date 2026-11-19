"""Pseudonymization: HMAC-SHA256 keys with domain separation.

No mapping table is ever stored; the RUT never reaches the dev database.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional

_STUDENT_DOMAIN = b""  # persona_key: message is the normalized RUT itself
_TEACHER_DOMAIN = b"docente:"


def normalize_rut(raw: Optional[str]) -> Optional[str]:
    """Strip spaces, dots and dashes, uppercase, drop leading zeros.

    Returns ``None`` when nothing is left (empty input is rejected, never keyed).
    """
    if raw is None:
        return None
    cleaned = "".join(str(raw).split()).replace(".", "").replace("-", "").upper()
    cleaned = cleaned.lstrip("0")
    return cleaned or None


def _digest(secret: str, domain: bytes, rut: Optional[str]) -> Optional[str]:
    if not secret:
        raise ValueError("HMAC secret must not be empty")
    normalized = normalize_rut(rut)
    if normalized is None:
        return None
    message = domain + normalized.encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def persona_key(rut: Optional[str], secret: str) -> Optional[str]:
    """Student key: ``HMAC-SHA256(secret, normalize_rut(rut))`` as hex."""
    return _digest(secret, _STUDENT_DOMAIN, rut)


def docente_key(rut: Optional[str], secret: str) -> Optional[str]:
    """Teacher key: same HMAC but over ``b"docente:" + rut`` (never equals a persona_key)."""
    return _digest(secret, _TEACHER_DOMAIN, rut)


_FINGERPRINT_MESSAGE = b"dai-neural:huella-clave:v1"


def key_fingerprint(secret: str) -> str:
    """Non-reversible fingerprint of the HMAC key (``HMAC(secret, fixed message)`` hex).

    Stored in ``neural_meta.huella_clave`` so a different key is detected instead of silently missing every lookup.
    """
    if not secret:
        raise ValueError("HMAC secret must not be empty")
    return hmac.new(secret.encode("utf-8"), _FINGERPRINT_MESSAGE, hashlib.sha256).hexdigest()
