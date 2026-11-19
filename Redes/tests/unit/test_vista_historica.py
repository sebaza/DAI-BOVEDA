"""View "Lo que pasó": aggregation rules, causal grouping, exact counts for every group size, migration guard and exporter rows."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from evaluation import vista_historica as VH
from pipelines.marts import vista_historica as MV
from pipelines.migrate import validate_sql

SQL = Path(__file__).resolve().parents[2] / "sql" / "core" / "029_vista_historica.sql"


def test_causal_groups_follow_p117_and_unknown_codes_fall_in_otras():
    assert [VH.grupo_causal(c) for c in ("0B", "2B", "5B")] == ["tercera"] * 3
    assert [VH.grupo_causal(c) for c in ("0C", "2A", "5A")] == ["segunda"] * 3
    assert [VH.grupo_causal(c) for c in ("0D", "2D", "5I")] == ["no_inscribe"] * 3
    assert [VH.grupo_causal(c) for c in ("0A", "2C")] == ["avance"] * 2
    assert [VH.grupo_causal(c) for c in ("84", "5Z")] == ["egresado"] * 2
    assert [VH.grupo_causal(c) for c in ("0E", "0Z", "5D", "29", "xx", None, float("nan"))] == ["otras"] * 7


def _t3(n=200):
    rng = np.random.default_rng(0)
    causa = rng.choice([0, 1, 2], size=n, p=[0.3, 0.2, 0.5])
    return pd.DataFrame({"tiempo": rng.integers(1, 13, size=n), "causa": causa, "eliminado": causa == 2})


def test_semestres_counts_exits_by_semester_and_first_year_share():
    d = _t3()
    b = VH.bloque_semestres(d)
    sal = d[d["causa"] == 2]
    assert b["n"] == len(d) and b["bajas"] == len(sal)
    assert [f["semestre"] for f in b["filas"]] == list(range(1, 13))
    for f in b["filas"]:
        c = int(((sal["tiempo"] == f["semestre"]) & sal["eliminado"]).sum())
        assert f["eliminados"] == c
    assert b["pct_bajas_primer_anio"] == pytest.approx((sal["tiempo"] <= 2).mean())


def test_semestres_splits_leave_and_eliminated_and_ignores_other_causes():
    d = pd.DataFrame({"tiempo": [3] * 30, "causa": [2] * 20 + [1] * 5 + [0] * 5, "eliminado": [True] * 12 + [False] * 18})
    f = VH.bloque_semestres(d)["filas"][2]
    assert f["eliminados"] == 12
    assert f["dejan"] == 8 and f["pct_dejan"] == pytest.approx(8 / 30)        # 8 people leave: published exactly


def test_small_group_is_published_with_exact_counts():
    assert VH.bloque_semestres(_t3(9))["n"] == 9
    b = VH.bloque_siguieron(np.zeros(500, dtype=int), np.full(500, 0.1))             # no event: everybody continued
    assert b["siguieron"] == 500 and b["pct_siguieron"] == 1.0
    c = VH.curva_alcance(np.array([1] * 5 + [0] * 100), np.linspace(0, 1, 105))
    assert c["eventos"] == 5 and c["n"] == 105 and 0 <= c["alcanzados"] <= 5


def test_empty_group_is_not_published():
    vacio = pd.DataFrame({"tiempo": [], "causa": [], "eliminado": []})
    assert VH.bloque_semestres(vacio) is None
    assert VH.bloque_siguieron(np.array([], dtype=int), np.array([])) is None
    assert VH.curva_alcance(np.zeros(50, dtype=int), np.linspace(0, 1, 50)) is None          # no event: no share to reach
    assert VH.bloque_causales(pd.Series([], dtype=object)) is None


def test_siguieron_expected_is_n_minus_the_sum_of_probabilities():
    y = np.array([1] * 20 + [0] * 180)
    p = np.full(200, 0.15)
    b = VH.bloque_siguieron(y, p)
    assert b["siguieron"] == 180 and b["esperados"] == pytest.approx(170.0) and b["diferencia"] == pytest.approx(10.0)
    assert b["pct_siguieron"] == pytest.approx(0.9) and b["pct_esperado"] == pytest.approx(0.85)


def test_capture_curve_of_a_perfect_ranking_and_of_a_random_one():
    y = np.array([1] * 20 + [0] * 180)
    perfecto = VH.curva_alcance(y, y.astype(float))
    assert perfecto["alcanzados"] == 20 and perfecto["de_cada_10"] == 10.0 and perfecto["al_azar_de_cada_10"] == 1.0
    assert perfecto["curva"][0] == {"apoyados": 0.0, "alcanzados": 0.0} and perfecto["curva"][-1]["alcanzados"] == 1.0
    assert all(a["alcanzados"] <= b["alcanzados"] for a, b in zip(perfecto["curva"], perfecto["curva"][1:]))
    azar = VH.curva_alcance(y, np.random.default_rng(3).random(200))
    assert azar is None or azar["pct_alcanzado"] < 0.5


def test_years_have_expected_only_where_every_row_has_a_prediction():
    n = 200
    filas = []
    for cohorte, con_p in ((2019, False), (2022, True)):
        res = ["eliminacion"] * 30 + ["continua"] * (n - 30)
        filas.append(pd.DataFrame({"cohorte_anio": cohorte, "resultado": res, "p": 0.2 if con_p else np.nan}))
    anios = VH.bloque_anios(pd.concat(filas, ignore_index=True))
    assert [a["anio"] for a in anios] == [2020, 2023]                       # year = cohort + 1
    assert anios[0]["esperados"] is None and anios[0]["tasa"] == pytest.approx(0.15)
    assert anios[1]["esperados"] == pytest.approx(40.0) and anios[1]["tasa_esperada"] == pytest.approx(0.2)


def test_partial_year_is_flagged_and_excluded_from_the_key_figure():
    obs = pd.DataFrame({"cohorte_anio": 2023, "resultado": ["eliminacion"] * 20 + ["continua"] * 80, "p": np.nan})
    cens = pd.DataFrame({"cohorte_anio": 2024, "resultado": ["eliminacion"] * 15 + ["continua"] * 60 + ["censurado"] * 30, "p": np.nan})
    anios = VH.bloque_anios(pd.concat([obs, cens], ignore_index=True))
    assert [a["parcial"] for a in anios] == [False, True]
    assert VH.bloque_eliminados(anios, None)["clave"] is None                  # the key figure is the yearly total, not T5


def test_causales_publish_every_cause_with_its_exact_count_and_no_otros_row():
    cods = pd.Series(["0B"] * 50 + ["0D"] * 40 + ["84"] * 5 + ["0A"] * 20)
    b = VH.bloque_causales(cods)
    por = {f["grupo"]: f for f in b["filas"]}
    assert b["total"] == 115 and por["tercera"]["pct"] == pytest.approx(50 / 115)
    assert por["egresado"]["n"] == 5 and por["avance"]["n"] == 20 and por["segunda"]["n"] == 0
    assert [f["grupo"] for f in b["filas"]] == list(VH.GRUPOS_CAUSAL)          # the closed P117 list; "otras" is a cause, not a size bucket
    assert "otros" not in por and sum(f["n"] for f in b["filas"]) == b["total"]


def test_no_size_based_otros_row_anywhere():
    cods = pd.Series(["0B"] * 3 + ["0D"] * 2 + ["84"])
    b = VH.bloque_causales(cods)
    assert b["total"] == 6 and {f["grupo"]: f["n"] for f in b["filas"]}["tercera"] == 3
    assert all(f["grupo"] != "otros" for f in b["filas"])
    assert "otros" not in json.dumps(_documento_pequeno(), default=int)


def test_eliminated_causes_use_the_same_window_and_one_elimination_per_episode_as_the_program_block():
    fac = ["Facultad A"] * 40
    causas = pd.DataFrame({"facultad": fac, "episodio_id": list(range(35)) + [0, 1, 2, 3, 4],
                           "periodo": ["202010"] * 35 + ["202110"] * 3 + ["202610", "202620"],
                           "cod_programa": "P1", "programa": "Uno", "cod_causal": ["0B"] * 40})
    d = VH.construir_documento(_t3(40).assign(facultad="Facultad A", cohorte_anio=2018),
                               pd.DataFrame({"facultad": ["Facultad A"] * 40, "cohorte_anio": 2022}), np.zeros(40, dtype=int),
                               np.zeros(40), pd.DataFrame({"facultad": ["Facultad A"] * 40, "cohorte_anio": 2022, "resultado": "continua",
                                                           "p": 0.1}), causas)
    total_e1 = d["eliminados"]["Toda la UCN"]["causales"]["total"]
    total_e2 = sum(f["total"] for f in d["causales_programa"]["Toda la UCN"]["filas"])
    assert total_e1 == total_e2 == 35
def test_document_has_one_entry_per_filter_and_no_person_columns():
    rng = np.random.default_rng(1)
    n = 300
    fac = np.array(["Facultad A", "Facultad B", "Sin facultad"])[rng.integers(0, 3, n)]
    t3 = _t3(n).assign(facultad=fac, cohorte_anio=2018)
    y = (rng.random(n) < 0.2).astype(int)
    t1 = pd.DataFrame({"facultad": fac, "cohorte_anio": 2022})
    t5 = pd.DataFrame({"facultad": fac, "cohorte_anio": 2022,
                       "resultado": np.where(rng.random(n) < 0.2, "eliminacion", "continua"), "p": rng.random(n) * 0.3})
    causas = pd.DataFrame({"facultad": fac, "cod_causal": rng.choice(["0B", "0D", "2C"], n)})
    doc = VH.construir_documento(t3, t1, y, rng.random(n), t5, causas)
    assert doc["filtros"] == ["Toda la UCN", "Facultad A", "Facultad B"]
    assert set(doc["semestres"]) == set(doc["filtros"]) and "Sin facultad" not in doc["semestres"]
    texto = json.dumps(doc, default=int).lower()
    for prohibido in ("persona_key", "episodio", "rut"):
        assert prohibido not in texto


def test_migration_is_accepted_by_the_runner_guard_and_is_create_only():
    texto = SQL.read_text(encoding="utf-8")
    assert len(validate_sql(texto, SQL.name)) == 1
    assert "neural_mart.vista_historica" in texto


def test_exporter_rows_one_per_block_and_filter():
    doc = {"version": 1, "filtros": ["Toda la UCN", "A"], "cohortes": {}, "semestres": {"Toda la UCN": {"n": 1}, "A": {"n": 2}},
           "siguieron": {"Toda la UCN": {}}, "eliminados": {}, "alcance": {}, "por_facultad": [{"facultad": "A"}]}
    filas = MV.filas(doc)
    assert {(b, f) for b, f, _ in filas} == {("meta", "Toda la UCN"), ("semestres", "Toda la UCN"), ("semestres", "A"),
                                             ("siguieron", "Toda la UCN"), ("por_facultad", "Toda la UCN")}
    assert all(isinstance(json.loads(c), (dict, list)) for _, _, c in filas)
    assert "n_min" not in MV.META and "n_min" not in json.loads(next(c for b, f, c in filas if b == "meta"))


def test_years_with_few_eliminations_are_published():
    obs = pd.DataFrame({"cohorte_anio": 2023, "resultado": ["eliminacion"] * 2 + ["continua"] * 4, "p": np.nan})
    assert VH.bloque_anios(obs) == [{"anio": 2024, "n": 6, "eliminados": 2, "tasa": pytest.approx(2 / 6), "parcial": False,
                                     "esperados": None, "tasa_esperada": None}]


def test_yearly_totals_count_distinct_episodes_per_calendar_year_up_to_202520():
    filas = [(e, "201910", "0B") for e in range(12)] + [(e, "201920", "0B") for e in range(6, 20)]   # episodes 6-11 twice in 2019
    filas += [(100 + e, "202520", "5B") for e in range(15)] + [(300 + e, "202610", "5B") for e in range(30)] + [(500, "202010", "0D")]
    d = pd.DataFrame(filas, columns=["episodio_id", "periodo", "cod_causal"])
    assert VH.bloque_totales(d) == [{"anio": 2019, "eliminados": 20}, {"anio": 2020, "eliminados": 1}, {"anio": 2025, "eliminados": 15}]   # 2026 out of range
    b = VH.bloque_eliminados([], None, VH.bloque_totales(d))
    assert b["clave"] == {"anio": 2025, "eliminados": 15} and b["totales"][0]["anio"] == 2019


def test_document_has_no_person_level_keys():
    rng = np.random.default_rng(2)
    n = 400
    fac = np.array(["Facultad A", "Facultad B"])[rng.integers(0, 2, n)]
    t3 = _t3(n).assign(facultad=fac, cohorte_anio=2018)
    t1 = pd.DataFrame({"facultad": fac, "cohorte_anio": 2022, "via_clase": rng.choice(["regular", "especial"], n),
                       "tipo_colegio": rng.choice(["H1", "T1"], n), "pct_ponderado": rng.uniform(300, 900, n),
                       "reprobados": rng.integers(0, 5, n)})
    t5 = pd.DataFrame({"facultad": fac, "cohorte_anio": 2022, "resultado": "continua", "p": rng.random(n) * 0.3})
    causas = pd.DataFrame({"facultad": fac, "episodio_id": np.arange(n), "periodo": "202010",
                           "cod_programa": np.where(fac == "Facultad A", "P1", "P2"), "programa": np.where(fac == "Facultad A", "Uno", "Dos"),
                           "cod_causal": rng.choice(["0B", "0D", "2C"], n)})
    ramos = pd.DataFrame({"facultad": fac[:60], "codigo": [f"C{i % 12}" for i in range(60)], "nombre": [f"Curso {i % 12}" for i in range(60)],
                          "depto": "DM", "semestre": [1 + i % 4 for i in range(60)], "intentos": 80, "reprobados": 30})
    esperado = pd.DataFrame({"facultad": fac[:40], "ventana": ["prueba", "posterior"] * 20, "codigo": [f"C{i % 10}" for i in range(40)],
                             "nombre": [f"Curso {i % 10}" for i in range(40)], "depto": "DM", "depto_desc": "Matemática",
                             "intentos": 100, "observados": 30, "esperados": 25.0, "varianza": 18.0})
    prerreq = pd.DataFrame({"cod_programa": "P1", "catalogo": "1", "codigo_requisito": ["C0", "C1"], "codigo_asignatura": ["C1", "C2"]})
    tiempo = pd.DataFrame({"facultad": fac, "cod_programa": np.where(fac == "Facultad A", "P1", "P2"), "programa": "Prog",
                           "duracion_nominal_sem": 10, "seguimiento_max": 16, "tiempo": rng.integers(8, 15, n), "causa": rng.choice([1, 2], n)})
    doc = VH.construir_documento(t3, t1, (rng.random(n) < 0.2).astype(int), rng.random(n), t5, causas,
                                 ramos=ramos, esperado=esperado, prerreq=prerreq, tiempo=tiempo)
    nuevos = ("perfil_ingreso", "primer_semestre", "ramos_reprobados", "ramos_esperado", "cuellos_botella", "semestre_malla",
              "causales_programa", "tiempo_egreso")
    assert all(doc[b] for b in nuevos) and set(nuevos) <= set(MV.BLOQUES)
    assert VH.UCN in doc["causales_programa"] and doc["causales_programa"][VH.UCN]["nivel"] == "facultad"
    texto = json.dumps(doc, default=int).lower()
    for prohibido in ("persona_key", "episodio", "docente", "nrc", "seccion", "sección", "rut"):
        assert prohibido not in texto
    assert len(VH.resumen(doc).splitlines()) == 9


def test_semestres_publish_every_cell_even_when_it_is_one_to_nine():
    d = pd.DataFrame({"tiempo": [1] * 15 + [2] * 23 + [5] * 30, "causa": [2] * 68,
                      "eliminado": [False] * 15 + [True] * 3 + [False] * 20 + [False] * 30})
    d = pd.concat([d, pd.DataFrame({"tiempo": [1] * 40, "causa": [1] * 40, "eliminado": [False] * 40})], ignore_index=True)
    b = VH.bloque_semestres(d)
    assert b["filas"][1]["eliminados"] == 3 and b["filas"][1]["dejan"] == 20
    assert b["bajas_primer_anio"] == 38 and b["bajas"] == 68
    assert b["pct_bajas_primer_anio"] == pytest.approx(38 / 68) and b["pct_bajas"] == pytest.approx(68 / 108)


def test_zero_n_group_has_null_pct():
    sin_bajas = pd.DataFrame({"tiempo": [1] * 12, "causa": [1] * 12, "eliminado": [False] * 12})   # nobody leaves: total 0
    b = VH.bloque_semestres(sin_bajas)
    assert b["bajas"] == 0 and b["pct_bajas_primer_anio"] is None and b["pct_bajas"] == 0.0
    assert all(f["dejan"] == 0 and f["pct_dejan"] == 0.0 for f in b["filas"])                  # n > 0: a true zero is 0 %
    assert VH._pct(0, 0) is None and VH._pct(3, 0) is None


def _documento_pequeno():
    """A 3-person faculty next to a big one."""
    rng = np.random.default_rng(5)
    fac = np.array(["Grande"] * 60 + ["Chica"] * 3)
    n = len(fac)
    t3 = _t3(n).assign(facultad=fac, cohorte_anio=2018)
    t1 = pd.DataFrame({"facultad": fac, "cohorte_anio": 2022})
    t5 = pd.DataFrame({"facultad": fac, "cohorte_anio": 2022, "resultado": np.where(rng.random(n) < 0.3, "eliminacion", "continua"),
                       "p": rng.random(n) * 0.3})
    causas = pd.DataFrame({"facultad": fac, "cod_causal": rng.choice(["0B", "0D", "2C"], n)})
    y = np.array([1, 0, 1] * 21)
    return VH.construir_documento(t3, t1, y, rng.random(n), t5, causas)


def test_small_faculty_block_is_published_with_exact_counts():
    doc = _documento_pequeno()
    assert doc["filtros"] == ["Toda la UCN", "Chica", "Grande"]
    chica = doc["siguieron"]["Chica"]
    assert chica["n"] == 3 and chica["siguieron"] == 1 and chica["pct_siguieron"] == pytest.approx(1 / 3)     # y = [1, 0, 1]
    assert doc["semestres"]["Chica"]["n"] == 3
    assert {p["facultad"]: p["n"] for p in doc["por_facultad"]} == {"Chica": 3, "Grande": 60}
    assert doc["eliminados"]["Chica"]["causales"]["total"] == 3
    assert "n_min" not in doc


def test_every_percentage_row_carries_its_n():
    doc = _documento_pequeno()
    for f in doc["semestres"]["Chica"]["filas"]:
        assert f["pct_dejan"] is None or doc["semestres"]["Chica"]["n"] > 0
    for c in doc["eliminados"]["Chica"]["causales"]["filas"]:
        assert "n" in c and "pct" in c
    for a in doc["eliminados"]["Chica"]["anios"]:
        assert "n" in a and "tasa" in a


# ------------------------------------------------------------------------------------- program filter and model behind each block
PROGRAMAS = pd.DataFrame({"nombre_programa": ["Uno", "Dos", "Tres"], "facultad_nombre": ["Facultad A", "Facultad A", "Facultad B"]},
                         index=pd.Index(["P1", "P2", "P3"], name="cod_programa"))
OBSERVADOS = ("semestres", "ramos_reprobados", "cuellos_botella", "semestre_malla", "causales_programa", "tiempo_egreso")
DESCRIPTIVOS = ("senales", "esperar_semestre")


def _documento_completo(programas=PROGRAMAS, senales=None):
    """Every block, for 3 programs: P1 (149 students), P2 (ONE student) and P3 (150), in two faculties."""
    rng = np.random.default_rng(11)
    cod = np.array(["P1"] * 149 + ["P2"] + ["P3"] * 150)
    n = len(cod)
    fac = np.where(cod == "P3", "Facultad B", "Facultad A")
    y = (rng.random(n) < 0.2).astype(int)
    y[cod == "P2"] = 1
    t3 = _t3(n).assign(facultad=fac, cod_programa=cod, cohorte_anio=2018)
    t1 = pd.DataFrame({"facultad": fac, "cod_programa": cod, "cohorte_anio": 2022, "via_clase": rng.choice(["regular", "especial"], n),
                       "tipo_colegio": rng.choice(["H1", "T1"], n), "pct_ponderado": rng.uniform(300, 900, n),
                       "reprobados": rng.integers(0, 5, n)})
    t5 = pd.DataFrame({"facultad": fac, "cod_programa": cod, "cohorte_anio": 2022, "resultado": "continua", "p": rng.random(n) * 0.3})
    causas = pd.DataFrame({"facultad": fac, "cod_programa": cod, "programa": np.select([cod == "P1", cod == "P2"], ["Uno", "Dos"], "Tres"),
                           "episodio_id": np.arange(n), "periodo": "202010", "cod_causal": rng.choice(["0B", "0D", "2C"], n)})
    cr, ce = np.array(["P1", "P2", "P3"] * 20), np.array(["P1", "P2", "P3"] * 14)[:40]
    fr, fe = np.where(cr == "P3", "Facultad B", "Facultad A"), np.where(ce == "P3", "Facultad B", "Facultad A")
    ramos = pd.DataFrame({"facultad": fr, "cod_programa": cr, "codigo": [f"C{(i // 3) % 12}" for i in range(60)],
                          "nombre": [f"Curso {(i // 3) % 12}" for i in range(60)], "depto": "DM", "semestre": [1 + i % 4 for i in range(60)],
                          "intentos": 80, "reprobados": 30})
    esperado = pd.DataFrame({"facultad": fe, "cod_programa": ce, "ventana": ["prueba", "posterior"] * 20, "codigo": [f"C{i % 10}" for i in range(40)],
                             "nombre": [f"Curso {i % 10}" for i in range(40)], "depto": "DM", "depto_desc": "Matemática",
                             "intentos": 100, "observados": 30, "esperados": 25.0, "varianza": 18.0})
    prerreq = pd.DataFrame({"cod_programa": "P1", "catalogo": "1", "codigo_requisito": ["C0", "C1", "C2"], "codigo_asignatura": ["C1", "C2", "C3"]})
    tiempo = pd.DataFrame({"facultad": fac, "cod_programa": cod, "programa": "Prog", "duracion_nominal_sem": 10, "seguimiento_max": 16,
                           "tiempo": rng.integers(8, 15, n), "causa": rng.choice([1, 2], n)})
    senales = senales if senales is not None else {"tareas": [{"tarea": "t1", "k": 1, "modelo": "cb_acad", "n_muestra": 100, "senales": []}]}
    esperar = {"comparaciones": [{"tarea": "t1", "k_antes": 1, "k_despues": 2, "de_cada_10_antes": 5.0, "de_cada_10_despues": 6.0}]}
    return VH.construir_documento(t3, t1, y, rng.random(n), t5, causas, ramos=ramos, esperado=esperado, prerreq=prerreq, tiempo=tiempo,
                                  senales=senales, esperar_semestre=esperar, programas=programas)


def test_every_block_is_published_per_program():
    doc = _documento_completo()
    for bloque in MV.BLOQUES:
        if bloque in DESCRIPTIVOS:
            continue
        assert {"P1", "P2", "P3"} <= set(doc[bloque]), bloque
    assert doc["siguieron"]["P2"]["n"] == 1 and doc["semestres"]["P2"]["n"] == 1                 # a program of ONE student is published
    assert doc["siguieron"]["P1"]["n"] == 149 and doc["siguieron"]["Facultad A"]["n"] == 150
    assert [f["cod_programa"] for f in doc["causales_programa"]["P2"]["filas"]] == ["P2"]
    assert {f["cod_programa"] for f in doc["causales_programa"]["Facultad A"]["filas"]} == {"P1", "P2"}
    assert doc["eliminados"]["P3"]["causales"]["total"] == 150


def test_program_filter_carries_faculty_and_name():
    doc = _documento_completo()
    assert doc["programas"] == [{"codigo": "P2", "nombre": "Dos", "facultad": "Facultad A"},           # by faculty, then by name
                                {"codigo": "P1", "nombre": "Uno", "facultad": "Facultad A"},
                                {"codigo": "P3", "nombre": "Tres", "facultad": "Facultad B"}]
    assert doc["filtros"] == ["Toda la UCN", "Facultad A", "Facultad B"]                           # the existing filters do not change
    assert "programas" in MV.META and "modelos" in MV.META
    meta = json.loads(next(c for b, f, c in MV.filas(doc) if b == "meta"))
    assert meta["programas"] == doc["programas"]
    assert {("siguieron", "P2"), ("siguieron", "Facultad A"), ("siguieron", "Toda la UCN")} <= {(b, f) for b, f, _ in MV.filas(doc)}


def test_without_a_program_dictionary_only_ucn_and_faculties_are_published():
    doc = _documento_completo(programas=None)
    assert doc["programas"] == [] and set(doc["siguieron"]) == {"Toda la UCN", "Facultad A", "Facultad B"}


def test_model_blocks_declare_their_model_and_observed_blocks_null():
    doc = _documento_completo()
    for filtro in ("Toda la UCN", "Facultad B", "P2"):
        for bloque in OBSERVADOS:
            assert doc[bloque][filtro]["modelo"] is None and "modelos" not in doc[bloque][filtro], (bloque, filtro)
    t1 = {"tarea": "T1", "tarea_nombre": "Continuidad", "modelo": "cb_acad", "modelo_nombre": "CatBoost (ingreso + agregados)", "k": 1,
          "corte": "1.er semestre", "tipo": "esperado"}
    for bloque in ("siguieron", "alcance", "perfil_ingreso", "primer_semestre"):
        for filtro in ("Toda la UCN", "P2"):
            m = dict(doc[bloque][filtro]["modelo"])
            assert m.pop("particion").startswith("Prueba") and m == t1, (bloque, filtro)
    e = doc["eliminados"]["P1"]["modelo"]
    assert (e["tarea"], e["tarea_nombre"], e["modelo"], e["k"], e["corte"], e["tipo"]) == ("T5", "Eliminación", "gru_adm", 2, "2.º semestre", "esperado")
    r = doc["ramos_esperado"]["P3"]["modelo"]
    assert (r["tarea"], r["modelo"], r["k"], r["tipo"]) == ("T2", "cb_c_nuevas", 0, "esperado") and "2023" in r["particion"]
    assert doc["modelos"]["semestres"] is None and doc["modelos"]["siguieron"]["modelo"] == "cb_acad" and doc["modelos"]["por_facultad"]["tarea"] == "T1"


def test_model_description_blocks_do_not_vary_by_population():
    con, sin = _documento_completo(), _documento_completo(programas=None)
    for bloque in DESCRIPTIVOS:
        assert set(con[bloque]) == {"Toda la UCN"} and con[bloque]["Toda la UCN"]["aplica_a_poblacion"] is False, bloque
        assert con[bloque] == sin[bloque]                                                           # the same with or without program filters
        assert con[bloque]["Toda la UCN"]["modelo"] is None and len(con[bloque]["Toda la UCN"]["modelos"]) >= 1
    assert con["senales"]["Toda la UCN"]["modelos"][0]["modelo"] == "cb_acad"
    assert [m["modelo"] for m in con["esperar_semestre"]["Toda la UCN"]["modelos"]] == ["cb_acad", "lr_acad"]


def test_program_blocks_have_no_person_level_keys():
    texto = json.dumps(_documento_completo(), default=int, ensure_ascii=False).lower()
    for prohibido in ("persona_key", "episodio", "docente", "nrc", "seccion", "sección", "rut"):
        assert prohibido not in texto, prohibido
