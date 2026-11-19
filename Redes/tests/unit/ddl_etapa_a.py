"""Columns added to the snapshot tables by migration 020 (stage A): the original CREATE TABLE files no longer list them."""
import re
from pathlib import Path

DDL_020 = Path(__file__).resolve().parents[2] / "sql" / "core" / "020_etapa_a_snapshots.sql"


def columnas_020(tabla: str) -> set:
    text = DDL_020.read_text(encoding="utf-8")
    return set(re.findall(rf"ALTER TABLE neural_mart\.{tabla} ADD COLUMN IF NOT EXISTS (\w+) ", text))
