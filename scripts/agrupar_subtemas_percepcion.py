"""Agrupa los comentarios de cada tema en SUBTEMAS con un modelo de embeddings LOCAL.

POR QUÉ
-------
Un `tema` es muy grueso. Este script embebe cada comentario (texto limpio de URLs, @menciones y
frases del scraper) con una red neuronal multilingüe que corre en este equipo (sin APIs
externas), agrupa por tema con KMeans (k por silueta) y guarda, por comentario, su subtema:

    percepcion_subtema               etiqueta anonimizada + términos + tamaño de cada subtema
    percepcion_comentario_subtema    subtema de cada comentario

La etiqueta sale de los TOKENS guardados con umbrales anti-PII (>= 5 comentarios y >= 3 autores
por término) y sin nombres propios, handles mencionados ni palabras que el tokenizador del modelo
no reconoce (handles escritos sin @). Lo que se escape se veta a mano con `--vetar` o
`PERCEPCION_SUBTEMAS_VETADOS` (no van al repositorio). El texto crudo no sale de este proceso.
La API solo lee estas tablas.

CUÁNDO CORRERLO
---------------
DESPUÉS de `scripts/precalcular_tokens_percepcion.py` (las etiquetas usan sus tokens) y cada vez
que se repita. Es una reconstrucción COMPLETA e idempotente en UNA transacción.
Tras la PRIMERA corrida (que crea las dos tablas) hay que volver a ejecutar
`backend/sql/003_percepcion_roles.sql` para que `boveda_app` pueda leerlas.

DEPENDENCIAS
------------
`backend/requirements-ml.txt` (torch CPU + sentence-transformers). Solo este script las usa; la
API no las importa. La primera vez descarga el modelo (~470 MB) a la caché de Hugging Face.

NOMBRES MANUALES (MIGRACIÓN)
----------------------------
Los subtemas se pueden renombrar desde Curación (columnas `etiqueta_manual`, `renombrado_por`,
`renombrado_en` de `percepcion_subtema`). Antes de reconstruir (y solo sin `--dry-run`) el script
agrega esas columnas si faltan (`ADD COLUMN IF NOT EXISTS`, no hace nada si ya existen). Solo el
DUEÑO de la tabla puede hacer el ALTER, así que la PRIMERA corrida tras este cambio debe usar la
URL de administrador:

    ... scripts/agrupar_subtemas_percepcion.py --url $env:PERCEPCION_ADMIN_DATABASE_URL

y luego volver a ejecutar `backend/sql/003_percepcion_roles.sql` (crear_roles) para que
`boveda_app` pueda actualizar esas tres columnas. Al reconstruir, cada nombre manual pasa al
subtema nuevo que más se le parece (Jaccard de comentarios >= 0,5); si ninguno alcanza, se
descarta. Se imprimen solo los conteos.

CONEXIÓN
--------
`--url`, o `PERCEPCION_PROCESO_DATABASE_URL`, o `PERCEPCION_DATABASE_URL`, en ese orden (lee
texto crudo: necesita el rol de proceso). La URL no se imprime. Solo se imprimen conteos.

Uso:
    backend\.venv\Scripts\python.exe -I scripts/agrupar_subtemas_percepcion.py [--dry-run]
        [--modelo NOMBRE] (o env PERCEPCION_SUBTEMAS_MODELO)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BACKEND = RAIZ / "backend"
if str(BACKEND) not in sys.path:      # `python -I` no agrega el cwd
    sys.path.insert(0, str(BACKEND))

MODELO_POR_DEFECTO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MAX_TROZOS_PALABRA = 2


def crear_embedder(modelo: str):
    """Embedder local (CPU, lotes de 64, vectores normalizados). Importa torch acá y solo acá."""
    from sentence_transformers import SentenceTransformer

    m = SentenceTransformer(modelo, device="cpu")

    def embedder(textos: list[str]):
        return m.encode(textos, batch_size=64, normalize_embeddings=True, show_progress_bar=False)

    def es_palabra(termino: str) -> bool:
        # Una palabra real del vocabulario se parte en 1-2 trozos; un handle escrito sin @
        # ("nombreapellido23") en 4 o más. Deja afuera algunas palabras raras: lado seguro.
        return len(m.tokenizer.tokenize(" " + termino)) <= MAX_TROZOS_PALABRA

    return embedder, es_palabra


COLUMNAS_NOMBRE_MANUAL = (("etiqueta_manual", "VARCHAR(120)"), ("renombrado_por", "VARCHAR(200)"),
                          ("renombrado_en", "TIMESTAMP"))


def asegurar_columnas_nombre_manual(engine) -> None:
    """Agrega las columnas de nombre manual si faltan (solo Postgres; SQLite las crea create_all)."""
    from sqlalchemy import inspect, text

    if engine.dialect.name != "postgresql":
        return
    existentes = {c["name"] for c in inspect(engine).get_columns("percepcion_subtema")}
    faltan = [(c, t) for c, t in COLUMNAS_NOMBRE_MANUAL if c not in existentes]
    if not faltan:           # el ALTER exige ser dueño aun si la columna existe: así el rol de proceso no falla
        return
    with engine.begin() as conn:
        for col, tipo in faltan:
            conn.execute(text(f"ALTER TABLE percepcion_subtema ADD COLUMN IF NOT EXISTS {col} {tipo}"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Agrupa comentarios en subtemas con embeddings locales.")
    ap.add_argument("--url", default=None, help="URL de la base (por defecto, la del entorno); no se imprime")
    ap.add_argument("--modelo", default=os.environ.get("PERCEPCION_SUBTEMAS_MODELO", MODELO_POR_DEFECTO))
    ap.add_argument("--dry-run", action="store_true", help="calcula y muestra conteos sin escribir")
    ap.add_argument("--vetar", default=os.environ.get("PERCEPCION_SUBTEMAS_VETADOS", ""),
                    help="palabras separadas por coma que nunca van en una etiqueta (apodos, nombres)")
    args = ap.parse_args(argv)
    vetos = [v for v in args.vetar.split(",") if v.strip()]

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import get_settings
    from app.services.percepcion import subtemas
    from app.services.percepcion.models import PercepcionComentarioSubtema, PercepcionSubtema
    from app.services.percepcion.pg import url_con_esquema

    s = get_settings()
    url = (args.url or s.percepcion_proceso_database_url or s.percepcion_database_url
           or s.operational_database_url).strip()
    if url.startswith("postgresql"):
        # Una URL de administrador no trae search_path: sin esto las tablas caerían en `public`.
        url = url_con_esquema(url)
    t0 = time.monotonic()
    engine = create_engine(url, future=True, pool_pre_ping=True)
    try:
        if not args.dry_run:
            for modelo in (PercepcionSubtema, PercepcionComentarioSubtema):
                modelo.__table__.create(bind=engine, checkfirst=True)
            asegurar_columnas_nombre_manual(engine)
        embedder, es_palabra = crear_embedder(args.modelo)
        with sessionmaker(bind=engine, future=True)() as db:
            try:
                r = subtemas.reconstruir_subtemas(
                    db, embedder, modelo=args.modelo, ahora=datetime.utcnow(),
                    escribir=not args.dry_run, vetar=vetos, es_palabra=es_palabra)
                if args.dry_run:
                    db.rollback()
                else:
                    db.commit()
            except Exception:
                db.rollback()
                raise
    except Exception as e:  # noqa: BLE001 - el mensaje del driver puede traer la URL o texto de filas
        print(f"No se pudo agrupar ({type(e).__name__}). Revisa que el rol pueda leer texto y escribir las "
              "tablas de subtemas, que las dependencias de requirements-ml.txt estén instaladas y que "
              "el modelo se pueda cargar.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print(("[dry-run] " if args.dry_run else "") + f"Temas: {r['temas']}  Subtemas: {r['subtemas']}  "
          f"Comentarios asignados: {r['asignados']}  Solo etiquetas: {r['etiquetan']}")
    print(f"Nombres manuales conservados: {r['nombres_manuales_conservados']}  "
          f"descartados: {r['nombres_manuales_descartados']}")
    for tema, n in sorted(r["por_tema"].items()):
        print(f"  {tema}: {n}")
    print(f"Tiempo: {time.monotonic() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
