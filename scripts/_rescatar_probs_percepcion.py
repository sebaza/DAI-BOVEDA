"""Rescata las probabilidades del modelo que la curación sobrescribió.

QUÉ PASÓ
--------
`curacion.corregir_sentimiento()` pisaba `percepcion_score.prob_pos/neu/neg` con los
valores sintéticos de `_PROBS_SENT` (0,90 / 0,05 / 0,05) para reflejar la certeza de
quien corrige. El problema es que esos tres números ERAN la salida del modelo, y son
justo el insumo que necesita cualquier recalibración de umbral: para saber si el corte
NEU/POS está mal puesto hay que ver con qué probabilidad el modelo dijo NEU.

Medido sobre la base real: **262 scores** quedaron con el patrón sintético. Es decir,
en los 262 comentarios donde SÍ se conoce la respuesta correcta —los más valiosos del
corpus— la salida original del modelo ya no existe.

POR QUÉ SE PUEDE RECUPERAR SIN RE-CORRER EL MODELO
--------------------------------------------------
El worker dejó respaldos de la base. `percepcion_real.db.bak-20260805-135722` tiene
`percepcion_correccion` VACÍA y un solo score sintético: es el estado ANTERIOR a las
dos pasadas de auditoría (`auditoria-contextual-v4`, `auditoria-v9`).

Verificado contra la base real: **261 de los 262 (99,6%)** tienen ahí sus
probabilidades originales intactas. El restante ya venía pisado de antes.

Re-puntuar con `pysentimiento/robertuito-sentiment` (determinista) daría el mismo
resultado, pero exige el venv del worker con torch + transformers. Copiar del respaldo
es exacto, instantáneo y no depende de nada.

QUÉ ESCRIBE
-----------
NO toca `percepcion_score` (lo corregido está bien corregido; el valor humano manda).
Rellena en `percepcion_correccion` las columnas que agregó la Torre:

  * `modelo_orig`, `prob_pos_orig`, `prob_neu_orig`, `prob_neg_orig`, `prob_emocion_orig`
    -> el snapshot del modelo, desde el respaldo.
  * `confirmado` -> False donde `valor_original != valor_nuevo` (verificado fila a
    fila, no en bloque). Las 376 filas de la base real son todas cambios, pero eso
    se comprueba, no se asume.
  * `autor_tipo` -> 'agente' si el autor no parece un correo, 'humano' si lo parece.
    En la base real: 375 agente (`auditoria-contextual-v4`, `auditoria-v9`) y 1
    humano (`alberto.velasquez@ucn.cl`).

Es DRY-RUN por defecto: sin `--aplicar` solo diagnostica y no escribe una coma.
Con `--aplicar` copia la base a backups/ antes de tocarla.

Uso:
    backend\\.venv\\Scripts\\python.exe scripts/_rescatar_probs_percepcion.py
    backend\\.venv\\Scripts\\python.exe scripts/_rescatar_probs_percepcion.py --aplicar
    backend\\.venv\\Scripts\\python.exe scripts/_rescatar_probs_percepcion.py ruta.db --respaldo=otro.db
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):          # Windows: la consola es cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ_WORKER = r"C:/Users/sezad/Documents/GitHub/Sentiment_Analisys_University"
DB_POR_DEFECTO = f"{RAIZ_WORKER}/percepcion_real.db"
RESPALDO_POR_DEFECTO = f"{RAIZ_WORKER}/percepcion_real.db.bak-20260805-135722"

# Los tres valores que `_PROBS_SENT` escribe al corregir. Si una fila los tiene, sus
# probabilidades no son del modelo.
_SINTETICAS = ({0.9, 0.05}, )

# Espejo de las columnas que la Torre agregó a `percepcion_correccion`.
# FUENTE DE VERDAD: `backend/app/services/percepcion/models.py`. Se repiten acá
# —igual que hace `_reparar_origen_percepcion.py`— para que el script corra con
# sqlite3 pelado, sin importar la app ni depender de que el backend esté levantado.
# Todas NULLABLE: una fila vieja no sabe su `confirmado`, y NULL es la respuesta
# honesta (≠ False, que afirmaría un desacuerdo que nadie registró).
COLUMNAS_NUEVAS = {
    "confirmado": "BOOLEAN",
    "modelo_orig": "VARCHAR(120)",
    "prob_pos_orig": "FLOAT",
    "prob_neu_orig": "FLOAT",
    "prob_neg_orig": "FLOAT",
    "prob_emocion_orig": "FLOAT",
    "autor_tipo": "VARCHAR(20)",
    "origen_muestra": "VARCHAR(20)",
}


def _columnas(con, tabla: str) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info({tabla})")}


def _crear_columnas(ruta: str, faltantes: list[str]) -> None:
    """ADD COLUMN de lo que falte. Idempotente y no destructivo.

    Lo hace el script y no "levantá el backend una vez" porque esa dependencia de
    orden no se sostiene: es un paso invisible, fácil de olvidar, y que falla con un
    error que no dice qué hacer. El backend igual las crea al arrancar
    (`db._asegurar_columnas()`); las dos vías son idempotentes y no se pisan.
    """
    con = sqlite3.connect(ruta)
    try:
        for nombre in faltantes:
            con.execute(
                f'ALTER TABLE percepcion_correccion ADD COLUMN "{nombre}" '
                f"{COLUMNAS_NUEVAS[nombre]}"
            )
        con.commit()
    finally:
        con.close()


def _es_sintetica(pp, pn, pg) -> bool:
    """¿Estas tres probabilidades son las que escribe la corrección, no el modelo?"""
    return {round(float(pp or 0), 3), round(float(pn or 0), 3),
            round(float(pg or 0), 3)} <= {0.9, 0.05}


def _es_humano(autor: str | None) -> bool:
    """Un correo es una persona; `auditoria-v9` no lo es."""
    return "@" in (autor or "")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aplicar = "--aplicar" in sys.argv
    respaldo_arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--respaldo=")), None)
    ruta = args[0] if args else os.getenv("PERCEPCION_DB_VERIFICACION") or DB_POR_DEFECTO
    ruta_bak = respaldo_arg or RESPALDO_POR_DEFECTO

    for etiqueta, r in (("base", ruta), ("respaldo", ruta_bak)):
        if not Path(r).exists():
            print(f"[X] No existe la {etiqueta}: {r}")
            return 2

    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    faltan = [c for c in COLUMNAS_NUEVAS if c not in _columnas(con, "percepcion_correccion")]
    con.close()
    if faltan:
        print(f"[i] Faltan {len(faltan)} columnas en `percepcion_correccion`: "
              + ", ".join(faltan))
        if aplicar:
            _crear_columnas(ruta, faltan)
            print("    Agregadas (ALTER TABLE, no destructivo).\n")
        else:
            print("    Con --aplicar se agregan solas. No hace falta levantar el backend.\n")

    bak = sqlite3.connect(f"file:{ruta_bak}?mode=ro", uri=True)
    originales = {
        cid: (mo, pp, pn, pg, pe)
        for cid, mo, pp, pn, pg, pe in bak.execute(
            "select comentario_id, modelo, prob_pos, prob_neu, prob_neg, prob_emocion "
            "from percepcion_score"
        )
    }
    bak.close()

    # En dry-run sobre una base sin migrar la columna todavía no existe; se asume
    # "sin snapshot", que es exactamente el estado real.
    hay_snapshot = "modelo_orig" not in faltan or aplicar
    columnas = "id, comentario_id, valor_original, valor_nuevo, autor" + (
        ", modelo_orig" if hay_snapshot else ""
    )
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    filas = [
        fila if hay_snapshot else (*fila, None)
        for fila in con.execute(f"select {columnas} from percepcion_correccion order by id")
    ]
    con.close()

    print(f"Base:     {ruta}")
    print(f"Respaldo: {ruta_bak}  ({len(originales)} scores)\n")
    print(f"  Correcciones en la base: {len(filas)}")

    plan: list[tuple] = []
    sin_respaldo, ya_snapshot, sinteticas_en_bak = 0, 0, 0
    for cid_fila, com_id, v_orig, v_nuevo, autor, snapshot in filas:
        confirmado = 0 if v_orig != v_nuevo else 1
        autor_tipo = "humano" if _es_humano(autor) else "agente"
        if snapshot is not None:
            ya_snapshot += 1
            plan.append((None, None, None, None, None, confirmado, autor_tipo, cid_fila))
            continue
        orig = originales.get(com_id)
        if orig is None:
            sin_respaldo += 1
            plan.append((None, None, None, None, None, confirmado, autor_tipo, cid_fila))
            continue
        modelo, pp, pn, pg, pe = orig
        if _es_sintetica(pp, pn, pg):
            sinteticas_en_bak += 1
            plan.append((None, None, None, None, None, confirmado, autor_tipo, cid_fila))
            continue
        plan.append((modelo, pp, pn, pg, pe, confirmado, autor_tipo, cid_fila))

    recuperables = sum(1 for p in plan if p[0] is not None)
    humanos = sum(1 for p in plan if p[6] == "humano")
    cambios = sum(1 for p in plan if p[5] == 0)

    print(f"  Con snapshot ya cargado:          {ya_snapshot}")
    print(f"  Sin score en el respaldo:         {sin_respaldo}")
    print(f"  Ya sintéticas en el respaldo:     {sinteticas_en_bak}")
    print(f"  PROBABILIDADES A RECUPERAR:       {recuperables}"
          f"  ({recuperables / len(filas) * 100:.1f}%)" if filas else "")
    print()
    print(f"  Se marcarán como cambio (confirmado=0):  {cambios}")
    print(f"  Se marcarán como confirmación (=1):      {len(filas) - cambios}")
    print(f"  Autor humano: {humanos} · autor agente: {len(filas) - humanos}")

    if not aplicar:
        print("\n[DRY-RUN] No se escribió nada. Volvé a correr con --aplicar para rescatar.")
        return 0

    destino = Path(ruta).parent / "backups" / (
        f"{Path(ruta).stem}_pre_rescatar_probs_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ruta, destino)
    print(f"\n  Respaldo previo: {destino}")

    escritura = sqlite3.connect(ruta)
    escritura.executemany(
        "update percepcion_correccion set "
        "  modelo_orig       = coalesce(?, modelo_orig),"
        "  prob_pos_orig     = coalesce(?, prob_pos_orig),"
        "  prob_neu_orig     = coalesce(?, prob_neu_orig),"
        "  prob_neg_orig     = coalesce(?, prob_neg_orig),"
        "  prob_emocion_orig = coalesce(?, prob_emocion_orig),"
        "  confirmado        = ?,"
        "  autor_tipo        = ? "
        "where id = ?",
        plan,
    )
    escritura.commit()
    quedan = escritura.execute(
        "select count(*) from percepcion_correccion where modelo_orig is null"
    ).fetchone()[0]
    escritura.close()
    print(f"  Filas actualizadas: {len(plan)}")
    print(f"  Siguen sin snapshot: {quedan} (no había de dónde sacarlas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
