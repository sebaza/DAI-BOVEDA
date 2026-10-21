"""Utilidades de conexión a PostgreSQL para el módulo Percepción (sin efectos al importar).

Los modelos de `models.py` reflejan las tablas del worker externo y NO conocen ningún
esquema. En Postgres las tablas viven en el esquema `percepcion`, y se lo elige por la
URL de conexión (`?options=-csearch_path%3Dpercepcion`) en vez de cablearlo en cada
modelo. Este módulo arma esa URL para quien necesite apuntar a otro esquema (la
migración, los tests con un esquema descartable, la verificación de paridad).
"""
from __future__ import annotations

from sqlalchemy.engine import make_url

ESQUEMA_PERCEPCION = "percepcion"


def url_con_esquema(url: str, esquema: str = ESQUEMA_PERCEPCION) -> str:
    """Devuelve `url` con `search_path` fijado a `esquema`, descartando el que traiga."""
    parsed = make_url(url)
    return parsed.update_query_dict({"options": f"-csearch_path={esquema}"}).render_as_string(
        hide_password=False
    )
