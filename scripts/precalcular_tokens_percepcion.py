"""Precalcula los derivados del texto crudo: tokens, familias del léxico y rasgos de captions.

POR QUÉ
-------
La API corre con un rol de base de datos que NO puede leer `percepcion_comentario.texto` ni
`percepcion_publicacion.caption`. La nube de palabras, los términos bajo vigilancia, el impacto
de palabras, las palabras destacadas, las anomalías y el análisis de comunicación leen, en su
lugar, tres tablas derivadas que llena ESTE script con un rol que sí puede leer el texto
(`boveda_proceso`):

    percepcion_comentario_token      palabras únicas de cada comentario
    percepcion_comentario_familia    familias del léxico de vigilancia que menciona cada comentario
    percepcion_publicacion_rasgo     rasgos binarios de cada caption (emojis, @, #, «?», largo)

Usa EXACTAMENTE la misma lógica que el resto del código (`app.services.percepcion.derivados`),
así que los resultados no cambian respecto de calcular sobre el texto.

CUÁNDO CORRERLO
---------------
Después de migrar y ANTES de crear los roles (para que las tablas existan y se llenen), y de
nuevo cada vez que el worker ingeste comentarios o publicaciones nuevos (o que cambie el
tokenizador). Las filas ingestadas después de la última corrida no aparecen en la nube ni en
los términos hasta que se vuelva a correr.

Es una reconstrucción COMPLETA e idempotente en UNA transacción: si algo falla no se toca nada.

CONEXIÓN
--------
`--url`, o `PERCEPCION_PROCESO_DATABASE_URL`, o `PERCEPCION_DATABASE_URL` (también desde
`backend/.env`), en ese orden. Necesita leer texto/caption y escribir las tres tablas derivadas
(`boveda_proceso` o el dueño). La URL no se imprime. Solo se imprimen conteos.

Uso:
    backend\\.venv\\Scripts\\python.exe -I scripts/precalcular_tokens_percepcion.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BACKEND = RAIZ / "backend"
if str(BACKEND) not in sys.path:      # `python -I` no agrega el cwd
    sys.path.insert(0, str(BACKEND))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Precalcula tokens/familias/rasgos del texto crudo.")
    ap.add_argument("--url", default=None, help="URL de la base (por defecto, la del entorno); no se imprime")
    args = ap.parse_args(argv)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import get_settings
    from app.services.percepcion import derivados
    from app.services.percepcion.models import (
        PercepcionComentarioFamilia,
        PercepcionComentarioToken,
        PercepcionPublicacionRasgo,
    )

    s = get_settings()
    url = (args.url or s.percepcion_proceso_database_url or s.percepcion_database_url
           or s.operational_database_url).strip()
    engine = create_engine(url, future=True, pool_pre_ping=True)
    try:
        for modelo in (PercepcionComentarioToken, PercepcionComentarioFamilia, PercepcionPublicacionRasgo):
            modelo.__table__.create(bind=engine, checkfirst=True)
        with sessionmaker(bind=engine, future=True)() as db:
            try:
                r = derivados.reconstruir(db)
                db.commit()
            except Exception:
                db.rollback()
                raise
    except Exception as e:  # noqa: BLE001 - el mensaje del driver puede traer la URL o texto de filas
        print(f"No se pudo precalcular ({type(e).__name__}). Revisa que el rol pueda leer texto/caption "
              "y escribir las tablas derivadas, y que las migraciones estén aplicadas.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print(f"Comentarios recorridos: {r['comentarios']}")
    print(f"Filas en percepcion_comentario_token:   {r['tokens']}")
    print(f"Filas en percepcion_comentario_familia: {r['familias']}")
    print(f"Filas en percepcion_publicacion_rasgo:  {r['rasgos']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
