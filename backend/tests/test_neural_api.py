"""DAI Neural API against a throwaway schema (``neural_test``) built from synthetic people.

Opt-in: skipped unless the DEV_* variables of the localhost dev database are set (same as
``Redes/tests/integration``). The core tables are replayed from ``Redes/sql/core`` inside ``neural_test``, the
marts are built there with the real mart builder, and the API runs with ``search_path=neural_test,neural_meta``
(dictionaries come from the real ``neural_meta``, read only). The schema is dropped at the end.

Access goes through the in-memory adapter, exactly as ``test_auth_gates.py`` does.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

import pytest

REDES = Path(__file__).resolve().parents[2] / "Redes"
_DEV = ("DEV_HOST", "DEV_PORT", "DEV_DB", "DEV_USER", "DEV_PASSWORD")
pytestmark = [
    pytest.mark.skipif(not all(os.environ.get(k) for k in _DEV), reason="DEV_* environment variables not set"),
    pytest.mark.skipif(not (REDES / "pipelines").exists(), reason="Redes folder not present"),
]

if REDES.exists():
    # `Redes/tests` is a regular package and would shadow this suite's `tests` namespace: the path is only
    # needed while the pipeline modules are imported.
    sys.path.insert(0, str(REDES))
    try:
        from pipelines.common.db import dev_connection  # noqa: E402
        from pipelines.marts import build as mart_build  # noqa: E402
        from pipelines.migrate import split_statements  # noqa: E402
    finally:
        sys.path.remove(str(REDES))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import AuthUser  # noqa: E402
from app.services import accesos  # noqa: E402
from app.services import auth as auth_service  # noqa: E402
from app.services.accesos import InMemoryAccessRepository  # noqa: E402
from app.services.neural import aceptacion, db as neural_db  # noqa: E402

T = "neural_test"
LECTOR = "lector@ucn.cl"
AJENO = "cualquiera@ucn.cl"
CORE_DDL = REDES / "sql" / "core" / "004_core.sql"
MART_DDL = REDES / "sql" / "core" / "009_mart.sql"
EXTRA_DDL = [REDES / "sql" / "core" / "015_programa_traslados.sql", REDES / "sql" / "core" / "016_resumen_modelos.sql",
             REDES / "sql" / "core" / "021_etapa_a_marts.sql",
             REDES / "sql" / "core" / "023_resumen_tareas.sql",
             REDES / "sql" / "core" / "028_resumen_grupo_t3_eventos.sql",
             REDES / "sql" / "core" / "029_vista_historica.sql",
             REDES / "sql" / "core" / "032_vista_temas_proyeccion.sql",
             REDES / "sql" / "core" / "033_sin_supresion.sql",
             REDES / "sql" / "core" / "034_grupo_intervalos.sql"]


def rut_a(i: int) -> str:
    return f"1000{i:04d}-0"        # cohort 201910 (12 students)


def rut_b(j: int) -> str:
    return f"2000{j:04d}-0"        # cohort 202010 (3 students)


RUT_LATE = "30000001-0"
RUT_VIEWER = "50000001-0"          # applicant of 202010 that never enrolled
RUTS_NO_MATRICULADOS = [f"4000{k:04d}-0" for k in range(1, 4)]


def key(rut: str) -> str:
    """Opaque stand-in for the pseudonymized key of the synthetic people (the API never computes or serves it)."""
    return hmac.new(b"t" * 64, rut.encode("utf-8"), hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------- #
# Synthetic data (core tables)
# --------------------------------------------------------------------------- #
def _ddl() -> list[str]:
    out = []
    for path, repl in ((CORE_DDL, "neural_core."), (MART_DDL, "neural_mart.")):
        out += split_statements(path.read_text(encoding="utf-8").replace(repl, f"{T}."))
    for path in EXTRA_DDL:
        out += split_statements(path.read_text(encoding="utf-8").replace("neural_mart.", f"{T}."))
    return out


def _persona(cur, pk):
    cur.execute(f"INSERT INTO {T}.persona (persona_key) VALUES (%s)", (pk,))


def _episodio(cur, pk, adm, ultimo, n_estados, clase):
    cur.execute(
        f"INSERT INTO {T}.episodio_programa (persona_key, cod_programa, cod_admision, periodo_admision, primer_periodo, "
        f"ultimo_periodo, n_tramos, n_estados, no_contiguo, catalogo_inicial, catalogo_final, ultimo_estado_clase) "
        f"VALUES (%s, 'C101', 'LS', %s, %s, %s, 1, %s, false, '2019', '2019', %s) RETURNING episodio_id",
        (pk, adm, adm, ultimo, n_estados, clase))
    return cur.fetchone()[0]


def _estados(cur, pk, ep, adm, filas):
    """filas: [(periodo, sorlcur, cod_estado, es_reversa)]; canonical order = (periodo, sorlcur)."""
    for orden, (periodo, sorlcur, cod, reversa) in enumerate(sorted(filas), start=1):
        cur.execute(
            f"INSERT INTO {T}.evento_estado (persona_key, sorlcur, episodio_id, periodo, orden_canonico, tramo_n, "
            f"cod_programa, cod_admision, periodo_admision, catalogo, cod_estado, es_correccion_sistema, carga_id) "
            f"VALUES (%s, %s, %s, %s, %s, %s, 'C101', 'LS', %s, '2019', %s, %s, 1)",
            (pk, sorlcur, None if reversa else ep, periodo, orden, None if reversa else 1, adm, cod, reversa))


_nrc = iter(range(1, 10**6))


def _intento(cur, pk, ep, periodo, materia, curso, nota, opor=1, convalidacion=False):
    evaluado = not convalidacion
    aprobado = True if convalidacion else nota >= 4.0
    cur.execute(
        f"INSERT INTO {T}.intento_asignatura (periodo, persona_key, cod_carrera, catalogo, materia, curso, oportunidad, "
        f"nrc, episodio_id, codigo_asignatura, nota_texto, nota_parse, nota_numerica, nota_es_heredada, resultado_tipo, "
        f"aprobado_curricular, es_intento_evaluado, creditos, carga_id) "
        f"VALUES (%s, %s, 'C101', '2019', %s, %s, %s, %s, %s, %s, %s, %s, %s, false, %s, %s, %s, 6, 1)",
        (periodo, pk, materia, curso, opor, str(next(_nrc)), ep, f"{materia}-{curso}",
         "DPA" if convalidacion else str(nota), "dpa" if convalidacion else "numeric",
         None if convalidacion else nota, "convalidacion" if convalidacion else "evaluado", aprobado, evaluado))


def _via(cur, pk, year, cod, matricula, ponderado):
    cur.execute(
        f"INSERT INTO {T}.postulacion_via (year_admision, persona_key, cod_carrera, cod_admision, matricula, ponderado, "
        f"puntaje_nem, puntaje_ranking, tipo_colegio, depend_colegio, carga_id) "
        f"VALUES (%s, %s, 'C101', %s, %s, %s, 640.5, 700.0, 'Científico-Humanista', 'Municipal', 1)",
        (year, pk, cod, matricula, ponderado))
    cur.execute(
        f"INSERT INTO {T}.postulacion (year_admision, persona_key, cod_carrera, cod_admision_elegida, matricula_elegida, "
        f"alguna_via_matriculo, n_vias) VALUES (%s, %s, 'C101', %s, %s, %s, 1)",
        (year, pk, cod, matricula, matricula == "Y"))


def _cargar(cur):
    cur.execute(f"INSERT INTO {T}.programa (cod_programa, programa_d_id, valid_program, nombre_programa, id_nivel) "
                f"VALUES ('C101', 1, true, 'Ingeniería de Prueba', 1)")
    cur.execute(f"INSERT INTO {T}.programa_catalogo (cod_programa, catalogo, duracion) VALUES ('C101', '2019', 10)")
    for cod, sem, nombre in (("MAT-00001", 1, "ALGEBRA"), ("MAT-00002", 2, "CALCULO"), ("FIS-00001", 2, "FISICA"),
                             ("PRAC-04001", 10, "PRACTICA PROFESIONAL")):
        cur.execute(f"INSERT INTO {T}.asignatura_malla (cod_programa, catalogo, codigo_asignatura, semestre, creditos, "
                    f"nombre_asignatura) VALUES ('C101', '2019', %s, %s, 6, %s)", (cod, sem, nombre))
    for req, asig, en_malla, clasif in (("MAT-00001", "MAT-00002", True, "misma_malla"),
                                        ("ZZZZ-99999", "PRAC-04001", False, "ninguna")):
        cur.execute(f"INSERT INTO {T}.prerrequisito (cod_programa, catalogo, codigo_requisito, codigo_asignatura, "
                    f"filas_origen, asig_en_malla, req_en_malla, req_en_otro_programa, clasificacion) "
                    f"VALUES ('C101', '2019', %s, %s, 1, true, %s, false, %s)", (req, asig, en_malla, clasif))
    cur.execute(f"INSERT INTO {T}.hito_formativo (cod_programa, catalogo, codigo_asignatura, tipo_hito, metodo, validado, "
                f"version) VALUES ('C101', '2019', 'PRAC-04001', 'practica', 'regex_nombre_v1', false, 'v1')")

    # cohort 201910: 12 students; 1..4 graduate (U in 202120); 12 leaves (E) in 202010
    for i in range(1, 13):
        pk = key(rut_a(i))
        _persona(cur, pk)
        titula = i <= 4
        ultimo = "202120" if titula else "202010"
        ep = _episodio(cur, pk, "201910", ultimo, 6 if titula else 4, "egreso_titulacion" if titula else (
            "salida" if i == 12 else "matricula"))
        filas = [("201910", 1, "N", False), ("201910", 2, "M", False), ("201920", 3, "M", False),
                 ("202010", 4, "E" if i == 12 else "M", False)]
        if titula:
            filas += [("202110", 5, "G", False), ("202120", 6, "U", False)]
            cur.execute(f"INSERT INTO {T}.titulacion (persona_key, codigo_carrera, catalogo, fecha_titulacion, "
                        f"episodio_id, carga_id) VALUES (%s, 'C101', '2019', '2021-12-15', %s, 1)", (pk, ep))
        if i == 1:
            filas.append(("202010", 10, "2", True))             # system reversal: hidden from the timeline
        _estados(cur, pk, ep, "201910", filas)
        if i == 1:
            _intento(cur, pk, ep, "201910", "MAT", "00001", 3.0)                 # fails
            _intento(cur, pk, ep, "201920", "MAT", "00001", 4.5, opor=2)         # passes on the 2nd try
            _intento(cur, pk, ep, "201920", "FIS", "00001", None, convalidacion=True)   # DPA
            _intento(cur, pk, ep, "202010", "MAT", "00002", 5.5)
        else:
            _intento(cur, pk, ep, "201910", "MAT", "00001", round(3.0 + 0.2 * i, 1))
            _intento(cur, pk, ep, "201920", "MAT", "00002", 5.0)
        _via(cur, pk, "201910", "LS", "Y", 650.0)
    for k, rut in enumerate(RUTS_NO_MATRICULADOS, start=1):
        _via(cur, key(rut), "201910", "LS", "N", 650.0)             # applicants that never enrolled

    # cohort 202010: 3 students (always suppressed with the default threshold)
    for j in range(1, 4):
        pk = key(rut_b(j))
        _persona(cur, pk)
        ep = _episodio(cur, pk, "202010", "202020", 3, "matricula")
        _estados(cur, pk, ep, "202010", [("202010", 1, "N", False), ("202010", 2, "M", False), ("202020", 3, "M", False)])
        _intento(cur, pk, ep, "202010", "MAT", "00001", 5.0)
        _via(cur, pk, "202010", "LS", "Y", 700.0 + j)
    _via(cur, key(RUT_VIEWER), "202010", "LS", "N", 600.0)          # the applicant we look at

    # someone present in the latest period of the data, so that older cohorts are fully observed
    pk = key(RUT_LATE)
    _persona(cur, pk)
    ep = _episodio(cur, pk, "202610", "202620", 2, "matricula")
    _estados(cur, pk, ep, "202610", [("202610", 1, "M", False), ("202620", 2, "M", False)])


_sorl, _orden = iter(range(1, 10**7)), iter(range(1, 10**7))


def _ep_prog(cur, pk, prog, cod_admision, adm, ultimo, estados):
    """A one-program episode with its states (estados: [(periodo, cod_estado)]). Returns the episode id."""
    cur.execute(
        f"INSERT INTO {T}.episodio_programa (persona_key, cod_programa, cod_admision, periodo_admision, primer_periodo, "
        f"ultimo_periodo, n_tramos, n_estados, no_contiguo, catalogo_inicial, catalogo_final, ultimo_estado_clase) "
        f"VALUES (%s, %s, %s, %s, %s, %s, 1, %s, false, '2019', '2019', 'matricula') RETURNING episodio_id",
        (pk, prog, cod_admision, adm, estados[0][0], ultimo, len(estados)))
    ep = cur.fetchone()[0]
    for orden, (periodo, cod) in enumerate(estados, start=1):
        cur.execute(
            f"INSERT INTO {T}.evento_estado (persona_key, sorlcur, episodio_id, periodo, orden_canonico, tramo_n, "
            f"cod_programa, cod_admision, periodo_admision, catalogo, cod_estado, es_correccion_sistema, carga_id) "
            f"VALUES (%s, %s, %s, %s, %s, 1, %s, %s, %s, '2019', %s, false, 1)",
            (pk, next(_sorl), ep, periodo, next(_orden), prog, cod_admision, adm, cod))
    return ep


def rut_t(grupo: int, i: int) -> str:
    return f"{grupo}000{i:04d}-0"


def _cargar_traslados(cur):
    for cod, pid, nombre in (("T100", 11, "Programa Origen"), ("T200", 12, "Programa Destino"), ("T300", 13, "Programa Chico"),
                             ("8643", 14, "Ingeniería Civil Plan Común"), ("8553", 15, "Ingeniería Civil Industrial")):
        cur.execute(f"INSERT INTO {T}.programa (cod_programa, programa_d_id, valid_program, nombre_programa, id_nivel) "
                    f"VALUES (%s, %s, true, %s, 1)", (cod, pid, nombre))
    grupos = ((6, 12, "T100", "LS", "T200", "CC"),      # 12 changes of degree (counts as abandonment)
              (7, 10, "8643", "LS", "8553", "ES"),      # 10 specialty elections (not a loss)
              (8, 3, "T100", "LS", "T300", "LS"))       # 3 other transfers: always hidden
    for grupo, n, origen, adm_o, destino, adm_d in grupos:
        for i in range(1, n + 1):
            pk = key(rut_t(grupo, i))
            _persona(cur, pk)
            _ep_prog(cur, pk, origen, adm_o, "201910", "201920", [("201910", "N"), ("201910", "M"), ("201920", "M")])
            _ep_prog(cur, pk, destino, adm_d, "202010", "202010", [("202010", "M")])


def _cargar_modelos(cur):
    cur.execute(f"INSERT INTO {T}.resumen_modelos_construccion (id, filas) VALUES (1, 6)")
    for modelo, nombre, familia, escalon, valor in (("cb_acad", "CatBoost (ingreso + agregados)", "arboles", 2, 0.34),
                                                    ("gru_seq", "GRU (ingreso + secuencia por semestre)", "red", 3, 0.325)):
        cur.execute(f"INSERT INTO {T}.resumen_modelos (tarea, corte_k, conjunto, modelo, modelo_nombre, familia, escalon, "
                    f"escalon_nombre, metrica, valor, ic_inf, ic_sup, n_evaluacion) VALUES "
                    f"('t1', 1, 'test', %s, %s, %s, %s, 'Escalón', 'ap', %s, %s, %s, 4934)",
                    (modelo, nombre, familia, escalon, valor, valor - 0.05, valor + 0.05))
    cur.execute(f"INSERT INTO {T}.resumen_modelos_delta (tarea, corte_k, conjunto, modelo_a, modelo_b, metrica, delta, "
                f"ic_inf, ic_sup, veredicto) VALUES ('t1', 1, 'test', 'gru_seq', 'cb_acad', 'ap', -0.015, -0.036, 0.007, "
                f"'sin_diferencia'), ('t1', 1, 'test', 'gru_seq', 'cb_acad', 'brier', 0.001, 0.0, 0.002, 'empeora')")
    cur.execute(f"INSERT INTO {T}.resumen_modelos_info (tarea, corte_k, modelo, clave, valor_num, valor_texto) VALUES "
                f"('t1', 1, 'gru_seq', 'n_parametros', 16561, NULL), ('t3', 2, 'nn_gru', 'hidden', NULL, '128-64')")
    cur.execute(f"INSERT INTO {T}.resumen_modelos_titular (tarea, orden, clave, texto) VALUES "
                f"('t1', 1, 't1_gru_vs_arboles_k1', 'Secuencia: la GRU no se distingue de CatBoost.')")


def _cargar_tareas(cur):
    """Two tasks of the per-task summary: T1 (two cuts, groups by program) and T4 (forecast marked as not reliable)."""
    cur.execute(f"INSERT INTO {T}.resumen_tarea (tarea, orden, nombre, pregunta, poblacion, evento, estado, estado_etiqueta, "
                f"veredicto_redes, metrica_titular, metrica_secundaria) VALUES "
                f"('t1', 1, 'T1 · Continuidad', '¿Sigue matriculada?', 'Episodios de pregrado.', 'no continuidad observada', "
                f"'completo', 'Benchmark completo', 'Las redes no agregan señal.', 'ap', 'roc_auc'), "
                f"('t4', 4, 'T4 · Cambio de programa', '¿Cambia de programa?', 'Trayectorias.', 'traslado', 'completo', "
                f"'Benchmark completo', 'Se conserva el clásico.', 'ap', 'roc_auc')")
    cur.execute(f"INSERT INTO {T}.resumen_tarea_nota (tarea, tipo, orden, texto) VALUES "
                f"('t1', 'dato', 1, 'P58: sin reprobaciones en 201920.'), ('t1', 'limite', 1, 'Pocos eventos.')")
    cur.execute(f"INSERT INTO {T}.resumen_tarea_vista (tarea, variante, corte_k, etiqueta, principal, conservado_modelo, "
                f"referencia_modelo, metrica_titular, metrica_secundaria, concluyente, pronostico_agregado, nota) VALUES "
                f"('t1', 'base', 1, '', true, 'cb_acad', 'baseline_tasa', 'ap', 'roc_auc', true, 'descriptivo', NULL), "
                f"('t1', 'base', 2, '', false, 'cb_acad', 'baseline_tasa', 'ap', 'roc_auc', true, 'descriptivo', NULL), "
                f"('t4', 'base', 2, '', true, 'lr_agg', 'baseline_tasa', 'ap', 'roc_auc', true, 'no_confiable', 'No confiable.')")
    cur.execute(f"INSERT INTO {T}.resumen_tarea_particion (tarea, variante, corte_k, particion, n, eventos, tasa) VALUES "
                f"('t1', 'base', 1, 'train', 12000, 750, 0.0625), ('t1', 'base', 1, 'test', 4934, 280, 0.0567), "
                f"('t4', 'base', 2, 'test', 4688, 141, 0.0301)")
    for tarea, k, modelo, nombre, fam, esc, val in (
            ("t1", 1, "baseline_tasa", "Tasa histórica del programa", "referencia", 0, 0.07),
            ("t1", 1, "cb_acad", "CatBoost (ingreso + agregados)", "arboles", 2, 0.36),
            ("t1", 1, "gru_seq", "GRU (ingreso + secuencia)", "red", 3, 0.33),
            ("t4", 2, "baseline_tasa", "Tasa histórica del programa", "referencia", 0, 0.03),
            ("t4", 2, "lr_agg", "Logística (ingreso + agregados)", "regresion", 2, 0.094)):
        cur.execute(f"INSERT INTO {T}.resumen_tarea_metrica (tarea, variante, corte_k, modelo, modelo_nombre, familia, escalon, "
                    f"escalon_nombre, metrica, valor, ic_inf, ic_sup, n_evaluacion, conservado) VALUES "
                    f"(%s, 'base', %s, %s, %s, %s, %s, 'Escalón', 'ap', %s, %s, %s, 4934, %s)",
                    (tarea, k, modelo, nombre, fam, esc, val, val - 0.03, val + 0.03, modelo in ("cb_acad", "lr_agg")))
    cur.execute(f"INSERT INTO {T}.resumen_tarea_delta (tarea, variante, corte_k, modelo_a, modelo_b, metrica, delta, ic_inf, "
                f"ic_sup, veredicto) VALUES ('t1', 'base', 1, 'gru_seq', 'cb_acad', 'ap', -0.03, -0.05, -0.01, 'empeora')")
    cur.execute(f"INSERT INTO {T}.resumen_tarea_calibracion (tarea, variante, corte_k, modelo, decil, n, riesgo_medio, "
                f"tasa_observada) VALUES ('t1', 'base', 1, 'cb_acad', 1, 494, 0.03, 0.01), ('t1', 'base', 1, 'cb_acad', 2, 494, 0.06, 0.07)")
    cur.execute(f"INSERT INTO {T}.resumen_tarea_grupo (tarea, variante, corte_k, nivel, categoria, grupo, nombre, facultad, n, "
                f"eventos, observada, obs_inf, obs_sup, esperada, esp_inf, esp_sup, referencia, ap, roc_auc, ap_lo, ap_hi, auc_lo, auc_hi, "
                f"tasa_lo, tasa_hi, esperado_lo, esperado_hi) VALUES "
                f"('t1', 'base', 1, 'programa', '', 'C101', 'ARQUITECTURA', 'Escuela de Arquitectura', 173, 20, 0.116, NULL, NULL, 0.1, NULL, NULL, NULL, 0.4, 0.85, "
                f"0.3, 0.5, 0.8, 0.9, 0.07, 0.17, 0.08, 0.12), "
                f"('t1', 'base', 1, 'programa', '', 'C102', 'DERECHO', 'Facultad de Ciencias Jurídicas', 300, NULL, 0.05, NULL, NULL, 0.05, NULL, NULL, NULL, NULL, NULL, "
                f"NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL), "
                f"('t4', 'base', 2, 'facultad', '', 'Facultad de Ciencias', 'Facultad de Ciencias', NULL, 300, 20, 0.07, 0.05, 0.09, 0.15, 0.13, 0.17, 0.1, NULL, NULL, "
                f"NULL, NULL, NULL, NULL, 0.05, 0.09, 0.13, 0.17)")
    cur.execute(f"INSERT INTO {T}.resumen_tarea_grupo_resumen (tarea, variante, corte_k, nivel, categoria, grupos_total, "
                f"grupos_reportables, mae_modelo, mae_base, spearman) VALUES "
                f"('t1', 'base', 1, 'programa', '', 2, 2, NULL, NULL, NULL)")


def _fila_semestres(n, dejan, elim):
    """Fixture of the ``semestres`` block: ``dejan`` / ``elim`` are the counts of semester 1 and 2 (the rest is zero)."""
    filas = [{"semestre": s, "dejan": (dejan if s == 1 else 0), "eliminados": (elim if s == 2 else 0),
              "pct_dejan": (dejan / n if s == 1 else 0.0), "pct_eliminados": (elim / n if s == 2 else 0.0)} for s in range(1, 13)]
    return {"n": n, "bajas": dejan + elim, "bajas_primer_anio": dejan + elim, "pct_bajas_primer_anio": 1.0,
            "pct_bajas": (dejan + elim) / n, "filas": filas}


MODELO_T1 = {"tarea": "T1", "tarea_nombre": "Continuidad", "modelo": "cb_acad", "modelo_nombre": "CatBoost (ingreso + agregados)",
             "k": 1, "corte": "1.er semestre", "particion": "Prueba: cohortes 2022-2023", "tipo": "esperado"}
MODELO_T2 = {"tarea": "T2", "tarea_nombre": "Aprobación por ramo", "modelo": "cb_c_nuevas", "modelo_nombre": "CatBoost (c)",
             "k": 0, "corte": "inicio de cada período", "particion": "Prueba: 2023-2024", "tipo": "esperado"}
PROGRAMAS = [{"codigo": "P1", "nombre": "Programa Uno", "facultad": "Facultad A"},
             {"codigo": "P2", "nombre": "Programa Dos", "facultad": "Facultad A"},
             {"codigo": "PSD", "nombre": "Programa Sin Datos", "facultad": "Facultad A"},
             {"codigo": "P9", "nombre": "Programa Chico", "facultad": "Facultad Chica"}]
# which model each block of "Lo que paso" declares (None = observed data); senales / esperar_semestre carry several
MODELO_BLOQUE = {"siguieron": MODELO_T1, "alcance": MODELO_T1, "perfil_ingreso": MODELO_T1, "primer_semestre": MODELO_T1,
                 "eliminados": MODELO_T1, "ramos_esperado": MODELO_T2}

META_HISTORICO = {"version": 1, "modelo_t1": "cb_acad", "modelo_t5": "gru_adm", "programas": PROGRAMAS,
                  "filtros": ["Toda la UCN", "Facultad A", "Facultad Chica"], "periodo_causales_desde": "201610",
                  "modelos": {"semestres": None, "siguieron": MODELO_T1, "por_facultad": MODELO_T1},
                  "cohortes": {"semestres": [2015, 2020], "siguieron": [2022, 2023], "eliminados": [2016, 2026],
                               "alcance": [2022, 2023], "test_t5": [2023, 2024]}}


def _cargar_historico(cur):
    """Lo que paso: the UCN and one faculty with a normal block, and a small one whose blocks must disappear."""
    curva = [{"apoyados": i / 20, "alcanzados": min(1.0, i / 20 * 5)} for i in range(21)]
    alcance = {"n": 4934, "eventos": 280, "fraccion_apoyo": 0.1, "apoyados": 494, "alcanzados": 157, "pct_alcanzado": 0.56,
               "de_cada_10": 5.6, "al_azar_de_cada_10": 1.0, "curva": curva}
    eliminados = {"totales": [{"anio": 2024, "eliminados": 900}, {"anio": 2025, "eliminados": 7}], "anios": [
        {"anio": 2023, "n": 2123, "eliminados": 278, "tasa": 0.13, "parcial": False, "esperados": 211.6, "tasa_esperada": 0.0997},
        {"anio": 2024, "n": 2565, "eliminados": 178, "tasa": 0.069, "parcial": False, "esperados": None, "tasa_esperada": None},
        {"anio": 2025, "n": 800, "eliminados": 7, "tasa": 0.009, "parcial": True, "esperados": None, "tasa_esperada": None}],
        "anio_reglamento": 2025, "clave": {"anio": 2024, "eliminados": 900},
        "causales": {"total": 12184, "filas": [
            {"grupo": "tercera", "etiqueta": "3.a oportunidad", "n": 3183, "pct": 0.26},
            {"grupo": "no_inscribe", "etiqueta": "No inscribe asignaturas", "n": 8990, "pct": 0.738},
            {"grupo": "egresado", "etiqueta": "Egresado sin titularse", "n": 4, "pct": 0.0003},
            {"grupo": "otras", "etiqueta": "Otras causas", "n": 7, "pct": 0.0006}]}}
    docs = [
        ("meta", "Toda la UCN", META_HISTORICO),
        ("semestres", "Toda la UCN", _fila_semestres(14880, 4000, 3000)),
        ("semestres", "Facultad A", _fila_semestres(900, 200, 150)),
        ("semestres", "Facultad Chica", _fila_semestres(8, 2, 1)),
        ("siguieron", "Toda la UCN", {"n": 4934, "siguieron": 4654, "esperados": 4676.5, "pct_siguieron": 0.943,
                                      "pct_esperado": 0.9478, "diferencia": -22.5}),
        ("siguieron", "Facultad Chica", {"n": 60, "siguieron": 55, "esperados": 56.0, "pct_siguieron": 0.9167,
                                         "pct_esperado": 0.93, "diferencia": -1.0}),
        ("por_facultad", "Toda la UCN", [
            {"facultad": "Facultad A", "n": 1166, "pct_siguieron": 0.93, "pct_esperado": 0.94},
            {"facultad": "Facultad Chica", "n": 60, "pct_siguieron": 0.9167, "pct_esperado": 0.93}]),
        ("eliminados", "Toda la UCN", eliminados),
        ("alcance", "Toda la UCN", alcance),
        ("alcance", "Facultad Chica", {**alcance, "n": 60, "eventos": 12, "alcanzados": 6, "apoyados": 6}),
    ]
    docs += _seed_temas()
    docs += [("semestres", "P1", _fila_semestres(120, 30, 20)), ("semestres", "P9", _fila_semestres(5, 1, 1)),
             ("siguieron", "P1", {"n": 70, "siguieron": 60, "esperados": 62.0, "pct_siguieron": 0.857, "pct_esperado": 0.886,
                                  "diferencia": -2.0}),
             ("ramos_reprobados", "P1", {"desde": "202110", "hasta": "202520", "por_tasa": [], "por_volumen": []})]
    for bloque, facultad, contenido in docs:
        if isinstance(contenido, dict) and bloque in ("semestres", "ramos_reprobados"):
            contenido = {**contenido, "modelo": None}
        elif isinstance(contenido, dict) and bloque in MODELO_BLOQUE:
            contenido = {**contenido, "modelo": MODELO_BLOQUE[bloque]}
        cur.execute(f"INSERT INTO {T}.vista_historica (bloque, facultad, contenido) VALUES (%s, %s, %s::jsonb)",
                    (bloque, facultad, json.dumps(contenido)))


def _seed_temas():
    """New blocks of "Lo que paso" (by topics). The export is NOT trusted: some rows break the rules on purpose."""
    perfil = {"n": 4934, "nota_asociacion": True, "dimensiones": [
        {"dimension": "via", "filas": [   # 28 people with 7 who did not continue and 6 more: both small, merged into «otros»
            {"grupo": "regular", "etiqueta": "Ingreso regular", "n": 4000, "pct_siguieron": 0.94, "pct_esperado": 0.95},
            {"grupo": "especial", "etiqueta": "Ingreso especial", "n": 900, "pct_siguieron": 0.9, "pct_esperado": 0.91},
            {"grupo": "cambio", "etiqueta": "Cambio de carrera", "n": 28, "pct_siguieron": 0.75, "pct_esperado": 0.8},
            {"grupo": "otra", "etiqueta": "Otra", "n": 6, "pct_siguieron": 0.5, "pct_esperado": 0.5}]},
        {"dimension": "colegio", "filas": [   # a single small cell: the whole distribution is hidden
            {"grupo": "humanista", "etiqueta": "Humanista", "n": 500, "pct_siguieron": 0.9, "pct_esperado": 0.9},
            {"grupo": "otro", "etiqueta": "Otro", "n": 5, "pct_siguieron": 0.8, "pct_esperado": 0.8}]}]}
    primer = {"n": 4900, "nota_asociacion": True, "filas": [
        {"reprobaciones": "0", "n": 3000, "pct_siguieron": 0.96}, {"reprobaciones": "1", "n": 1200, "pct_siguieron": 0.93},
        {"reprobaciones": "2", "n": 600, "pct_siguieron": 0.9}, {"reprobaciones": "3+", "n": 100, "pct_siguieron": 0.85}]}
    ramo = {"codigo": "CALC1", "nombre": "Cálculo I", "depto": "MAT", "intentos": 500, "reprobados": 200, "tasa": 0.4, "lo": 0.35, "hi": 0.45}
    ramos = {"desde": "202110", "hasta": "202520",
             "por_tasa": [ramo, {**ramo, "codigo": "X1", "nombre": "Cinco", "reprobados": 5, "tasa": 0.01},
                          {**ramo, "codigo": "X2", "nombre": "Aprueban uno", "intentos": 12, "reprobados": 11, "tasa": 0.92}],
             "por_volumen": [ramo, {**ramo, "codigo": "X1", "nombre": "Cinco", "reprobados": 5, "tasa": 0.01}]}
    cifras = {"intentos": 300, "observados": 120, "esperados": 100.0, "diferencia": 20.0, "lo": 5.0, "hi": 35.0}
    esperado = {"ventanas": {"prueba": {"desde": "202310", "hasta": "202420", "ramos": [
        {"codigo": "CALC1", "nombre": "Cálculo I", **cifras, "nrc": "NRC-9981", "seccion": "S-77", "docente": "Profesor Fulano"},
        {"codigo": "CHICO", "nombre": "Pocos", **{**cifras, "intentos": 8, "observados": 7}}],
        "deptos": [{"depto": "MAT", "depto_desc": "Matemática", **cifras}]}}}
    cuellos = {"filas": [{"codigo": "CALC1", "nombre": "Cálculo I", "reprobados": 200, "dependientes": 12, "impacto": 2400},
                         {"codigo": "X9", "nombre": "Pocos fallos", "reprobados": 6, "dependientes": 3, "impacto": 18}]}
    malla = {"filas": [{"semestre": 1, "intentos": 5000, "reprobados": 1500, "tasa": 0.3},
                       {"semestre": 2, "intentos": 4000, "reprobados": 7, "tasa": 0.00175},
                       {"semestre": 3, "intentos": 6, "reprobados": 0, "tasa": 0.0},
                       {"semestre": 4, "intentos": 100, "reprobados": 95, "tasa": 0.95}]}
    causales = {"desde": "201610", "hasta": "202520", "nivel": "programa", "filas": [
        {"cod_programa": "P1", "programa": "Programa Uno", "total": 300, "causales": [
            {"grupo": "tercera", "etiqueta": "3.a oportunidad", "n": 250}, {"grupo": "egresado", "etiqueta": "Egresado sin titularse", "n": 50}]},
        {"cod_programa": "P2", "programa": "Programa Dos", "total": 200, "causales": [
            {"grupo": "tercera", "etiqueta": "3.a oportunidad", "n": 195}, {"grupo": "egresado", "etiqueta": "Egresado sin titularse", "n": 5}]},
        {"cod_programa": "P3", "programa": "Programa Tres", "total": 6, "causales": None},
        {"cod_programa": "P4", "programa": "Programa Cuatro", "total": 5, "causales": None}]}
    tiempo = {"regla_duracion": "Duración nominal = mayor semestre de la malla.", "filas": [
        {"cod_programa": "P1", "programa": "Programa Uno", "n": 100, "duracion_nominal_sem": 10, "pct_a_tiempo": 0.3,
         "pct_mas_1": 0.96, "pct_mas_2": 0.5},
        {"cod_programa": "P3", "programa": "Programa Tres", "n": 6, "duracion_nominal_sem": 10, "pct_a_tiempo": 0.5,
         "pct_mas_1": 0.5, "pct_mas_2": 0.5}]}
    senales = {"tareas": [
        {"tarea": "t1", "k": 1, "modelo": "cb_acad", "n_muestra": 5000,
         "senales": [{"familia": "notas", "etiqueta": "Notas del semestre", "peso_pct": 40.5, "caida_ap": 0.05}]},
        {"tarea": "t3", "k": 0, "modelo": "dt_lr_adm", "n_muestra": 4, "senales": []}],
        "aplica_a_poblacion": False, "modelo": None, "modelos": [MODELO_T1, MODELO_T2]}
    esperar = {"comparaciones": [{"tarea": "t1", "k_antes": 1, "k_despues": 2, "de_cada_10_antes": 5.6, "de_cada_10_despues": 6.1}],
               "nota_poblaciones": True, "aplica_a_poblacion": False, "modelo": None, "modelos": [MODELO_T1]}
    chica = {
        "perfil_ingreso": {"n": 8, "nota_asociacion": True, "dimensiones": [{"dimension": "via", "filas": [
            {"grupo": "regular", "etiqueta": "Ingreso regular", "n": 8, "pct_siguieron": 0.9, "pct_esperado": 0.9}]}]},
        "primer_semestre": {"n": 8, "nota_asociacion": True, "filas": [{"reprobaciones": "0", "n": 8, "pct_siguieron": 1.0}]},
        "ramos_reprobados": {"desde": "202110", "hasta": "202520", "por_tasa": [{**ramo, "intentos": 8, "reprobados": 4}], "por_volumen": []},
        "ramos_esperado": {"ventanas": {"prueba": {"desde": "202310", "hasta": "202420", "ramos": [
            {"codigo": "CHICO", "nombre": "Pocos", **{**cifras, "intentos": 8, "observados": 7}}], "deptos": []}}},
        "cuellos_botella": {"filas": [{"codigo": "X9", "nombre": "Pocos fallos", "reprobados": 6, "dependientes": 3, "impacto": 18}]},
        "semestre_malla": {"filas": [{"semestre": 1, "intentos": 6, "reprobados": 2, "tasa": 0.33}]},
        "causales_programa": {"desde": "201610", "hasta": "202520", "nivel": "facultad", "filas": [
            {"cod_programa": None, "programa": "Facultad Chica", "total": 6, "causales": None}]},
        "tiempo_egreso": {"regla_duracion": "x", "filas": [{"cod_programa": "P3", "programa": "Programa Tres", "n": 6,
                                                            "duracion_nominal_sem": 10, "pct_a_tiempo": 0.5, "pct_mas_1": 0.5, "pct_mas_2": 0.5}]}}
    docs = [("perfil_ingreso", "Toda la UCN", perfil), ("primer_semestre", "Toda la UCN", primer),
            ("ramos_reprobados", "Toda la UCN", ramos), ("ramos_esperado", "Toda la UCN", esperado),
            ("cuellos_botella", "Toda la UCN", cuellos), ("semestre_malla", "Toda la UCN", malla),
            ("causales_programa", "Toda la UCN", causales), ("tiempo_egreso", "Toda la UCN", tiempo),
            ("senales", "Toda la UCN", senales), ("esperar_semestre", "Toda la UCN", esperar),
            ("ramos_reprobados", "Facultad A", ramos), ("semestre_malla", "Facultad A", malla)]
    docs += [(bloque, "Facultad Chica", contenido) for bloque, contenido in chica.items()]
    return docs


MODELO_PROY = {"tarea": "T1", "tarea_nombre": "Continuidad", "modelo": "cb_ben_pit", "modelo_nombre": "CatBoost oficial (+ beneficios)",
               "k": 1, "corte": "1.er semestre", "particion": "Estudiantes vigentes al cierre de 202610, cohorte 2026", "tipo": "proyeccion"}
MODELO_PROY_EGRESO = {**MODELO_PROY, "tarea": "T3", "tarea_nombre": "Tiempo hasta egreso", "modelo": "gru_agg", "k": 4}
META_PROYECCION = {"version": 1, "corte": "202610", "filtros": ["Toda la UCN", "Facultad A", "Facultad Chica"],
                   "programas": PROGRAMAS[:2] + PROGRAMAS[3:],
                   "poblaciones": [{"bloque": "continuidad", "tarea": "t1", "k": 1, "modelo": "cb_ben_pit", "cohorte": 2026}],
                   "sin_proyeccion": {"n": 5324}}


def _entrada(cohorte, n, esperados, lo, hi, **extra):
    return {"cohorte": cohorte, "k": 1, "modelo": MODELO_PROY, "corte": "202610", "horizonte": "202620", "n": n,
            "esperados": esperados, "lo": lo, "hi": hi, **extra}


def _cargar_proyeccion(cur):
    """Lo que viene: the UCN with blocks that break the rules on purpose (the export is not trusted), a normal faculty and a small one."""
    hito = {"esperados": 100.0, "lo": 80.0, "hi": 120.0, "desde": "202620", "hasta": "203220"}
    continuidad = {"n": 4000, "esperados": 3800.5, "lo": 3780.2, "hi": 3820.8, "por_cohorte": [
        _entrada(2026, 3000, 2850.0, 2830.0, 2870.0, sin_historial_beneficios=4),
        _entrada(2025, 990, 940.0, 930.0, 950.0, sin_historial_beneficios=0), _entrada(2024, 6, 5.0, 3.0, 6.0)]}
    eliminacion = {"n": 4000, "esperados": 300.0, "lo": 270.0, "hi": 330.0, "por_cohorte": [
        {**_entrada(2025, 3000, 220.0, 200.0, 240.0), "horizonte_desde": "202610"},
        {**_entrada(2024, 1000, 80.0, 70.0, 90.0), "horizonte_desde": "202610"}],
        "observados_hasta_hoy": 7, "periodo_observado": "202610", "orientativo": True}
    egreso = {"n": 3000, "regla": "Egresados esperados acumulados.", "nominal": hito, "nominal_mas_2": None, "ya_pasado_nominal": 5,
              "ya_pasado_nominal_mas_2": 40, "horizonte_truncado": 0, "por_cohorte": [
                  {"cohorte": 2025, "k": 4, "modelo": MODELO_PROY_EGRESO, "corte": "202610", "horizonte": "203220", "n": 3000,
                   "nominal": hito, "nominal_mas_2": None}]}
    umbral = {"n": 4000, "en_umbral": 300, "a_1": 200, "a_2": 7, "lejos": 3493, "nota_p58": True}
    chica = {"n": 8, "esperados": 7.0, "lo": 6.0, "hi": 8.0,
             "por_cohorte": [_entrada(2026, 8, 7.0, 6.0, 8.0, sin_historial_beneficios=2)]}
    docs = [("meta", "Toda la UCN", META_PROYECCION), ("continuidad", "Toda la UCN", continuidad),
            ("eliminacion", "Toda la UCN", eliminacion), ("egreso", "Toda la UCN", egreso), ("umbral", "Toda la UCN", umbral),
            ("continuidad", "Facultad A", {**continuidad, "n": 500, "por_cohorte": [_entrada(2026, 500, 480.0, 470.0, 490.0)]}),
            ("umbral", "Facultad A", {"n": 500, "en_umbral": 30, "a_1": 40, "a_2": 50, "lejos": 380, "nota_p58": True}),
            ("continuidad", "Facultad Chica", chica), ("eliminacion", "Facultad Chica", {**chica, "observados_hasta_hoy": 0,
                                                                                         "periodo_observado": "202610", "orientativo": True}),
            ("egreso", "Facultad Chica", {"n": 8, "regla": "x", "nominal": hito, "nominal_mas_2": None, "ya_pasado_nominal": 3,
                                          "por_cohorte": []}),
            ("umbral", "Facultad Chica", {"n": 8, "en_umbral": 1, "a_1": 2, "a_2": 3, "lejos": 2, "nota_p58": True}),
            ("continuidad", "P1", {"n": 70, "esperados": 66.0, "lo": 64.0, "hi": 68.0, "por_cohorte": [_entrada(2026, 70, 66.0, 64.0, 68.0)]}),
            ("umbral", "P1", {"n": 70, "en_umbral": 3, "a_1": 4, "a_2": 5, "lejos": 58, "nota_p58": True}),
            ("continuidad", "P9", {"n": 3, "esperados": 2.5, "lo": 2.0, "hi": 3.0, "por_cohorte": [_entrada(2026, 3, 2.5, 2.0, 3.0)]})]
    for bloque, facultad, contenido in docs:
        if isinstance(contenido, dict) and bloque in ("continuidad", "eliminacion", "egreso"):
            contenido = {**contenido, "modelo": None, "modelos": [MODELO_PROY, MODELO_PROY_EGRESO]}
        elif isinstance(contenido, dict) and bloque == "umbral":
            contenido = {**contenido, "modelo": MODELO_PROY}
        cur.execute(f"INSERT INTO {T}.vista_proyeccion (bloque, facultad, contenido) VALUES (%s, %s, %s::jsonb)",
                    (bloque, facultad, json.dumps(contenido)))


@pytest.fixture(scope="module")
def mundo():
    with dev_connection() as c:
        c.autocommit = True
        c.execute(f"DROP SCHEMA IF EXISTS {T} CASCADE")
        c.execute(f"CREATE SCHEMA {T}")
        for stmt in _ddl():
            c.execute(stmt)
        with c.cursor() as cur:
            _cargar(cur)
            _cargar_traslados(cur)
            _cargar_modelos(cur)
            _cargar_tareas(cur)
            _cargar_historico(cur)
            _cargar_proyeccion(cur)
        mart_build.build(c, core_schema=T, mart_schema=T, meta_schema="neural_meta", out=lambda _m: None)
        yield c
        c.execute(f"DROP SCHEMA IF EXISTS {T} CASCADE")


def _url() -> str:
    env = os.environ
    opciones = quote(f"-c search_path={T},neural_meta", safe="")
    return (f"postgresql+psycopg://{quote(env['DEV_USER'], safe='')}:{quote(env['DEV_PASSWORD'], safe='')}"
            f"@{env['DEV_HOST']}:{env['DEV_PORT']}/{env['DEV_DB']}?options={opciones}")


@pytest.fixture()
def api(mundo, monkeypatch):
    monkeypatch.setenv("NEURAL_DATABASE_URL", _url())
    neural_db.reset()
    s = get_settings()
    monkeypatch.setattr(s, "app_env", "dev")
    monkeypatch.setattr(s, "boveda_database_url", "postgresql+psycopg://configurada-solo-en-test")
    repo = InMemoryAccessRepository()
    repo.add_module("neural", "DAI Neural")
    repo.add_module("percepcion", "Termómetro Institucional")
    repo.grant_access("neural", LECTOR, "lector", by="test")
    repo.registrar_aceptacion("neural", LECTOR, aceptacion.VERSION)  # the gate stays on: LECTOR accepted the current text
    accesos.configure(repo)
    with TestClient(app) as client:
        yield client
    accesos.reset()
    neural_db.reset()


def _h(email: str) -> dict:
    user = AuthUser(email=email, name=email, auth_mode="google")
    return {"Authorization": f"Bearer {auth_service.build_login_response(user, message='', next_step='').session_token}"}


def get(api, path, **params):
    return api.get(f"/neural{path}", params=params, headers=_h(LECTOR))


# --------------------------------------------------------------------------- #
# Access
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("method,path", [
    ("get", "/neural/programas"), ("get", "/neural/calidad"), ("get", "/neural/traslados/resumen"),
    ("get", "/neural/traslados/programa/T100"), ("get", "/neural/modelos/resumen"),
    ("get", "/neural/modelos/malla-ejemplo"), ("get", "/neural/modelos/tareas"), ("get", "/neural/modelos/tarea/t1"),
    ("get", "/neural/modelos/tarea/t1/grupos?nivel=programa"), ("get", "/neural/historico"),
])
def test_requires_a_session_and_the_module(api, method, path):
    assert getattr(api, method)(path).status_code == 401
    assert getattr(api, method)(path, headers=_h(AJENO)).status_code == 403


def test_a_reader_of_another_module_does_not_enter(api):
    from app.services.accesos import get_repository

    get_repository().grant_access("percepcion", "otro@ucn.cl", "lector", by="test")
    assert api.get("/neural/programas", headers=_h("otro@ucn.cl")).status_code == 403


def test_reader_role_is_enough(api):
    assert get(api, "/programas").status_code == 200


def test_module_without_database_url_answers_503_and_the_app_boots(api, monkeypatch):
    monkeypatch.setenv("NEURAL_DATABASE_URL", "")
    neural_db.reset()
    r = get(api, "/programas")
    assert r.status_code == 503 and "no está configurado" in r.json()["detail"]
    assert api.get("/health").status_code == 200


# --------------------------------------------------------------------------- #
# Unknown things are 404
# --------------------------------------------------------------------------- #
def test_unknown_program_cohorts_is_404(api):
    assert get(api, "/programa/NOEXISTE/cohortes").status_code == 404


# --------------------------------------------------------------------------- #
# Programs, quality
# --------------------------------------------------------------------------- #
def test_programs_and_cohorts(api):
    progs = get(api, "/programas").json()
    c101 = next(p for p in progs if p["cod_programa"] == "C101")
    assert c101["n_episodios"] == 16 and c101["primera_cohorte"] == "201910" and c101["ultima_cohorte"] == "202610"
    j = get(api, "/programa/C101/cohortes").json()
    res = {r["cohorte"]: r for r in j["resultados"]}
    a = res["201910"]
    assert a["n_ingreso"] == 12 and "suprimido" not in a and a["pocos_casos"] is False and a["duracion"] == 10 and a["duracion_anios"] == 5
    assert a["censurado_d"] is False and a["titulados_d"] == 4 and a["titulados_d1"] == 4
    assert a["n_retencion_obs"] == 12 and a["n_retenidos"] == 11
    b = res["202010"]
    assert b["n_ingreso"] == 3 and b["pocos_casos"] is True and b["titulados_d"] is not None   # small cohorts are served as stored
    late = res["202610"]
    assert late["censurado_d"] is True and late["titulados_d"] is None   # censored, not zero
    assert {s["cohorte"] for s in j["semestres_por_cohorte"]} >= {"201910", "202010"}


def test_quality_endpoint(api):
    j = get(api, "/calidad").json()
    assert set(j) == {"cargas", "auditoria", "marts", "cobertura"}
    assert {m["mart"] for m in j["marts"]} >= {"indicador_periodo", "ficha_episodio", "cohorte_resultado"}
    assert all("n_min" not in m for m in j["marts"])
    assert j["auditoria"]["total"] >= j["auditoria"]["ok"] >= 0
    assert any("2016" in n for n in j["cobertura"]) and any("2025" in n for n in j["cobertura"])


# --------------------------------------------------------------------------- #
# Transfers between programs (P61)
# --------------------------------------------------------------------------- #
def test_transfers_summary_counts_every_type_including_small_groups(api):
    j = get(api, "/traslados/resumen").json()
    assert "n_min" not in j and "total_suprimido" not in j and "otros_flujos" not in j
    assert j["total"] == 25
    tipos = {t["tipo"]: t for t in j["por_tipo"]}
    assert tipos["cambio_carrera"]["n"] == 12 and tipos["cambio_carrera"]["cuenta_abandono"] is True
    assert tipos["eleccion_especialidad"]["n"] == 10 and tipos["eleccion_especialidad"]["cuenta_abandono"] is False
    assert tipos["traslado_otro"]["n"] == 3 and "suprimido" not in tipos["traslado_otro"]      # 3 people: served, marked
    assert tipos["traslado_otro"]["pocos_casos"] is True and tipos["cambio_carrera"]["pocos_casos"] is False
    assert tipos["cambio_ciclo"]["n"] == 0
    assert j["anios_disponibles"] == {"desde": 2020, "hasta": 2020}
    assert {(a["anio"], a["tipo"], a["n"]) for a in j["por_anio"]} == {
        (2020, "cambio_carrera", 12), (2020, "eleccion_especialidad", 10), (2020, "traslado_otro", 3)}


def test_transfer_flows_are_all_served_with_their_count(api):
    j = get(api, "/traslados/resumen").json()
    assert [(f["cod_origen"], f["cod_destino"], f["n"], f["tipo_principal"], f["pocos_casos"]) for f in j["flujos"]] == [
        ("T100", "T200", 12, "cambio_carrera", False), ("8643", "8553", 10, "eleccion_especialidad", False),
        ("T100", "T300", 3, "traslado_otro", True)]
    assert j["flujos"][0]["nombre_origen"] == "Programa Origen"


def test_balance_with_and_without_specialty_election(api):
    j = get(api, "/traslados/resumen").json()
    b = {r["cod_programa"]: r for r in j["balance"]}
    assert b["8553"]["ganados_total"] == 10 and b["8553"]["ganados_sin_eleccion"] == 0
    assert b["8643"]["perdidos_total"] == 10 and b["8643"]["perdidos_sin_eleccion"] == 0
    assert b["8643"]["neto_total"] == -10 and b["8643"]["neto_sin_eleccion"] == 0
    assert b["T100"]["perdidos_total"] == 15 and b["T100"]["neto_total"] == -15          # 12 + 3
    assert b["T200"]["ganados_total"] == 12 and b["T200"]["neto_total"] == 12
    assert b["T300"]["ganados_total"] == 3 and b["T300"]["neto_total"] == 3             # a group of 3 is served


def test_transfer_filters(api):
    j = get(api, "/traslados/resumen", tipo="cambio_carrera").json()
    assert j["total"] == 12 and len(j["flujos"]) == 1 and j["filtros"]["tipo"] == "cambio_carrera"
    j = get(api, "/traslados/resumen", solo_abandono="true").json()
    tipos = {t["tipo"]: t["n"] for t in j["por_tipo"]}
    assert tipos["eleccion_especialidad"] == 0 and tipos["cambio_carrera"] == 12 and j["total"] == 15
    j = get(api, "/traslados/resumen", anio_desde=2021).json()
    assert j["total"] == 0 and j["flujos"] == [] and j["balance"] == []
    j = get(api, "/traslados/resumen", anio_desde=2020, anio_hasta=2020).json()
    assert j["total"] == 25


def test_transfer_filters_are_validated(api):
    assert get(api, "/traslados/resumen", tipo="inventado").status_code == 422
    assert get(api, "/traslados/resumen", anio_desde=2022, anio_hasta=2020).status_code == 422
    assert get(api, "/traslados/resumen", anio_desde="abc").status_code == 422


def test_transfers_of_one_program(api):
    j = get(api, "/traslados/programa/T100").json()
    assert j["nombre_programa"] == "Programa Origen" and "n_min" not in j
    assert j["balance"]["perdidos_total"] == 15 and j["balance"]["ganados_total"] == 0
    assert [(d["cod_programa"], d["n"], d["pocos_casos"]) for d in j["destinos"]] == [("T200", 12, False), ("T300", 3, True)]
    assert j["origenes"] == []
    salidas = {t["tipo"]: t["n"] for t in j["salidas_por_tipo"]}
    assert salidas["cambio_carrera"] == 12 and salidas["traslado_otro"] == 3
    assert [(a["anio"], a["perdidos"], a["ganados"], a["neto"]) for a in j["por_anio"]] == [(2020, 15, 0, -15)]
    e = get(api, "/traslados/programa/8553").json()
    assert e["balance"]["ganados_total"] == 10 and e["balance"]["ganados_sin_eleccion"] == 0
    assert e["origenes"][0]["cod_programa"] == "8643"


def test_transfers_of_unknown_or_invalid_program(api):
    assert get(api, "/traslados/programa/ZZZZ").status_code == 404
    assert get(api, "/traslados/programa/a b").status_code == 422


def test_transfer_responses_hold_no_person_level_data(api):
    for path in ("/traslados/resumen", "/traslados/programa/T100"):
        r = get(api, path)
        assert "persona_key" not in r.text and "episodio_id" not in r.text
        import re
        assert not re.search(r"[0-9a-f]{64}", r.text)


# --------------------------------------------------------------------------- #
# Models: benchmark aggregates
# --------------------------------------------------------------------------- #
def test_models_summary_serves_aggregates_with_the_notice(api):
    j = get(api, "/modelos/resumen").json()
    assert j["disponible"] is True and "predicciones individuales no están habilitadas" in j["aviso"]
    modelos = {m["modelo"]: m for m in j["modelos"]}
    assert modelos["cb_acad"]["metricas"]["ap"] == {"valor": 0.34, "ic_inf": pytest.approx(0.29), "ic_sup": pytest.approx(0.39)}
    assert modelos["gru_seq"]["escalon"] == 3 and modelos["gru_seq"]["n_evaluacion"] == 4934
    assert [(c["modelo_a"], c["modelo_b"], c["metrica"], c["veredicto"]) for c in j["comparaciones"]] == [
        ("gru_seq", "cb_acad", "ap", "sin_diferencia")]                 # only the main metrics are served
    assert {(a["modelo"], a["clave"]) for a in j["arquitectura"]} == {("gru_seq", "n_parametros"), ("nn_gru", "hidden")}
    assert j["titulares"][0]["clave"] == "t1_gru_vs_arboles_k1"


def test_models_summary_has_no_prediction_or_person_fields(api):
    r = get(api, "/modelos/resumen")
    text = r.text.lower()
    for prohibido in ("persona_key", "episodio_id", "prediccion", "probabilidad", "y_pred", "rut"):
        assert prohibido not in text.replace("predicciones individuales", "")
    assert set(r.json()) == {"disponible", "generado_en", "aviso", "modelos", "comparaciones", "arquitectura",
                             "titulares", "notas"}


def test_example_malla_has_courses_and_prerequisites_only(api):
    j = get(api, "/modelos/malla-ejemplo", cod_programa="C101").json()
    assert j["cod_programa"] == "C101" and j["catalogo"] == "2019" and j["semestre_max"] == 4
    assert {(n["codigo"], n["nombre"], n["semestre"]) for n in j["nodos"]} == {
        ("MAT-00001", "ALGEBRA", 1), ("MAT-00002", "CALCULO", 2), ("FIS-00001", "FISICA", 2)}
    assert j["aristas"] == [{"desde": "MAT-00001", "hacia": "MAT-00002"}]           # the practicum is beyond semester 4
    assert "persona" not in " ".join(j.keys()) and "episodio" not in " ".join(j.keys())
    auto = get(api, "/modelos/malla-ejemplo").json()
    assert auto["cod_programa"] == "C101"                                            # the program with the most edges
    assert get(api, "/modelos/malla-ejemplo", cod_programa="NOEXISTE").json()["nodos"] == []
    assert get(api, "/modelos/malla-ejemplo", semestre_max=9).status_code == 422


def test_models_summary_reports_when_it_was_not_exported(api, mundo):
    mundo.execute(f"DELETE FROM {T}.resumen_modelos_construccion")
    try:
        j = get(api, "/modelos/resumen").json()
        assert j["disponible"] is False and j["modelos"] == [] and "predicciones" in j["aviso"]
    finally:
        mundo.execute(f"INSERT INTO {T}.resumen_modelos_construccion (id, filas) VALUES (1, 6)")


# --------------------------------------------------------------------------- #
# Models: per-task pages (T1-T6), aggregates only
# --------------------------------------------------------------------------- #
def test_task_cards_headline_the_kept_model_against_its_baseline(api):
    j = get(api, "/modelos/tareas").json()
    assert j["disponible"] is True and "predicciones individuales no están habilitadas" in j["aviso"]
    assert [t["tarea"] for t in j["tareas"]] == ["t1", "t4"]
    t1 = j["tareas"][0]
    assert t1["estado"] == "completo" and t1["estado_etiqueta"] == "Benchmark completo" and t1["corte_k"] == 1
    assert t1["conservado"]["nombre"] == "CatBoost (ingreso + agregados)"
    assert t1["conservado"]["metrica"] == {"valor": pytest.approx(0.36), "ic_inf": pytest.approx(0.33), "ic_sup": pytest.approx(0.39)}
    assert t1["referencia"]["nombre"] == "Tasa histórica del programa" and t1["referencia"]["metrica"]["valor"] == pytest.approx(0.07)
    assert t1["metrica"] == "ap" and t1["veredicto_redes"] == "Las redes no agregan señal."
    assert t1["n_prueba"] == 4934 and t1["tasa_prueba"] == pytest.approx(0.0567)


def test_task_cards_report_when_the_summary_was_not_exported(api, mundo):
    mundo.execute(f"CREATE TEMP TABLE respaldo AS SELECT * FROM {T}.resumen_tarea")
    mundo.execute(f"DELETE FROM {T}.resumen_tarea")
    try:
        j = get(api, "/modelos/tareas").json()
        assert j["disponible"] is False and j["tareas"] == [] and "predicciones" in j["aviso"]
        assert get(api, "/modelos/tarea/t1").status_code == 404
    finally:
        mundo.execute(f"INSERT INTO {T}.resumen_tarea SELECT * FROM respaldo")
        mundo.execute("DROP TABLE respaldo")


def test_task_detail_has_views_splits_ladder_comparisons_notes_and_calibration(api):
    j = get(api, "/modelos/tarea/t1").json()
    assert j["tarea"]["pregunta"] == "¿Sigue matriculada?" and j["tarea"]["evento"] == "no continuidad observada"
    assert [(v["variante"], v["corte_k"], v["principal"]) for v in j["vistas"]] == [("base", 1, True), ("base", 2, False)]
    assert j["vistas"][0]["pronostico_agregado"] == "descriptivo" and j["vistas"][0]["conservado_modelo"] == "cb_acad"
    assert {(p["particion"], p["n"], p["eventos"]) for p in j["particiones"]} == {("train", 12000, 750), ("test", 4934, 280)}
    modelos = {m["modelo"]: m for m in j["modelos"]}
    assert set(modelos) == {"baseline_tasa", "cb_acad", "gru_seq"} and modelos["cb_acad"]["conservado"] is True
    assert modelos["cb_acad"]["metricas"]["ap"]["valor"] == pytest.approx(0.36) and modelos["gru_seq"]["escalon"] == 3
    assert [(c["modelo_a"], c["modelo_b"], c["veredicto"]) for c in j["comparaciones"]] == [("gru_seq", "cb_acad", "empeora")]
    assert [n["tipo"] for n in j["notas"]] == ["dato", "limite"] and j["notas"][0]["texto"].startswith("P58")
    assert [(c["decil"], c["n"]) for c in j["calibracion"]] == [(1, 494), (2, 494)]
    assert [c["pocos_casos"] for c in j["calibracion"]] == [False, False]
    assert get(api, "/modelos/tarea/t4").json()["vistas"][0]["pronostico_agregado"] == "no_confiable"


def test_task_detail_rejects_unknown_tasks_and_missing_data(api):
    assert get(api, "/modelos/tarea/t9").status_code == 422
    assert get(api, "/modelos/tarea/uno").status_code == 422
    assert get(api, "/modelos/tarea/t3").status_code == 404                 # valid task, nothing exported for it


def test_group_tables_serve_names_expected_versus_observed_and_the_group_summary(api):
    j = get(api, "/modelos/tarea/t1/grupos", nivel="programa", variante="base", corte=1).json()
    assert j["tarea"] == "t1" and j["nivel"] == "programa" and j["pronostico_agregado"] == "descriptivo"
    grupos = {g["grupo"]: g for g in j["grupos"]}
    assert set(grupos) == {"C101", "C102"}
    assert grupos["C101"]["nombre"] == "ARQUITECTURA" and grupos["C101"]["facultad"] == "Escuela de Arquitectura"
    assert grupos["C101"]["observada"] == pytest.approx(0.116) and grupos["C101"]["esperada"] == pytest.approx(0.1)
    assert grupos["C101"]["pocos_casos"] is False
    assert {k: grupos["C101"][k] for k in ("ap_lo", "ap_hi", "auc_lo", "auc_hi", "tasa_lo", "tasa_hi", "esperado_lo", "esperado_hi")} == {
        "ap_lo": 0.3, "ap_hi": 0.5, "auc_lo": 0.8, "auc_hi": 0.9, "tasa_lo": 0.07, "tasa_hi": 0.17, "esperado_lo": 0.08, "esperado_hi": 0.12}
    assert j["resumen"][0]["grupos_total"] == 2
    for retirado in ("grupos_reportables", "grupos_suprimidos", "n_min", "eventos_min"):
        assert retirado not in j["resumen"][0]
    assert not any("n >= 10" in n or "ocult" in n.lower() for n in j["notas"]) and any("pocos casos" in n for n in j["notas"])


def test_group_tables_default_to_the_principal_view_and_filter_by_level(api):
    j = get(api, "/modelos/tarea/t4/grupos", nivel="facultad").json()
    assert j["variante"] == "base" and j["corte_k"] == 2 and j["pronostico_agregado"] == "no_confiable"
    assert [g["nombre"] for g in j["grupos"]] == ["Facultad de Ciencias"]
    assert get(api, "/modelos/tarea/t4/grupos", nivel="programa").json()["grupos"] == []
    for nivel in ("sexo", "via", "tipo_colegio"):                              # Task 5 levels (migration 034)
        assert get(api, "/modelos/tarea/t4/grupos", nivel=nivel).status_code == 200
    assert get(api, "/modelos/tarea/t1/grupos", nivel="persona").status_code == 422
    assert get(api, "/modelos/tarea/t1/grupos").status_code == 422          # the level is required
    assert get(api, "/modelos/tarea/t1/grupos", nivel="programa", variante="Base;--").status_code == 422


def _grupo_extra(mundo, tarea, grupo, n, eventos, nivel="programa", corte=1, ap=None, roc=None, nombre=None):
    obs = "NULL" if eventos is None or n == 0 else eventos / n
    mundo.execute(f"INSERT INTO {T}.resumen_tarea_grupo (tarea, variante, corte_k, nivel, categoria, grupo, nombre, n, eventos, "
                  f"observada, esperada, ap, roc_auc, pocos_casos) VALUES ('{tarea}', 'base', {corte}, '{nivel}', '', '{grupo}', "
                  f"'{nombre or grupo}', {n}, {'NULL' if eventos is None else eventos}, {obs}, 0.2, "
                  f"{'NULL' if ap is None else ap}, {'NULL' if roc is None else roc}, {n < 10})")


def test_small_groups_are_served_with_pocos_casos_true(api, mundo):
    _grupo_extra(mundo, "t1", "C104", 150, None, nombre="CHICO")           # events unknown
    _grupo_extra(mundo, "t1", "C105", 3, 1, ap=0.9, roc=0.8)               # 3 people, 1 event
    _grupo_extra(mundo, "t1", "C106", 9, 0)                                # no events at all
    _grupo_extra(mundo, "t1", "C107", 0, 0)                                # empty group: no divide by zero
    try:
        j = get(api, "/modelos/tarea/t1/grupos", nivel="programa", variante="base", corte=1).json()
        g = {x["grupo"]: x for x in j["grupos"]}
        assert set(g) == {"C101", "C102", "C104", "C105", "C106", "C107"}
        assert g["C101"]["pocos_casos"] is False and g["C104"]["pocos_casos"] is False
        assert [g[k]["pocos_casos"] for k in ("C105", "C106", "C107")] == [True, True, True]
        assert g["C105"]["n"] == 3 and g["C105"]["eventos"] == 1 and g["C105"]["ap"] == 0.9 and g["C105"]["roc_auc"] == 0.8   # as stored
        assert g["C106"]["eventos"] == 0
        assert "confianza" not in g["C105"]
    finally:
        mundo.execute(f"DELETE FROM {T}.resumen_tarea_grupo WHERE grupo IN ('C104','C105','C106','C107')")


def test_groups_of_every_task_and_level_are_served_as_stored(api, mundo):
    mundo.execute(f"INSERT INTO {T}.resumen_tarea (tarea, orden, nombre, pregunta, poblacion, evento, estado, estado_etiqueta, "
                  f"veredicto_redes, metrica_titular, metrica_secundaria) VALUES ('t3', 3, 'T3 · Tiempo a egreso', '¿Cuándo egresa?', "
                  f"'Episodios.', 'egreso', 'completo', 'Benchmark completo', 'Aportan.', 'c_index', 'ibs')")
    mundo.execute(f"INSERT INTO {T}.resumen_tarea_vista (tarea, variante, corte_k, etiqueta, principal, conservado_modelo, "
                  f"referencia_modelo, metrica_titular, metrica_secundaria, concluyente, pronostico_agregado, nota) VALUES "
                  f"('t3', 'base', 2, '', true, 'nn_gru', 'km_programa', 'c_index', 'ibs', true, 'descriptivo', NULL)")
    for grupo, n, ev in (("C301", 75, 5), ("C303", 300, 80), ("C304", 40, 0)):
        _grupo_extra(mundo, "t3", grupo, n, ev, corte=2, ap=0.5, roc=0.7)
    _grupo_extra(mundo, "t3", "mujer", 4, 2, nivel="sexo", corte=2)
    try:
        j = get(api, "/modelos/tarea/t3/grupos", nivel="programa").json()
        g = {x["grupo"]: x for x in j["grupos"]}
        assert set(g) == {"C301", "C303", "C304"}
        assert all(x["ap"] == 0.5 and x["roc_auc"] == 0.7 and "confianza" not in x for x in g.values())    # no n >= 100 rule
        assert not any("confianza" in x for x in j["notas"])
        assert [x["pocos_casos"] for x in get(api, "/modelos/tarea/t3/grupos", nivel="sexo").json()["grupos"]] == [True]
    finally:
        mundo.execute(f"DELETE FROM {T}.resumen_tarea_grupo WHERE grupo IN ('C301','C303','C304','mujer')")
        mundo.execute(f"DELETE FROM {T}.resumen_tarea_vista WHERE tarea = 't3'")
        mundo.execute(f"DELETE FROM {T}.resumen_tarea WHERE tarea = 't3'")


def test_t6_group_rows_note_says_validation_and_test_units(api, mundo):
    mundo.execute(f"INSERT INTO {T}.resumen_tarea (tarea, orden, nombre, pregunta, poblacion, evento, estado, estado_etiqueta, "
                  f"veredicto_redes, metrica_titular, metrica_secundaria) VALUES ('t6', 6, 'T6 · Modelo', '¿Q?', 'P.', 'e', 'completo', "
                  f"'Benchmark completo', 'V.', 'ap', 'roc_auc')")
    mundo.execute(f"INSERT INTO {T}.resumen_tarea_vista (tarea, variante, corte_k, etiqueta, principal, conservado_modelo, "
                  f"referencia_modelo, metrica_titular, metrica_secundaria, concluyente, pronostico_agregado, nota) VALUES "
                  f"('t6', 'base', 1, '', true, 'm', 'r', 'ap', 'roc_auc', true, 'descriptivo', NULL)")
    try:
        t6 = get(api, "/modelos/tarea/t6/grupos", nivel="programa").json()["notas"]
        assert any("validación y de prueba" in n and "riesgo esperado" in n for n in t6)
        assert not any("validación y de prueba" in n for n in get(api, "/modelos/tarea/t1/grupos", nivel="programa").json()["notas"])
    finally:
        mundo.execute(f"DELETE FROM {T}.resumen_tarea_vista WHERE tarea = 't6'")
        mundo.execute(f"DELETE FROM {T}.resumen_tarea WHERE tarea = 't6'")


def test_task_responses_hold_no_person_level_data_or_individual_predictions(api):
    import re

    for path in ("/modelos/tareas", "/modelos/tarea/t1", "/modelos/tarea/t1/grupos?nivel=programa"):
        r = api.get(f"/neural{path}", headers=_h(LECTOR))
        assert r.status_code == 200
        assert not re.search(r"[0-9a-f]{64}", r.text)
        for prohibido in ("persona_key", "episodio_id", "y_pred", "probabilidad"):
            assert prohibido not in r.text.lower()


# --------------------------------------------------------------------------- #
# Privacy and read-only
# --------------------------------------------------------------------------- #
def test_no_response_exposes_ruts_names_or_teacher_keys(api):
    paths = ["/programas", "/programa/C101/cohortes", "/calidad", "/traslados/resumen", "/traslados/programa/T100",
             "/modelos/resumen", "/modelos/malla-ejemplo", "/modelos/tareas", "/modelos/tarea/t1", "/modelos/tarea/t4",
             "/modelos/tarea/t1/grupos?nivel=programa&corte=1", "/modelos/tarea/t4/grupos?nivel=facultad&corte=2"]
    for path in paths:
        text = get(api, path).text.lower()
        assert "docente" not in text and "rut" not in text.replace("rutina", "")
        assert "persona_key" not in text
        for rut in (rut_a(1), RUT_VIEWER, rut_b(1)):
            assert rut.split("-")[0].lower() not in text


def test_the_connection_is_read_only(api):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    engine = neural_db.get_engine()
    with engine.connect() as conn:
        assert conn.execute(text("SHOW transaction_read_only")).scalar() == "on"
        with pytest.raises(DBAPIError):
            conn.execute(text(f"INSERT INTO {T}.persona (persona_key) VALUES ('x')"))


def test_the_router_has_no_write_endpoints():
    paths = {p: set(ops) for p, ops in app.openapi()["paths"].items() if p.startswith("/neural")}
    # The only write is the confidentiality acceptance (it records who accepted, not data of the module).
    assert paths.pop("/neural/aceptacion") == {"get", "post"}
    assert all(ops == {"get"} for ops in paths.values())
    assert len(paths) == 12


def test_no_neural_route_is_about_a_person_or_an_episode():
    """Regression guard: this module serves aggregates only; person-level routes must not come back."""
    paths = [p for p in app.openapi()["paths"] if p.startswith("/neural")]
    assert paths
    assert not [p for p in paths if "persona" in p.lower() or "episodio" in p.lower()]


# --------------------------------------------------------------------------- #
# View "Lo que paso"
# --------------------------------------------------------------------------- #
def test_historico_serves_the_four_blocks_for_the_whole_ucn(api):
    j = get(api, "/historico").json()
    assert j["disponible"] is True and j["filtro"] == "Toda la UCN"
    assert j["filtros"] == ["Toda la UCN", "Facultad A", "Facultad Chica"] and j["cohortes"]["siguieron"] == [2022, 2023]
    assert j["semestres"]["n"] == 14880 and j["semestres"]["bajas"] == 7000 and len(j["semestres"]["filas"]) == 12
    assert j["siguieron"]["siguieron"] == 4654 and j["siguieron"]["esperados"] == pytest.approx(4676.5)
    assert [(p["facultad"], p["pocos_casos"]) for p in j["por_facultad"]] == [("Facultad A", False), ("Facultad Chica", False)]
    assert j["eliminados"]["anio_reglamento"] == 2025 and j["eliminados"]["clave"]["anio"] == 2024
    assert j["alcance"]["alcanzados"] == 157 and j["alcance"]["de_cada_10"] == 5.6 and len(j["alcance"]["curva"]) == 21
    assert "predicciones individuales no están habilitadas" in j["aviso"]


def test_historico_serves_small_years_and_causal_cells_as_stored(api):
    e = get(api, "/historico").json()["eliminados"]
    assert [a["anio"] for a in e["anios"]] == [2023, 2024, 2025]                    # 2025 has 7 eliminations: served
    assert [a["pocos_casos"] for a in e["anios"]] == [False, False, False]          # the mark follows each year's n
    assert [a["anio"] for a in e["totales"]] == [2024, 2025]
    por = {c["grupo"]: c for c in e["causales"]["filas"]}
    assert por["tercera"]["n"] == 3183 and por["egresado"]["n"] == 4 and por["otras"]["n"] == 7 and "otros" not in por
    assert sum(f["n"] for f in e["causales"]["filas"]) == e["causales"]["total"]


def test_historico_filters_by_faculty_and_serves_small_groups(api):
    a = get(api, "/historico", facultad="Facultad A").json()
    assert a["filtro"] == "Facultad A" and a["semestres"]["n"] == 900 and a["siguieron"] is None and a["alcance"] is None
    chica = get(api, "/historico", facultad="Facultad Chica").json()
    assert chica["semestres"]["n"] == 8 and chica["semestres"]["pocos_casos"] is True and chica["semestres"]["bajas"] == 3
    assert chica["siguieron"]["n"] == 60 and chica["siguieron"]["siguieron"] == 55 and chica["siguieron"]["pocos_casos"] is False
    assert chica["alcance"]["n"] == 60 and chica["alcance"]["eventos"] == 12 and chica["alcance"]["alcanzados"] == 6


def test_historico_unknown_faculty_is_404_and_input_is_validated(api):
    assert get(api, "/historico", facultad="NoExiste").status_code == 404
    assert get(api, "/historico", facultad="x" * 200).status_code == 422


def test_historico_has_no_person_level_data(api):
    r = get(api, "/historico")
    text = r.text.lower()
    for prohibido in ("persona_key", "episodio", "rut", "docente"):
        assert prohibido not in text
    import re
    assert not re.search(r"[0-9a-f]{64}", r.text)


def test_historico_reports_when_it_was_not_exported(api, mundo):
    mundo.execute(f"ALTER TABLE {T}.vista_historica RENAME TO vista_historica_x")
    try:
        assert get(api, "/historico").status_code == 503
    finally:
        mundo.execute(f"ALTER TABLE {T}.vista_historica_x RENAME TO vista_historica")
    mundo.execute(f"DELETE FROM {T}.vista_historica WHERE bloque = 'meta'")
    try:
        j = get(api, "/historico").json()
        assert j["disponible"] is False and j["semestres"] is None and j["filtros"] == ["Toda la UCN"]
    finally:
        mundo.execute(f"INSERT INTO {T}.vista_historica (bloque, facultad, contenido) VALUES ('meta', 'Toda la UCN', %s::jsonb)",
                      (json.dumps(META_HISTORICO),))


# --------------------------------------------------------------------------- #
# View "Lo que paso" by topics (new blocks)
# --------------------------------------------------------------------------- #
def test_historico_serves_the_new_blocks(api):
    j = get(api, "/historico").json()
    assert j["perfil_ingreso"]["n"] == 4934 and j["perfil_ingreso"]["nota_asociacion"] is True
    assert j["primer_semestre"]["filas"][0] == {"reprobaciones": "0", "n": 3000, "pct_siguieron": pytest.approx(0.96), "pocos_casos": False}
    assert [f["codigo"] for f in j["ramos_reprobados"]["por_tasa"]] == ["CALC1", "X1", "X2"] and j["ramos_reprobados"]["desde"] == "202110"
    assert j["ramos_reprobados"]["por_tasa"][0]["lo"] == 0.35 and j["ramos_reprobados"]["por_tasa"][0]["hi"] == 0.45
    ventana = j["ramos_esperado"]["ventanas"]["prueba"]
    assert [r["codigo"] for r in ventana["ramos"]] == ["CALC1", "CHICO"] and ventana["deptos"][0]["depto_desc"] == "Matemática"
    assert [f["codigo"] for f in j["cuellos_botella"]["filas"]] == ["CALC1", "X9"] and j["cuellos_botella"]["filas"][0]["impacto"] == 2400
    assert [f["semestre"] for f in j["semestre_malla"]["filas"]] == [1, 2, 3, 4]
    assert j["tiempo_egreso"]["filas"][0]["pct_a_tiempo"] == pytest.approx(0.3)
    assert [f["cod_programa"] for f in j["tiempo_egreso"]["filas"]] == ["P1", "P3"]
    assert j["senales"]["tareas"][0]["senales"][0]["peso_pct"] == 40.5 and len(j["senales"]["tareas"]) == 2
    assert j["esperar_semestre"]["comparaciones"][0]["de_cada_10_despues"] == 6.1
    # the model blocks keep the UCN content under a faculty filter; the population blocks do not exist there
    a = get(api, "/historico", facultad="Facultad A").json()
    assert a["senales"]["tareas"][0]["senales"][0]["peso_pct"] == 40.5 and a["esperar_semestre"]["comparaciones"]
    assert a["perfil_ingreso"] is None
    assert [f["codigo"] for f in a["ramos_reprobados"]["por_tasa"]] == ["CALC1", "X1", "X2"]


def test_new_blocks_serve_small_cells_without_merging_or_hiding(api):
    j = get(api, "/historico").json()
    dims = {d["dimension"]: d for d in j["perfil_ingreso"]["dimensiones"]}
    assert set(dims) == {"via", "colegio"}
    via = {f["grupo"]: f for f in dims["via"]["filas"]}
    assert set(via) == {"regular", "especial", "cambio", "otra"} and "otros" not in via
    assert via["otra"]["n"] == 6 and via["otra"]["pocos_casos"] is True and via["regular"]["pocos_casos"] is False
    assert via["cambio"]["pct_siguieron"] == pytest.approx(0.75)
    malla = {f["semestre"]: f for f in j["semestre_malla"]["filas"]}
    assert malla[2]["reprobados"] == 7 and malla[2]["tasa"] == pytest.approx(0.00175) and malla[3]["intentos"] == 6
    filas = {f["cod_programa"]: f for f in j["causales_programa"]["filas"] if f["cod_programa"]}
    assert [c["n"] for c in filas["P1"]["causales"]] == [250, 50]
    assert [c["n"] for c in filas["P2"]["causales"]] == [195, 5]
    assert filas["P3"]["total"] == 6 and filas["P3"]["pocos_casos"] is True and filas["P4"]["total"] == 5
    t = {f["cod_programa"]: f for f in j["tiempo_egreso"]["filas"]}
    assert t["P1"]["pct_mas_1"] == pytest.approx(0.96) and t["P3"]["n"] == 6 and t["P3"]["pocos_casos"] is True
    chica = get(api, "/historico", facultad="Facultad Chica").json()
    assert chica["perfil_ingreso"]["n"] == 8 and chica["primer_semestre"]["filas"][0]["n"] == 8
    assert chica["ramos_reprobados"]["por_tasa"][0]["intentos"] == 8 and chica["cuellos_botella"]["filas"][0]["reprobados"] == 6
    assert chica["semestre_malla"]["filas"][0]["reprobados"] == 2 and chica["causales_programa"]["filas"][0]["total"] == 6
    assert chica["tiempo_egreso"]["filas"][0]["n"] == 6
    for bloque in ("senales", "esperar_semestre"):                       # they describe the model: the UCN content
        assert chica[bloque]["aplica_a_poblacion"] is False, bloque


def test_esperado_has_no_section_or_teacher_fields(api):
    r = get(api, "/historico")
    ramo = r.json()["ramos_esperado"]["ventanas"]["prueba"]["ramos"][0]
    assert set(ramo) == {"codigo", "nombre", "intentos", "observados", "esperados", "diferencia", "lo", "hi"}   # no nrc, section or teacher
    for prohibido in ("nrc", "seccion", "docente", "profesor", "fulano", "s-77"):
        assert prohibido not in r.text.lower()


# --------------------------------------------------------------------------- #
# Tab "Lo que viene"
# --------------------------------------------------------------------------- #
def test_proyeccion_serves_four_blocks_with_ranges_and_cut(api):
    j = get(api, "/proyeccion").json()
    assert j["disponible"] is True and j["filtro"] == "Toda la UCN" and j["corte"] == "202610"
    assert j["filtros"] == ["Toda la UCN", "Facultad A", "Facultad Chica"] and j["sin_proyeccion"] == {"n": 5324}
    c = j["continuidad"]
    assert c["n"] == 4000 and c["lo"] < c["esperados"] < c["hi"]
    assert all(e["corte"] == "202610" and e["horizonte"] == "202620" for e in c["por_cohorte"])
    e = j["eliminacion"]
    assert e["orientativo"] is True and e["periodo_observado"] == "202610" and e["lo"] < e["esperados"] < e["hi"]
    g = j["egreso"]
    assert g["nominal"]["lo"] < g["nominal"]["esperados"] < g["nominal"]["hi"] and g["nominal_mas_2"] is None
    assert g["por_cohorte"][0]["nominal"]["desde"] == "202620"
    assert j["umbral"]["nota_p58"] is True and j["umbral"]["lejos"] == 3493
    assert "Art. 46" in " ".join(j["notas"]) and "subregistro" in " ".join(j["notas"])
    assert "predicciones individuales no están habilitadas" in j["aviso"]


def test_proyeccion_filters_by_faculty_and_serves_small_groups(api):
    j = get(api, "/proyeccion").json()
    por = j["continuidad"]["por_cohorte"]
    assert [(x["cohorte"], x["n"], x["pocos_casos"]) for x in por] == [(2026, 3000, False), (2025, 990, False), (2024, 6, True)]
    assert por[2]["k"] == 1 and por[2]["corte"] == "202610" and por[0]["sin_historial_beneficios"] == 4
    assert j["eliminacion"]["observados_hasta_hoy"] == 7
    assert j["egreso"]["ya_pasado_nominal"] == 5 and j["egreso"]["ya_pasado_nominal_mas_2"] == 40
    u = j["umbral"]                                               # the four categories are always there
    assert (u["en_umbral"], u["a_1"], u["a_2"], u["lejos"]) == (300, 200, 7, 3493) and "otros" not in u
    a = get(api, "/proyeccion", facultad="Facultad A").json()
    assert a["filtro"] == "Facultad A" and a["continuidad"]["n"] == 500 and a["umbral"]["a_2"] == 50 and a["eliminacion"] is None
    chica = get(api, "/proyeccion", facultad="Facultad Chica").json()
    assert chica["disponible"] is True
    assert chica["continuidad"]["n"] == 8 and chica["continuidad"]["pocos_casos"] is True
    assert chica["continuidad"]["por_cohorte"][0]["sin_historial_beneficios"] == 2
    assert chica["eliminacion"]["observados_hasta_hoy"] == 0 and chica["egreso"]["ya_pasado_nominal"] == 3
    assert chica["egreso"]["nominal"]["esperados"] == 100.0
    assert (chica["umbral"]["en_umbral"], chica["umbral"]["a_1"], chica["umbral"]["a_2"], chica["umbral"]["lejos"]) == (1, 2, 3, 2)


def test_proyeccion_unknown_faculty_is_404_and_missing_table_is_503(api, mundo):
    assert get(api, "/proyeccion", facultad="NoExiste").status_code == 404
    assert get(api, "/proyeccion", facultad="x" * 200).status_code == 422
    mundo.execute(f"ALTER TABLE {T}.vista_proyeccion RENAME TO vista_proyeccion_x")
    try:
        assert get(api, "/proyeccion").status_code == 503
    finally:
        mundo.execute(f"ALTER TABLE {T}.vista_proyeccion_x RENAME TO vista_proyeccion")
    mundo.execute(f"DELETE FROM {T}.vista_proyeccion WHERE bloque = 'meta'")
    try:
        j = get(api, "/proyeccion").json()
        assert j["disponible"] is False and j["continuidad"] is None and j["filtros"] == ["Toda la UCN"]
    finally:
        mundo.execute(f"INSERT INTO {T}.vista_proyeccion (bloque, facultad, contenido) VALUES ('meta', 'Toda la UCN', %s::jsonb)",
                      (json.dumps(META_PROYECCION),))


def test_proyeccion_has_no_person_level_data(api):
    r = get(api, "/proyeccion")
    for prohibido in ("persona_key", "episodio", "rut", "docente", "nrc"):
        assert prohibido not in r.text.lower()
    import re
    assert not re.search(r"[0-9a-f]{64}", r.text)


# --------------------------------------------------------------------------- #
# No suppression anywhere (Task 6): the API serves the marts as stored
# --------------------------------------------------------------------------- #
RETIRADOS = {"suprimido", "suprimido_promedio", "total_suprimido", "n_min", "eventos_min", "grupos_suprimidos", "grupos_reportables",
             "otros_flujos", "confianza"}


def _claves(valor, acumulado=None):
    acumulado = set() if acumulado is None else acumulado
    if isinstance(valor, dict):
        for k, v in valor.items():
            acumulado.add(k)
            _claves(v, acumulado)
    elif isinstance(valor, list):
        for v in valor:
            _claves(v, acumulado)
    return acumulado


def _nulos_de_conteo(valor, ruta="$"):
    """Paths of ``n`` / count keys that are null (what a size rule used to leave)."""
    if isinstance(valor, dict):
        for k, v in valor.items():
            if v is None and (k == "n" or k.startswith("n_") and k not in ("n_retencion_obs", "n_retenidos", "n_prueba", "n_evaluacion")):
                yield f"{ruta}.{k}"
            yield from _nulos_de_conteo(v, f"{ruta}.{k}")
    elif isinstance(valor, list):
        for i, v in enumerate(valor):
            yield from _nulos_de_conteo(v, f"{ruta}[{i}]")


def test_no_route_returns_size_suppressed_nulls(api):
    """The 3-person cohort, the 3-person transfer group and the 8-person faculty are in the data: every route that
    carries them serves their counts, and no response carries a suppression key or a null count."""
    rutas = [("/programas", {}), ("/programa/C101/cohortes", {}), ("/calidad", {}), ("/traslados/resumen", {}),
             ("/traslados/programa/T100", {}), ("/traslados/programa/T300", {}), ("/modelos/resumen", {}), ("/modelos/malla-ejemplo", {}),
             ("/modelos/tareas", {}), ("/modelos/tarea/t1", {}), ("/modelos/tarea/t1/grupos", {"nivel": "programa"}),
             ("/modelos/tarea/t4/grupos", {"nivel": "facultad"}), ("/historico", {}), ("/historico", {"facultad": "Facultad A"}),
             ("/historico", {"facultad": "Facultad Chica"}), ("/proyeccion", {}), ("/proyeccion", {"facultad": "Facultad A"}),
             ("/proyeccion", {"facultad": "Facultad Chica"})]
    for ruta, params in rutas:
        r = get(api, ruta, **params)
        assert r.status_code == 200, (ruta, params, r.text)
        j = r.json()
        assert not (_claves(j) & RETIRADOS), (ruta, params, _claves(j) & RETIRADOS)
        assert not list(_nulos_de_conteo(j)), (ruta, params, list(_nulos_de_conteo(j)))
        assert "n >= 10" not in r.text and "ocult" not in r.text.lower() and "suprim" not in r.text.lower(), (ruta, params)
    chica = get(api, "/proyeccion", facultad="Facultad Chica").json()
    assert chica["umbral"]["a_2"] == 3 and chica["continuidad"]["n"] == 8
    assert get(api, "/traslados/programa/T300").json()["balance"]["ganados_total"] == 3


def _documento_antiguo():
    """Shape of the export before the suppression was lifted: null cells, «otros» rows, ``n_min`` and the ``otros`` bucket."""
    cohorte = {"cohorte": "otros", "k": None, "modelo": None, "corte": None, "horizonte": None, "n": 40, "esperados": 30.0, "lo": 25.0, "hi": 35.0}
    base = {"n": 400, "esperados": 380.0, "lo": 370.0, "hi": 390.0, "por_cohorte": [_entrada(2026, 300, 280.0, 270.0, 290.0), cohorte]}
    return [
        ("semestres", {**_fila_semestres(400, 40, 30), "bajas": None, "pct_bajas": None, "bajas_primer_anio": None,
                       "pct_bajas_primer_anio": None,
                       "filas": [{"semestre": 1, "dejan": None, "eliminados": None, "pct_dejan": None, "pct_eliminados": None}]}),
        ("perfil_ingreso", {"n": 400, "nota_asociacion": True, "dimensiones": [{"dimension": "via", "filas": [
            {"grupo": "regular", "etiqueta": "Ingreso regular", "n": 350, "pct_siguieron": 0.9, "pct_esperado": 0.9},
            {"grupo": "otros", "etiqueta": "Otros", "n": 50}]}]}),
        ("primer_semestre", {"n": 400, "nota_asociacion": True, "filas": [{"reprobaciones": "otros", "n": 20}]}),
        ("causales_programa", {"desde": "201610", "hasta": "202520", "nivel": "programa", "filas": [
            {"cod_programa": None, "programa": "otros programas", "total": 30, "causales": None}]}),
        ("semestre_malla", {"filas": [{"semestre": 1, "intentos": 100, "reprobados": None, "tasa": None}]}),
        ("tiempo_egreso", {"regla_duracion": "x", "filas": [{"cod_programa": "P1", "programa": "Uno", "n": 50, "duracion_nominal_sem": 10,
                                                              "pct_a_tiempo": None, "pct_mas_1": None, "pct_mas_2": None}]}),
        ("continuidad", base), ("eliminacion", {**base, "observados_hasta_hoy": None, "periodo_observado": "202610", "orientativo": True}),
        ("egreso", {"n": 300, "regla": "x", "nominal": None, "nominal_mas_2": None, "ya_pasado_nominal": None, "por_cohorte": [
            {"cohorte": "otros", "k": None, "modelo": None, "corte": None, "horizonte": None, "n": 40, "nominal": None, "nominal_mas_2": None}]}),
        ("umbral", {"n": 400, "en_umbral": 300, "a_1": None, "a_2": None, "lejos": 80, "otros": {"n": 20, "categorias": ["a_1", "a_2"]},
                    "nota_p58": True}),
    ]


def test_old_suppressed_document_still_serves(api, mundo):
    antigua = "Facultad Antigua"
    meta_h = {**META_HISTORICO, "n_min": 10, "filtros": META_HISTORICO["filtros"] + [antigua]}
    meta_p = {**META_PROYECCION, "n_min": 10, "filtros": META_PROYECCION["filtros"] + [antigua]}
    docs = _documento_antiguo()
    mundo.execute(f"UPDATE {T}.vista_historica SET contenido = %s::jsonb WHERE bloque = 'meta'", (json.dumps(meta_h),))
    mundo.execute(f"UPDATE {T}.vista_proyeccion SET contenido = %s::jsonb WHERE bloque = 'meta'", (json.dumps(meta_p),))
    for bloque, contenido in docs:
        tabla = "vista_proyeccion" if bloque in ("continuidad", "eliminacion", "egreso", "umbral") else "vista_historica"
        mundo.execute(f"INSERT INTO {T}.{tabla} (bloque, facultad, contenido) VALUES (%s, %s, %s::jsonb)", (bloque, antigua, json.dumps(contenido)))
    try:
        h = get(api, "/historico", facultad=antigua)
        assert h.status_code == 200, h.text
        h = h.json()
        assert h["semestres"]["filas"][0]["dejan"] is None and h["semestres"]["bajas"] is None
        assert [f["grupo"] for f in h["perfil_ingreso"]["dimensiones"][0]["filas"]] == ["regular", "otros"]
        assert h["primer_semestre"]["filas"][0]["reprobaciones"] == "otros"
        assert h["causales_programa"]["filas"][0]["programa"] == "otros programas"
        assert h["semestre_malla"]["filas"][0]["reprobados"] is None and h["tiempo_egreso"]["filas"][0]["pct_a_tiempo"] is None
        p = get(api, "/proyeccion", facultad=antigua)
        assert p.status_code == 200, p.text
        p = p.json()
        assert [e["cohorte"] for e in p["continuidad"]["por_cohorte"]] == [2026, "otros"] and p["continuidad"]["por_cohorte"][1]["k"] is None
        assert p["eliminacion"]["observados_hasta_hoy"] is None and p["egreso"]["por_cohorte"][0]["nominal"] is None
        assert (p["umbral"]["en_umbral"], p["umbral"]["a_1"], p["umbral"]["lejos"]) == (300, None, 80) and "otros" not in p["umbral"]
        for ruta in ("/historico", "/proyeccion"):
            assert get(api, ruta).status_code == 200
    finally:
        mundo.execute(f"DELETE FROM {T}.vista_historica WHERE facultad = %s", (antigua,))
        mundo.execute(f"DELETE FROM {T}.vista_proyeccion WHERE facultad = %s", (antigua,))
        mundo.execute(f"UPDATE {T}.vista_historica SET contenido = %s::jsonb WHERE bloque = 'meta'", (json.dumps(META_HISTORICO),))
        mundo.execute(f"UPDATE {T}.vista_proyeccion SET contenido = %s::jsonb WHERE bloque = 'meta'", (json.dumps(META_PROYECCION),))


# --------------------------------------------------------------------------- #
# Program filter and model metadata (Task 9)
# --------------------------------------------------------------------------- #
def test_historico_and_proyeccion_filter_by_program(api):
    h = get(api, "/historico", programa="P1").json()
    assert h["filtro"] == "P1" and h["programa"] == {"codigo": "P1", "nombre": "Programa Uno", "facultad": "Facultad A"}
    assert h["semestres"]["n"] == 120 and h["siguieron"]["n"] == 70 and h["alcance"] is None           # absent block: no data
    p = get(api, "/proyeccion", programa="P1").json()
    assert p["filtro"] == "P1" and p["programa"]["nombre"] == "Programa Uno"
    assert p["continuidad"]["n"] == 70 and p["umbral"]["a_2"] == 5 and p["eliminacion"] is None
    # a small program is served with its mark, never hidden
    assert get(api, "/historico", programa="P9").json()["semestres"]["pocos_casos"] is True
    assert get(api, "/proyeccion", programa="P9").json()["continuidad"]["pocos_casos"] is True
    # a faculty keeps answering as before, with no program echoed
    a = get(api, "/historico", facultad="Facultad A").json()
    assert a["filtro"] == "Facultad A" and a["programa"] is None and a["semestres"]["n"] == 900
    # a known program without a given block is «sin datos», not a 404 (PSD is in the list and has no document)
    for ruta in ("/historico", "/proyeccion"):
        r = get(api, ruta, programa="PSD") if ruta == "/historico" else get(api, ruta, programa="P2")
        assert r.status_code == 200 and r.json()["disponible"] is True
    sd = get(api, "/historico", programa="PSD").json()
    assert sd["semestres"] is None and sd["siguieron"] is None and sd["eliminados"] is None and sd["tiempo_egreso"] is None
    # the model blocks keep the UCN content under a program, flagged as not about the population
    assert sd["senales"]["aplica_a_poblacion"] is False and sd["esperar_semestre"]["aplica_a_poblacion"] is False
    assert sd["senales"]["tareas"][0]["senales"][0]["peso_pct"] == 40.5


def test_faculty_and_program_together_is_422(api):
    for ruta in ("/historico", "/proyeccion"):
        r = get(api, ruta, facultad="Facultad A", programa="P1")
        assert r.status_code == 422, (ruta, r.text)
        assert get(api, ruta, programa="x" * 40).status_code == 422                    # input is validated
        assert get(api, ruta, programa="no valido!").status_code == 422


def test_unknown_program_is_404(api):
    for ruta in ("/historico", "/proyeccion"):
        assert get(api, ruta, programa="NOEXISTE").status_code == 404
    assert get(api, "/proyeccion", programa="PSD").status_code == 404                  # in /historico's list, not in this view's
    assert get(api, "/historico", facultad="NoExiste").status_code == 404              # the faculty behaviour is unchanged


def test_filters_list_programs_under_their_faculty(api):
    for ruta in ("/historico", "/proyeccion"):
        j = get(api, ruta).json()
        assert j["filtros"] == ["Toda la UCN", "Facultad A", "Facultad Chica"]           # the flat list is unchanged
        jer = j["jerarquia"]
        assert [f["facultad"] for f in jer] == j["filtros"] and jer[0]["programas"] == []
        por = {f["facultad"]: [(x["codigo"], x["nombre"]) for x in f["programas"]] for f in jer}
        assert por["Facultad Chica"] == [("P9", "Programa Chico")]
        assert por["Facultad A"][0] == ("P1", "Programa Uno") and ("P2", "Programa Dos") in por["Facultad A"]
    assert ("PSD", "Programa Sin Datos") in {(x["codigo"], x["nombre"]) for f in get(api, "/historico").json()["jerarquia"] for x in f["programas"]}
    assert all("facultad" not in x for f in get(api, "/historico").json()["jerarquia"] for x in f["programas"])


def test_blocks_expose_model_metadata(api):
    h = get(api, "/historico").json()
    assert h["siguieron"]["modelo"] == MODELO_T1 and h["alcance"]["modelo"]["modelo_nombre"] == "CatBoost (ingreso + agregados)"
    assert h["ramos_esperado"]["modelo"]["tarea"] == "T2"
    assert h["semestres"]["modelo"] is None and h["semestres"]["modelos"] is None        # observed data, no model
    assert h["senales"]["aplica_a_poblacion"] is False and h["senales"]["modelo"] is None
    assert [m["tarea"] for m in h["senales"]["modelos"]] == ["T1", "T2"] and h["esperar_semestre"]["aplica_a_poblacion"] is False
    assert h["modelos"]["por_facultad"]["tarea"] == "T1" and h["modelos"]["semestres"] is None
    p = get(api, "/proyeccion").json()
    assert p["umbral"]["modelo"]["tipo"] == "proyeccion"
    assert p["continuidad"]["modelo"] is None and [m["modelo"] for m in p["continuidad"]["modelos"]] == ["cb_ben_pit", "gru_agg"]
    assert p["continuidad"]["por_cohorte"][0]["modelo"] == MODELO_PROY                     # a typed object per cohort
    assert p["egreso"]["por_cohorte"][0]["modelo"]["modelo"] == "gru_agg"


def test_a_legacy_string_model_is_served_without_label():
    from app.services.neural import schemas
    c = schemas.ProyCohorte(cohorte=2026, k=1, modelo="cb_ben_pit", n=10, esperados=1.0, lo=0.5, hi=1.5)
    assert c.modelo is None and c.pocos_casos is False and c.modelo_no_identificado is True
    assert schemas.ProyCohorteEgreso(cohorte=2026, modelo=MODELO_PROY_EGRESO, n=3).modelo.modelo == "gru_agg"
    otros = schemas.ProyCohorte(cohorte="otros", k=None, modelo=None, n=3, esperados=1.0, lo=0.5, hi=1.5)
    assert otros.modelo is None and otros.modelo_no_identificado is False                  # genuinely no model: not «unidentified»


def test_per_year_and_per_decile_rows_carry_the_pocos_casos_mark():
    """HistAnio and CalibracionTarea compute the mark from their own n with the shared threshold (rules.POCOS_CASOS)."""
    from app.services.neural import rules, schemas
    anio = dict(anio=2025, eliminados=1, tasa=0.1, parcial=True)
    assert schemas.HistAnio(n=rules.POCOS_CASOS - 1, **anio).pocos_casos is True
    assert schemas.HistAnio(n=rules.POCOS_CASOS, **anio).pocos_casos is False
    assert schemas.HistAnio(n=0, **anio).pocos_casos is True
    decil = dict(variante="v", corte_k=1, modelo="m", decil=1)
    assert schemas.CalibracionTarea(n=3, **decil).pocos_casos is True
    assert schemas.CalibracionTarea(n=494, **decil).pocos_casos is False


def test_legacy_or_malformed_model_is_never_a_500_nor_an_observed_label():
    """Review ruling: a model that cannot be read is «model not identified» (no label), never «Dato observado, sin modelo»."""
    from app.services.neural import schemas
    n = {"n": 20, "siguieron": 10, "esperados": 9.0, "pct_siguieron": 50.0, "pct_esperado": 45.0, "diferencia": 5.0}
    observado = schemas.HistSiguieron(**n)
    assert observado.modelo is None and observado.modelos is None and observado.modelo_no_identificado is False
    for malo in ("cb_acad", {"tarea": "T1"}, {"tarea": "T1", "k": "no-numero"}, 7, []):
        b = schemas.HistSiguieron(**n, modelo=malo)                                        # no ValidationError
        assert b.modelo is None and b.modelo_no_identificado is True
    mezcla = schemas.HistSiguieron(**n, modelos=[MODELO_T1, {"tarea": "T2"}, "cb_c_nuevas"])
    assert [m.tarea for m in mezcla.modelos] == ["T1"] and mezcla.modelo_no_identificado is True
    bien = schemas.HistSiguieron(**n, modelo=MODELO_T1)
    assert bien.modelo.modelo == "cb_acad" and bien.modelo_no_identificado is False
    vista = schemas.ProyeccionVista(disponible=True, filtro="Toda la UCN", filtros=["Toda la UCN"], aviso="", notas=[],
                                    modelos={"umbral": {"tarea": "T1"}, "continuidad": [MODELO_PROY, "cb"], "egreso": "gru_agg"})
    assert vista.modelos["umbral"] is None and vista.modelos["egreso"] is None and len(vista.modelos["continuidad"]) == 1


def test_a_malformed_model_in_a_stored_view_is_served_unlabelled(api, mundo):
    """The route answers 200 (not 500) on stored blocks whose model is a partial dict or a bare code, and labels neither."""
    def _contenido(bloque):
        return mundo.execute(f"SELECT contenido FROM {T}.vista_historica WHERE bloque = %s AND facultad = 'Toda la UCN'", (bloque,)).fetchone()[0]
    originales = {b: _contenido(b) for b in ("siguieron", "semestres")}
    try:
        for bloque, malo in (("siguieron", {"tarea": "T1"}), ("semestres", "cb_acad")):
            mundo.execute(f"UPDATE {T}.vista_historica SET contenido = %s::jsonb WHERE bloque = %s AND facultad = 'Toda la UCN'",
                          (json.dumps({**originales[bloque], "modelo": malo}), bloque))
        r = get(api, "/historico")
        assert r.status_code == 200, r.text
        h = r.json()
        for bloque in ("siguieron", "semestres"):
            assert h[bloque]["modelo"] is None and h[bloque]["modelo_no_identificado"] is True
    finally:
        for bloque, contenido in originales.items():
            mundo.execute(f"UPDATE {T}.vista_historica SET contenido = %s::jsonb WHERE bloque = %s AND facultad = 'Toda la UCN'",
                          (json.dumps(contenido), bloque))
    assert get(api, "/historico").json()["semestres"]["modelo_no_identificado"] is False


# --------------------------------------------------------------------------- #
# The real marts of the local dev database (read only): the live shapes must validate for every filter
# --------------------------------------------------------------------------- #
@pytest.fixture()
def api_real(monkeypatch):
    opciones = quote("-c search_path=neural_mart,neural_core,neural_meta", safe="")
    env = os.environ
    if not all(env.get(k) for k in ("DEV_HOST", "DEV_PORT", "DEV_DB", "DEV_USER", "DEV_PASSWORD")):
        pytest.skip("DEV_* environment variables not set: the real marts are not reachable")
    monkeypatch.setenv("NEURAL_DATABASE_URL", f"postgresql+psycopg://{quote(env['DEV_USER'], safe='')}:{quote(env['DEV_PASSWORD'], safe='')}"
                                              f"@{env['DEV_HOST']}:{env['DEV_PORT']}/{env['DEV_DB']}?options={opciones}")
    neural_db.reset()
    with dev_connection() as c:
        existentes = c.execute("SELECT to_regclass('neural_mart.vista_historica'), to_regclass('neural_mart.vista_proyeccion')").fetchone()
        if None in existentes:
            pytest.skip("neural_mart has no vista_historica / vista_proyeccion in this database")
    s = get_settings()
    monkeypatch.setattr(s, "app_env", "dev")
    monkeypatch.setattr(s, "boveda_database_url", "postgresql+psycopg://configurada-solo-en-test")
    repo = InMemoryAccessRepository()
    repo.add_module("neural", "DAI Neural")
    repo.grant_access("neural", LECTOR, "lector", by="test")
    repo.registrar_aceptacion("neural", LECTOR, aceptacion.VERSION)
    accesos.configure(repo)
    with TestClient(app) as client:
        yield client
    accesos.reset()
    neural_db.reset()


@pytest.mark.parametrize("ruta", ["/historico", "/proyeccion"])
def test_real_mart_documents_serve_for_every_filter(api_real, ruta):
    base = get(api_real, ruta)
    assert base.status_code == 200, base.text
    j = base.json()
    if not j["disponible"]:
        pytest.skip("the view is not exported in this database")
    assert len(j["filtros"]) > 1
    for filtro in j["filtros"]:
        r = get(api_real, ruta, facultad=filtro)
        assert r.status_code == 200, (filtro, r.text)
        assert not (_claves(r.json()) & RETIRADOS)
    for f in j["jerarquia"]:                                   # every program of the cascade validates too (blocks may be absent)
        for prog in f["programas"]:
            r = get(api_real, ruta, programa=prog["codigo"])
            assert r.status_code == 200, (prog, r.text)
            assert r.json()["programa"]["facultad"] == f["facultad"] and not (_claves(r.json()) & RETIRADOS)
