"""Program and faculty names for the by-programa / by-facultad tables (stage B, P76 / P85: ``common.facultad_d``).

Every report table labels a faculty with its NAME; the numeric code stays an internal join key (``programa.facultad``).
"""
from __future__ import annotations

import pandas as pd

Q_PROGRAMAS = """
SELECT p.cod_programa, p.nombre_programa, p.facultad::text AS facultad, f.nombre_facultad
FROM neural_core.programa p LEFT JOIN neural_core.facultad f ON f.facultad_id::text = p.facultad::text
"""


def nombre_facultad(codigo, nombre) -> str:
    """Name of a faculty; a code without a name in the dictionary is labelled as such (never a bare number)."""
    if isinstance(nombre, str) and nombre.strip():
        return " ".join(nombre.split())
    if codigo is None or (isinstance(codigo, float) and codigo != codigo) or str(codigo) in ("", "None", "nan"):
        return "Sin facultad"
    return f"Facultad sin nombre (código {codigo})"


def cargar_programas(conn) -> pd.DataFrame:
    """One row per program (index ``cod_programa``) with ``nombre_programa``, ``facultad`` (code) and ``facultad_nombre``."""
    with conn.cursor() as cur:
        cur.execute(Q_PROGRAMAS)
        d = pd.DataFrame(cur.fetchall(), columns=["cod_programa", "nombre_programa", "facultad", "nombre_facultad"])
    d["facultad_nombre"] = [nombre_facultad(c, n) for c, n in zip(d["facultad"], d["nombre_facultad"])]
    return d.drop(columns="nombre_facultad").drop_duplicates("cod_programa").set_index("cod_programa")


def facultad_de(cod_programa: pd.Series, programas: pd.DataFrame) -> pd.Series:
    """Faculty name of each program code (``None`` for a program that is not in the dictionary)."""
    return cod_programa.map(programas["facultad_nombre"]).astype(object).where(cod_programa.isin(programas.index), None)
