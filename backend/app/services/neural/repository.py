"""Read-only SQL of the Neural API (aggregate marts only). Parameterized only: user input never reaches the SQL text.

Table names are unqualified on purpose: the connection URL sets ``search_path`` (``neural_mart``,
``neural_core``, ``neural_meta``), which also lets the tests point the same code at a throwaway schema.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


UCN = "Toda la UCN"


class NoEncontrado(LookupError):
    """The requested program or task does not exist (HTTP 404)."""


def _rows(conn: Connection, sql: str, **params) -> list[dict]:
    return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]


def _one(conn: Connection, sql: str, **params) -> dict | None:
    row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


_STATS = """n_episodios, n_activos, n_promedio, creditos_p25, creditos_p50, creditos_p75, promedio_p25, promedio_p50, promedio_p75"""


# --------------------------------------------------------------------------- #
# Programs and cohorts
# --------------------------------------------------------------------------- #
def programas(conn: Connection) -> list[dict]:
    return _rows(conn, """
        SELECT cod_programa, max(nombre_programa) AS nombre_programa, count(*)::int AS n_episodios,
               min(periodo_admision) AS primera_cohorte, max(periodo_admision) AS ultima_cohorte
        FROM ficha_episodio GROUP BY cod_programa ORDER BY max(nombre_programa) NULLS LAST, cod_programa
    """)


def programa(conn: Connection, cod: str) -> dict:
    fila = _one(conn, "SELECT cod_programa, max(nombre_programa) AS nombre_programa FROM ficha_episodio "
                      "WHERE cod_programa = :p GROUP BY cod_programa", p=cod)
    if fila is None:
        raise NoEncontrado("Programa no encontrado.")
    return fila


def cohortes_resultado(conn: Connection, cod: str) -> list[dict]:
    return _rows(conn, """
        SELECT cohorte, n_ingreso, duracion, duracion_anios, censurado_d, censurado_d1, censurado_d2,
               titulados_d, titulados_d1, titulados_d2, censurado_retencion, n_retencion_obs, n_retenidos
        FROM cohorte_resultado WHERE cod_programa = :p ORDER BY cohorte
    """, p=cod)


def cohortes_semestre(conn: Connection, cod: str) -> list[dict]:
    return _rows(conn, f"SELECT cohorte, semestre_k, {_STATS} FROM cohorte_semestre WHERE cod_programa = :p "
                       f"ORDER BY cohorte, semestre_k", p=cod)


def programa_semestres(conn: Connection, cod: str) -> list[dict]:
    return _rows(conn, f"SELECT semestre_k, {_STATS} FROM programa_semestre WHERE cod_programa = :p "
                       f"ORDER BY semestre_k", p=cod)


# --------------------------------------------------------------------------- #
# Quality
# --------------------------------------------------------------------------- #
def cargas(conn: Connection) -> list[dict]:
    return _rows(conn, """
        SELECT DISTINCT ON (fuente) fuente,
               to_timestamp(timestamp_carga_wh / 1000.0) AS carga_wh, filas_origen, filas_insertadas,
               terminado_en, estado
        FROM carga_extraccion WHERE estado = 'ok'
        ORDER BY fuente, terminado_en DESC NULLS LAST, carga_id DESC
    """)


def auditoria(conn: Connection) -> list[dict]:
    return _rows(conn, """
        SELECT DISTINCT ON (chequeo) chequeo, valor_esperado, valor_obtenido, ok, explicacion
        FROM auditoria_resultado ORDER BY chequeo, medido_en DESC
    """)


def construccion_marts(conn: Connection) -> list[dict]:
    return _rows(conn, "SELECT mart, filas, construido_en, periodo_maximo FROM mart_construccion ORDER BY mart")


# --------------------------------------------------------------------------- #
# Transfers between programs (P61). Ambiguous transitions (a third program starts in the same window) are left out.
# --------------------------------------------------------------------------- #
def _filtro_traslado(alias: str = "") -> str:
    """WHERE fragment of the shared filters; ``alias`` is the table alias with its dot (or empty)."""
    a = alias
    return (f"NOT {a}ambiguo AND {a}anio_traslado >= coalesce(:desde, 0) AND {a}anio_traslado <= coalesce(:hasta, 9999) "
            f"AND (CAST(:tipo AS text) IS NULL OR {a}tipo = CAST(:tipo AS text)) "
            f"AND (NOT :solo_abandono OR {a}cuenta_abandono)")


def traslados_rango(conn: Connection) -> dict:
    return _one(conn, "SELECT min(anio_traslado) AS desde, max(anio_traslado) AS hasta FROM programa_traslados "
                      "WHERE NOT ambiguo") or {"desde": None, "hasta": None}


def traslados_ambiguos(conn: Connection, **filtro) -> int:
    fila = _one(conn, f"SELECT count(*)::int AS n FROM programa_traslados WHERE ambiguo AND "
                      f"{_filtro_traslado().replace('NOT ambiguo AND ', '')}", **filtro)
    return fila["n"]


def traslados_por_tipo(conn: Connection, **filtro) -> list[dict]:
    return _rows(conn, f"SELECT tipo, count(*)::int AS n FROM programa_traslados WHERE {_filtro_traslado()} "
                       f"GROUP BY tipo ORDER BY tipo", **filtro)


def traslados_por_anio(conn: Connection, **filtro) -> list[dict]:
    return _rows(conn, f"SELECT anio_traslado AS anio, tipo, count(*)::int AS n FROM programa_traslados "
                       f"WHERE {_filtro_traslado()} GROUP BY anio_traslado, tipo ORDER BY anio_traslado, tipo", **filtro)


def traslados_flujos(conn: Connection, **filtro) -> list[dict]:
    return _rows(conn, f"""
        SELECT t.cod_programa_origen AS cod_origen, po.nombre_programa AS nombre_origen,
               t.cod_programa_destino AS cod_destino, pd.nombre_programa AS nombre_destino,
               count(*)::int AS n, mode() WITHIN GROUP (ORDER BY t.tipo) AS tipo_principal
        FROM programa_traslados t
        LEFT JOIN programa po ON po.cod_programa = t.cod_programa_origen
        LEFT JOIN programa pd ON pd.cod_programa = t.cod_programa_destino
        WHERE {_filtro_traslado('t.')}
        GROUP BY 1, 2, 3, 4
    """, **filtro)


def traslados_balance(conn: Connection, **filtro) -> list[dict]:
    return _rows(conn, f"""
        WITH g AS (
            SELECT cod_programa_destino AS cod, count(*)::int AS n,
                   count(*) FILTER (WHERE tipo = 'eleccion_especialidad')::int AS e
            FROM programa_traslados WHERE {_filtro_traslado()} GROUP BY 1
        ), p AS (
            SELECT cod_programa_origen AS cod, count(*)::int AS n,
                   count(*) FILTER (WHERE tipo = 'eleccion_especialidad')::int AS e
            FROM programa_traslados WHERE {_filtro_traslado()} GROUP BY 1
        )
        SELECT coalesce(g.cod, p.cod) AS cod_programa, pr.nombre_programa,
               coalesce(g.n, 0) AS ganados, coalesce(g.e, 0) AS ganados_eleccion,
               coalesce(p.n, 0) AS perdidos, coalesce(p.e, 0) AS perdidos_eleccion
        FROM g FULL JOIN p ON p.cod = g.cod
        LEFT JOIN programa pr ON pr.cod_programa = coalesce(g.cod, p.cod)
    """, **filtro)


def traslados_programa_tipos(conn: Connection, cod: str, lado: str, **filtro) -> list[dict]:
    columna = {"entrada": "cod_programa_destino", "salida": "cod_programa_origen"}[lado]
    return _rows(conn, f"SELECT tipo, count(*)::int AS n FROM programa_traslados WHERE {columna} = :cod AND "
                       f"{_filtro_traslado()} GROUP BY tipo", cod=cod, **filtro)


def traslados_programa_contrapartes(conn: Connection, cod: str, lado: str, **filtro) -> list[dict]:
    propio, otro = {"destinos": ("cod_programa_origen", "cod_programa_destino"),
                    "origenes": ("cod_programa_destino", "cod_programa_origen")}[lado]
    return _rows(conn, f"""
        SELECT t.{otro} AS cod_programa, pr.nombre_programa, count(*)::int AS n
        FROM programa_traslados t LEFT JOIN programa pr ON pr.cod_programa = t.{otro}
        WHERE t.{propio} = :cod AND {_filtro_traslado('t.')}
        GROUP BY 1, 2 ORDER BY n DESC, 1
    """, cod=cod, **filtro)


def traslados_programa_anios(conn: Connection, cod: str, **filtro) -> list[dict]:
    return _rows(conn, f"""
        SELECT anio_traslado AS anio,
               count(*) FILTER (WHERE cod_programa_destino = :cod)::int AS ganados,
               count(*) FILTER (WHERE cod_programa_origen = :cod)::int AS perdidos
        FROM programa_traslados WHERE (cod_programa_destino = :cod OR cod_programa_origen = :cod)
          AND {_filtro_traslado()} GROUP BY anio_traslado ORDER BY anio_traslado
    """, cod=cod, **filtro)


def programa_basico(conn: Connection, cod: str) -> dict:
    fila = _one(conn, "SELECT cod_programa, nombre_programa FROM programa WHERE cod_programa = :c", c=cod)
    if fila is None:
        raise NoEncontrado("Programa no encontrado.")
    return fila


# --------------------------------------------------------------------------- #
# Models: aggregates exported by Redes/tools/exportar_resumen_modelos.py
# --------------------------------------------------------------------------- #
_DELTAS_PRINCIPALES = ("(tarea = 't1' AND metrica IN ('ap', 'roc_auc')) OR "
                       "(tarea = 't2' AND metrica IN ('ap', 'roc_auc', 'recall_at_1')) OR "
                       "(tarea = 't3' AND metrica IN ('c_12', 'ibs'))")


def modelos_construccion(conn: Connection) -> dict | None:
    return _one(conn, "SELECT construido_en FROM resumen_modelos_construccion WHERE id = 1")


def modelos_metricas(conn: Connection) -> list[dict]:
    return _rows(conn, """SELECT tarea, corte_k, modelo, modelo_nombre, familia, escalon, escalon_nombre, metrica,
                                 valor::float8 AS valor, ic_inf::float8 AS ic_inf, ic_sup::float8 AS ic_sup, n_evaluacion
                          FROM resumen_modelos ORDER BY tarea, corte_k, escalon, modelo, metrica""")


def modelos_comparaciones(conn: Connection) -> list[dict]:
    return _rows(conn, f"""SELECT tarea, corte_k, modelo_a, modelo_b, metrica, delta::float8 AS delta,
                                  ic_inf::float8 AS ic_inf, ic_sup::float8 AS ic_sup, veredicto
                           FROM resumen_modelos_delta WHERE {_DELTAS_PRINCIPALES}
                           ORDER BY tarea, corte_k, modelo_a, modelo_b, metrica""")


def modelos_arquitectura(conn: Connection) -> list[dict]:
    return _rows(conn, """SELECT tarea, corte_k, modelo, clave, valor_num::float8 AS valor_num, valor_texto
                          FROM resumen_modelos_info ORDER BY tarea, corte_k, modelo, clave""")


def modelos_titulares(conn: Connection) -> list[dict]:
    return _rows(conn, "SELECT tarea, orden, clave, texto FROM resumen_modelos_titular ORDER BY tarea, orden")


def malla_ejemplo(conn: Connection, cod: str | None, semestre_max: int) -> dict:
    """Courses (code, name, semester, credits) and prerequisite edges of one official malla: no person data.

    Without ``cod`` the program (and its latest catalog) with the most prerequisite edges inside the first
    ``semestre_max`` semesters is used, so the diagram of the curriculum graph has something to show.
    """
    if cod is None:
        fila = _one(conn, """
            SELECT p.cod_programa, p.catalogo, count(*) AS aristas
            FROM prerrequisito p
            JOIN asignatura_malla a ON a.cod_programa = p.cod_programa AND a.catalogo = p.catalogo
                                   AND a.codigo_asignatura = p.codigo_asignatura AND a.semestre <= :s
            JOIN asignatura_malla r ON r.cod_programa = p.cod_programa AND r.catalogo = p.catalogo
                                   AND r.codigo_asignatura = p.codigo_requisito AND r.semestre <= :s
            WHERE p.asig_en_malla AND p.req_en_malla
            GROUP BY p.cod_programa, p.catalogo
            ORDER BY count(*) DESC, p.catalogo DESC, p.cod_programa LIMIT 1
        """, s=semestre_max)
    else:
        fila = _one(conn, "SELECT cod_programa, max(catalogo) AS catalogo FROM asignatura_malla WHERE cod_programa = :p "
                          "GROUP BY cod_programa", p=cod)
    if fila is None:
        return {"cod_programa": cod, "nombre_programa": None, "catalogo": None, "semestre_max": semestre_max,
                "nodos": [], "aristas": []}
    prog = _one(conn, "SELECT nombre_programa FROM programa WHERE cod_programa = :p", p=fila["cod_programa"])
    nodos = _rows(conn, """
        SELECT codigo_asignatura AS codigo, nombre_asignatura AS nombre, semestre, creditos::float8 AS creditos
        FROM asignatura_malla WHERE cod_programa = :p AND catalogo = :c AND semestre IS NOT NULL AND semestre <= :s
        ORDER BY semestre, codigo_asignatura LIMIT 60
    """, p=fila["cod_programa"], c=fila["catalogo"], s=semestre_max)
    codigos = [n["codigo"] for n in nodos]
    aristas = [a for a in _rows(conn, """
        SELECT codigo_requisito AS desde, codigo_asignatura AS hacia FROM prerrequisito
        WHERE cod_programa = :p AND catalogo = :c AND asig_en_malla AND req_en_malla
        ORDER BY codigo_asignatura, codigo_requisito
    """, p=fila["cod_programa"], c=fila["catalogo"]) if a["desde"] in codigos and a["hacia"] in codigos]
    return {"cod_programa": fila["cod_programa"], "nombre_programa": prog["nombre_programa"] if prog else None,
            "catalogo": fila["catalogo"], "semestre_max": semestre_max, "nodos": nodos, "aristas": aristas}


# --------------------------------------------------------------------------- #
# Models: per-task pages (T1-T6), exported by the same tool into ``resumen_tarea*`` (migration 023)
# --------------------------------------------------------------------------- #
_FICHA_SQL = """SELECT tarea, orden, nombre, pregunta, poblacion, evento, estado, estado_etiqueta, veredicto_redes,
                        metrica_titular, metrica_secundaria FROM resumen_tarea"""


def tareas_fichas(conn: Connection) -> list[dict]:
    return _rows(conn, f"{_FICHA_SQL} ORDER BY orden")


def tarea_ficha(conn: Connection, tarea: str) -> dict:
    fila = _one(conn, f"{_FICHA_SQL} WHERE tarea = :t", t=tarea)
    if fila is None:
        raise NoEncontrado("Esa tarea aún no tiene resultados exportados.")
    return fila


def tareas_vistas(conn: Connection, tarea: str | None = None) -> list[dict]:
    return _rows(conn, """SELECT tarea, variante, corte_k, etiqueta, principal, conservado_modelo, referencia_modelo,
                                 metrica_titular, metrica_secundaria, concluyente, pronostico_agregado, nota
                          FROM resumen_tarea_vista WHERE (CAST(:t AS text) IS NULL OR tarea = :t)
                          ORDER BY tarea, variante, corte_k""", t=tarea)


def tarea_notas(conn: Connection, tarea: str) -> list[dict]:
    return _rows(conn, "SELECT tipo, orden, texto FROM resumen_tarea_nota WHERE tarea = :t ORDER BY tipo, orden", t=tarea)


def tareas_particiones(conn: Connection, tarea: str | None = None) -> list[dict]:
    return _rows(conn, """SELECT tarea, variante, corte_k, particion, n, eventos, tasa::float8 AS tasa,
                                 tasa_inf::float8 AS tasa_inf, tasa_sup::float8 AS tasa_sup
                          FROM resumen_tarea_particion WHERE (CAST(:t AS text) IS NULL OR tarea = :t)
                          ORDER BY tarea, variante, corte_k, particion""", t=tarea)


def tareas_metricas(conn: Connection, tarea: str | None = None, metricas: list[str] | None = None) -> list[dict]:
    return _rows(conn, """SELECT tarea, variante, corte_k, modelo, modelo_nombre, familia, escalon, escalon_nombre, metrica,
                                 valor::float8 AS valor, ic_inf::float8 AS ic_inf, ic_sup::float8 AS ic_sup, n_evaluacion,
                                 conservado
                          FROM resumen_tarea_metrica
                          WHERE (CAST(:t AS text) IS NULL OR tarea = :t)
                            AND (CAST(:m AS text[]) IS NULL OR metrica = ANY(CAST(:m AS text[])))
                          ORDER BY tarea, variante, corte_k, escalon, modelo, metrica""", t=tarea, m=metricas)


def tarea_comparaciones(conn: Connection, tarea: str) -> list[dict]:
    return _rows(conn, """SELECT variante, corte_k, modelo_a, modelo_b, metrica, delta::float8 AS delta,
                                 ic_inf::float8 AS ic_inf, ic_sup::float8 AS ic_sup, veredicto
                          FROM resumen_tarea_delta WHERE tarea = :t
                          ORDER BY variante, corte_k, modelo_a, modelo_b, metrica""", t=tarea)


def tarea_calibracion(conn: Connection, tarea: str) -> list[dict]:
    return _rows(conn, """SELECT variante, corte_k, modelo, decil, n, riesgo_medio::float8 AS riesgo_medio,
                                 tasa_observada::float8 AS tasa_observada
                          FROM resumen_tarea_calibracion WHERE tarea = :t
                          ORDER BY variante, corte_k, modelo, decil""", t=tarea)


def tarea_grupos(conn: Connection, tarea: str, nivel: str, variante: str, corte_k: int) -> list[dict]:
    """Every group row of one view, as stored: groups of any size, with their intervals (T6 rows are valid + test units)."""
    return _rows(conn, """SELECT categoria, grupo, nombre, facultad, n, eventos, observada::float8 AS observada,
                                 obs_inf::float8 AS obs_inf, obs_sup::float8 AS obs_sup, esperada::float8 AS esperada,
                                 esp_inf::float8 AS esp_inf, esp_sup::float8 AS esp_sup, referencia::float8 AS referencia,
                                 ap::float8 AS ap, roc_auc::float8 AS roc_auc,
                                 ap_lo::float8 AS ap_lo, ap_hi::float8 AS ap_hi, auc_lo::float8 AS auc_lo, auc_hi::float8 AS auc_hi,
                                 tasa_lo::float8 AS tasa_lo, tasa_hi::float8 AS tasa_hi,
                                 esperado_lo::float8 AS esperado_lo, esperado_hi::float8 AS esperado_hi
                          FROM resumen_tarea_grupo
                          WHERE tarea = :t AND nivel = :nivel AND variante = :v AND corte_k = :k
                          ORDER BY categoria, nombre, grupo""",
                 t=tarea, nivel=nivel, v=variante, k=corte_k)


def tarea_grupos_resumen(conn: Connection, tarea: str, nivel: str, variante: str, corte_k: int) -> list[dict]:
    return _rows(conn, """SELECT categoria, grupos_total,
                                 mae_modelo::float8 AS mae_modelo, mae_base::float8 AS mae_base, spearman::float8 AS spearman
                          FROM resumen_tarea_grupo_resumen
                          WHERE tarea = :t AND nivel = :nivel AND variante = :v AND corte_k = :k ORDER BY categoria""",
                 t=tarea, nivel=nivel, v=variante, k=corte_k)


# --------------------------------------------------------------------------- #
# View "Lo que pasó" (migration 029): one JSON document per block and filter
# --------------------------------------------------------------------------- #
def _vista(conn: Connection, tabla: str, filtro: str | None) -> dict[tuple[str, str], object]:
    """The documents of one filter plus the whole-UCN ones (``meta``, the model blocks, the faculty list): the views hold
    one document per block and filter (2.4 MB and 0.5 MB with the programs), and a request needs one filter only."""
    if filtro is None:
        filas = _rows(conn, f"SELECT bloque, facultad, contenido FROM {tabla}")
    else:
        filas = _rows(conn, f"SELECT bloque, facultad, contenido FROM {tabla} WHERE facultad IN (:ucn, :filtro)", ucn=UCN, filtro=filtro)
    return {(r["bloque"], r["facultad"]): r["contenido"] for r in filas}


def historico(conn: Connection, filtro: str | None = None) -> dict[tuple[str, str], object]:
    """``{(bloque, facultad): contenido}`` (``facultad`` is the filter key: «Toda la UCN», a faculty or a program code).
    With ``filtro``, only that filter and «Toda la UCN». Empty when the view was not exported."""
    return _vista(conn, "vista_historica", filtro)


# --------------------------------------------------------------------------- #
# Tab "Lo que viene" (migration 032): one JSON document per block and filter
# --------------------------------------------------------------------------- #
def proyeccion(conn: Connection, filtro: str | None = None) -> dict[tuple[str, str], object]:
    """``{(bloque, facultad): contenido}``. With ``filtro``, only that filter and «Toda la UCN». Empty when not exported."""
    return _vista(conn, "vista_proyeccion", filtro)
