"""T2 snapshot (one row per evaluated attempt): rules, strict-past lookups, prerequisite features, teacher context and
the generic leakage guard (changing / deleting facts of period >= p never changes the features of p). No database."""
import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from pipelines.snapshots import features_t2 as F2   # noqa: E402
from pipelines.snapshots import rules_t2 as R2       # noqa: E402

LATEST = "202620"


# ---------------------------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------------------------
def episodios(*rows):
    cols = ["episodio_id", "persona_key", "cod_programa", "periodo_admision", "cod_admision", "id_nivel", "sede",
            "tipo_qualitas", "sexo"]
    return pd.DataFrame([dict(zip(cols, r)) for r in rows], columns=cols)


def ep(eid, persona, adm="201510", prog="C1", cod="LS", nivel=1):
    return (eid, persona, prog, adm, cod, nivel, 1, "1. Ingreso Regular o Centralizada", "F")


def intentos(*rows):
    """(persona, episodio_id, periodo, codigo, nota|'DPA', opts) ; opts: nrc, oportunidad, catalogo, tipo."""
    out = []
    for i, (persona, eid, periodo, codigo, nota, *rest) in enumerate(rows):
        o = rest[0] if rest else {}
        tipo = o.get("tipo", "convalidacion" if nota == "DPA" else "evaluado")
        evaluado = tipo == "evaluado"
        out.append({
            "intento_id": i + 1, "persona_key": persona, "episodio_id": eid, "periodo": periodo,
            "codigo_asignatura": codigo, "catalogo": o.get("catalogo", "2019"), "nrc": o.get("nrc"),
            "oportunidad": o.get("oportunidad", 1), "es_intento_evaluado": evaluado,
            "nota_numerica": float(nota) if evaluado else np.nan, "nota_es_heredada": False, "resultado_tipo": tipo,
            "aprobado_curricular": (float(nota) >= 4.0) if evaluado else (True if tipo == "convalidacion" else None),
            "creditos": 6.0, "creditos_reconocidos": 6.0 if tipo == "convalidacion" else np.nan,
        })
    df = pd.DataFrame(out)
    df["episodio_id"] = df["episodio_id"].astype("Int64")
    return df


def estados(*rows):
    out = [{"persona_key": p, "episodio_id": e, "periodo": per, "cod_estado": c, "cod_programa": "C1",
            "catalogo": "2019", "es_correccion_sistema": False, "orden_canonico": i + 1}
           for i, (p, e, per, c) in enumerate(rows)]
    df = pd.DataFrame(out, columns=["persona_key", "episodio_id", "periodo", "cod_estado", "cod_programa",
                                    "catalogo", "es_correccion_sistema", "orden_canonico"])
    df["episodio_id"] = df["episodio_id"].astype("Int64")
    return df


VIA = pd.DataFrame(columns=["postulacion_via_id", "year_admision", "persona_key", "cod_carrera", "cod_admision",
                            "preferencia", "matricula", "puntaje_leng", "puntaje_mat", "puntaje_ciencias",
                            "puntaje_historia", "puntaje_nem", "puntaje_ranking", "notas_em", "ponderado",
                            "tipo_colegio", "depend_colegio", "region_colegio"])
MALLA = pd.DataFrame([
    ("C1", "2019", "A", 1, 6.0, "basica", "MAT"), ("C1", "2019", "B", 2, 6.0, "basica", "MAT"),
    ("C1", "2019", "C", 2, 6.0, "profesional", "ING"), ("C1", "2019", "D", 3, 6.0, "profesional", "ING"),
], columns=["cod_programa", "catalogo", "codigo_asignatura", "semestre", "creditos", "formacion", "depto"])
PRE = pd.DataFrame([("C1", "2019", "A", "B"), ("C1", "2019", "A", "D"), ("C1", "2019", "B", "D")],
                   columns=["cod_programa", "catalogo", "codigo_requisito", "codigo_asignatura"])
SIN_DOC = pd.DataFrame(columns=["periodo", "nrc", "docente_key"])


def construir(ep_, it, est=None, docentes=SIN_DOC, malla=MALLA, pre=PRE):
    est = estados() if est is None else est
    snap, embudo = F2.construir_snapshot_t2(ep_, it, est, VIA, malla, pre, docentes, LATEST)
    return snap, embudo


def fila(snap, persona, periodo, codigo):
    r = snap[(snap["persona_key"] == persona) & (snap["periodo"] == periodo) & (snap["codigo_asignatura"] == codigo)]
    assert len(r) == 1, (persona, periodo, codigo, len(r))
    return r.iloc[0]


# ---------------------------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------------------------
def test_split_by_attempt_period_and_window():
    assert [R2.split_periodo(p) for p in ("201510", "202020", "202110", "202220", "202310", "202420", "202510")] == [
        "train", "train", "valid", "valid", "test", "test", "posterior"]
    assert R2.en_ventana("201510", LATEST) and R2.en_ventana("202520", LATEST)
    assert not R2.en_ventana("201420", LATEST) and not R2.en_ventana("202610", LATEST)
    assert not R2.en_ventana("201915", LATEST) and not R2.en_ventana("202010", "202010")
    assert R2.reprobado(3.9) and not R2.reprobado(4.0)
    assert R2.sin_reprobacion("201920") and R2.sin_reprobacion("202010") and not R2.sin_reprobacion("202020")


# ---------------------------------------------------------------------------------------------
# strict past
# ---------------------------------------------------------------------------------------------
def test_previo_uses_only_strictly_earlier_periods():
    der = pd.DataFrame({"k": [1, 1, 1], "per": [201910, 201920, 202010], "v": [1.0, 3.0, 6.0]})
    izq = pd.DataFrame({"k": [1, 1, 1, 1], "per": [201910, 201915, 201920, 202020]})
    out = F2.previo(izq, der, "k", ["v"])
    assert out["v"].isna().tolist() == [True, False, False, False]
    assert out["v"].dropna().tolist() == [1.0, 1.0, 6.0]       # 201915 sees 201910; 201920 sees 201910 (not itself)


def test_acumulado_is_inclusive_running_sum_and_max():
    ev = pd.DataFrame({"k": [1, 1, 1], "per": [1, 1, 2], "n": [1, 1, 1], "m": [3.0, 5.0, 4.0]})
    out = F2.acumulado(ev, "k", ["n"], ["m"])
    assert out["n"].tolist() == [2, 3] and out["m"].tolist() == [5.0, 5.0]


# ---------------------------------------------------------------------------------------------
# population and label
# ---------------------------------------------------------------------------------------------
def test_population_label_and_funnel():
    e = episodios(ep(1, "p1"), ep(2, "p2", cod="IN"), ep(3, "p3", nivel=2))
    it = intentos(
        ("p1", 1, "201510", "A", 3.9), ("p1", 1, "201515", "C", 5.0),            # summer: history only, not a row
        ("p1", 1, "201520", "A", 4.0), ("p1", 1, "201520", "B", "DPA"),         # convalidation: not a row
        ("p1", 1, "202610", "A", 6.0),                                           # in-progress period
        ("p2", 2, "201510", "A", 5.0), ("p3", 3, "201510", "A", 5.0),
        ("p1", None, "201510", "C", 5.0),                                        # no episode
    )
    snap, embudo = construir(e, it)
    assert sorted(zip(snap["persona_key"], snap["periodo"], snap["codigo_asignatura"])) == [
        ("p1", "201510", "A"), ("p1", "201520", "A")]
    assert fila(snap, "p1", "201510", "A")["y"] == 1 and fila(snap, "p1", "201520", "A")["y"] == 0   # 4.0 approves
    assert fila(snap, "p1", "201510", "A")["split"] == "train"
    ns = [x["n"] for x in embudo]
    assert ns == sorted(ns, reverse=True) and ns[-1] == 2


def test_features_known_at_enrollment():
    e = episodios(ep(1, "p1"))
    it = intentos(("p1", 1, "201510", "A", 3.0, {"oportunidad": 1}), ("p1", 1, "201510", "C", 5.0),
                  ("p1", 1, "201520", "A", 5.0, {"oportunidad": 2}), ("p1", 1, "201520", "B", 5.0))
    snap, _ = construir(e, it)
    r = fila(snap, "p1", "201520", "A")
    assert r["oportunidad"] == 2 and r["n_prev_curso"] == 1 and r["mejor_nota_prev_curso"] == 3.0
    assert r["n_cursos_carga"] == 2 and r["n_repetidos_carga"] == 1 and r["creditos_carga"] == 12.0
    assert r["k"] == 2 and r["sem_malla"] == 1 and r["desfase"] == 1.0
    f = fila(snap, "p1", "201510", "A")
    assert f["n_prev_curso"] == 0 and np.isnan(f["mejor_nota_prev_curso"]) and f["k"] == 1
    assert f["n_intentos_acum"] == 0 and np.isnan(f["prom_acum"]) and f["creditos_aprob_acum"] == 0
    assert r["n_intentos_acum"] == 2 and r["n_reprob_acum"] == 1 and r["prom_acum"] == pytest.approx(4.0)
    assert r["creditos_aprob_acum"] == 6.0 and r["tasa_aprob_acum"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------------------------
# course history, expanding and strictly past
# ---------------------------------------------------------------------------------------------
def test_course_history_excludes_the_same_period_and_later_periods():
    e = episodios(ep(1, "p1"), ep(2, "p2"), ep(3, "p3"))
    it = intentos(
        ("p1", 1, "201510", "A", 3.0), ("p2", 2, "201510", "A", 5.0),           # period 201910: 1 fail, 1 pass
        ("p3", 3, "201520", "A", 6.0),                                           # 201920 sees 2 attempts, rate 0.5
        ("p1", 1, "201610", "A", 7.0),                                           # 202010 sees 3 attempts, rate 2/3
    )
    snap, _ = construir(e, it)
    assert fila(snap, "p1", "201510", "A")["n_hist_curso"] == 0
    assert np.isnan(fila(snap, "p1", "201510", "A")["tasa_hist_curso"])
    assert fila(snap, "p2", "201510", "A")["n_hist_curso"] == 0                  # same period is not history
    r = fila(snap, "p3", "201520", "A")
    assert r["n_hist_curso"] == 2 and r["tasa_hist_curso"] == pytest.approx(0.5)
    assert r["prom_hist_curso"] == pytest.approx(4.0)
    r = fila(snap, "p1", "201610", "A")
    assert r["n_hist_curso"] == 3 and r["tasa_hist_curso"] == pytest.approx(2 / 3)
    assert 0.5 < r["tasa_hist_curso_suav"] < 1.0                                  # shrunk toward the prior, still in (0,1)
    assert r["n_hist_curso_prog"] == 3


def test_course_history_counts_attempts_outside_the_target_population():
    e = episodios(ep(1, "p1"), ep(2, "p2", cod="IN"))
    it = intentos(("p2", 2, "201510", "A", 2.0), ("p2", 2, "201515", "A", 2.0), ("p1", 1, "201520", "A", 5.0))
    snap, _ = construir(e, it)
    assert fila(snap, "p1", "201520", "A")["n_hist_curso"] == 2                   # exchange student / summer attempt


# ---------------------------------------------------------------------------------------------
# explicit prerequisites
# ---------------------------------------------------------------------------------------------
def test_prerequisite_state_before_the_period():
    e = episodios(ep(1, "p1"), ep(2, "p2"), ep(3, "p3"))
    it = intentos(
        ("p1", 1, "201510", "A", 3.0),                                           # fails A
        ("p1", 1, "201520", "B", 5.0),                                           # B with A failed and pending
        ("p1", 1, "201610", "A", 5.5),                                           # approves A
        ("p1", 1, "201620", "D", 4.5),                                           # D needs A (5.5) and B (5.0)
        ("p2", 2, "201510", "A", "DPA"), ("p2", 2, "201520", "B", 5.0),          # A by convalidation
        ("p3", 3, "201520", "A", 5.0), ("p3", 3, "201520", "B", 5.0),            # same period as its prerequisite
    )
    snap, _ = construir(e, it)
    r = fila(snap, "p1", "201520", "B")
    assert (r["n_prereq"], r["n_prereq_aprob"], r["n_prereq_pend_reprob"]) == (1, 0, 1) and r["min_nota_prereq"] == 3.0
    r = fila(snap, "p1", "201620", "D")
    assert (r["n_prereq"], r["n_prereq_aprob"], r["n_prereq_pend_reprob"], r["n_prereq_conva"]) == (2, 2, 0, 0)
    assert r["min_nota_prereq"] == 5.0 and r["mean_nota_prereq"] == pytest.approx(5.25)
    r = fila(snap, "p2", "201520", "B")
    assert (r["n_prereq_aprob"], r["n_prereq_conva"], r["n_prereq_pend_reprob"]) == (1, 1, 0)
    assert np.isnan(r["min_nota_prereq"])                                        # a convalidation brings no grade
    r = fila(snap, "p3", "201520", "B")                                          # A in the same period is not past
    assert (r["n_prereq_aprob"], r["n_prereq_en_carga"]) == (0, 1)
    r = fila(snap, "p1", "201510", "A")
    assert r["info_prereq"] and r["n_prereq"] == 0                               # known malla, no prerequisite


def test_coverage_flags_when_the_course_is_not_in_the_malla_or_the_catalog_is_unknown():
    e = episodios(ep(1, "p1"))
    it = intentos(("p1", 1, "201510", "Z", 5.0), ("p1", 1, "201510", "A", 5.0, {"catalogo": "1999"}))
    snap, _ = construir(e, it)
    z = fila(snap, "p1", "201510", "Z")
    assert not z["en_malla"] and not z["info_prereq"] and np.isnan(z["n_prereq"]) and np.isnan(z["sem_malla"])
    assert z["malla_conocida"]                                                    # the program+catalog is in the malla table
    a = fila(snap, "p1", "201510", "A")
    assert not a["malla_conocida"] and not a["info_prereq"] and np.isnan(a["n_prereq"])


# ---------------------------------------------------------------------------------------------
# teacher / section ablation
# ---------------------------------------------------------------------------------------------
def test_teacher_history_is_strictly_past_and_only_where_the_offer_exists():
    e = episodios(ep(1, "p1"), ep(2, "p2"), ep(3, "p3"))
    it = intentos(
        ("p1", 1, "201510", "A", 3.0, {"nrc": "1"}), ("p2", 2, "201510", "A", 5.0, {"nrc": "1"}),
        ("p3", 3, "201520", "A", 6.0, {"nrc": "2"}), ("p1", 1, "201520", "C", 5.0),   # C: no nrc
    )
    doc = pd.DataFrame([("201510", "1", "T1"), ("201520", "2", "T1")], columns=["periodo", "nrc", "docente_key"])
    snap, _ = construir(e, it, docentes=doc)
    r = fila(snap, "p1", "201510", "A")
    assert r["tiene_docente"] and r["doc_n"] == 0                                 # same period is not history
    r = fila(snap, "p3", "201520", "A")
    assert r["doc_n"] == 2 and r["doc_curso_n"] == 2
    assert not fila(snap, "p1", "201520", "C")["tiene_docente"]
    assert np.isnan(fila(snap, "p1", "201520", "C")["doc_tasa_suav"])


# ---------------------------------------------------------------------------------------------
# periods without recorded failures (201920, 202010)
# ---------------------------------------------------------------------------------------------
def test_periods_without_recorded_failures_are_not_units_nor_pass_rate_history_but_keep_credits_and_prerequisites():
    e = episodios(ep(1, "p1"), ep(2, "p2"))
    it = intentos(
        ("p1", 1, "201920", "A", 4.0), ("p2", 2, "201920", "A", 4.0),            # 4.0 floor, no failures recorded
        ("p1", 1, "202010", "C", 5.0),
        ("p1", 1, "202020", "B", 3.0), ("p2", 2, "202020", "A", 5.0),            # B needs A (approved in 201920)
        ("p1", 1, "202110", "C", 5.0),
    )
    snap, embudo = construir(e, it)
    assert set(snap["periodo"]) == {"202020", "202110"}
    assert any("reprobacion no registrada" in x["paso"] for x in embudo)
    r = fila(snap, "p1", "202020", "B")
    assert r["n_prereq_aprob"] == 1 and r["creditos_aprob_acum"] == 12.0          # approvals/credits still count
    assert r["n_intentos_acum"] == 0 and np.isnan(r["prom_acum"]) and np.isnan(r["tasa_aprob_acum"])
    assert fila(snap, "p2", "202020", "A")["n_hist_curso"] == 0                    # the 4.0s of 201920 are not course history
    assert fila(snap, "p1", "202110", "C")["n_intentos_acum"] == 1                 # only 202020 counts


# ---------------------------------------------------------------------------------------------
# generic leakage guard
# ---------------------------------------------------------------------------------------------
def _sintetico(seed=0, n_est=40):
    rng = np.random.default_rng(seed)
    periodos = ["201510", "201515", "201520", "201610", "201620", "201710", "201720", "201810", "201820"]
    cursos = ["A", "B", "C", "D", "Z"]
    filas, eps, doc = [], [], []
    for i in range(n_est):
        eps.append(ep(i + 1, f"p{i}", adm=str(rng.choice(["201510", "201520", "201610"]))))
        for per in periodos:
            for c in rng.choice(cursos, size=int(rng.integers(0, 4)), replace=False):
                tipo = "convalidacion" if rng.random() < 0.05 else "evaluado"
                nota = "DPA" if tipo == "convalidacion" else float(np.round(rng.uniform(2, 7), 1))
                filas.append((f"p{i}", i + 1, per, str(c), nota, {"nrc": f"{per}{c}{rng.integers(0, 2)}"}))
    for per in periodos:
        for c in cursos:
            for j in range(2):
                doc.append((per, f"{per}{c}{j}", f"T{rng.integers(0, 4)}"))
    return episodios(*eps), intentos(*filas), pd.DataFrame(doc, columns=["periodo", "nrc", "docente_key"])


def _comparar(a, b, cols):
    key = ["intento_id"]
    m = a.merge(b, on=key, suffixes=("_a", "_b"))
    assert len(m) == len(a) == len(b)
    for c in cols:
        x, y = m[f"{c}_a"], m[f"{c}_b"]
        both_nan = x.isna() & y.isna()
        assert ((x == y) | both_nan).all(), c


FEATURES = [c for c in F2.SNAPSHOT_COLS_T2 if c not in
            ("intento_id", "episodio_id", "persona_key", "periodo", "cod_programa", "catalogo", "codigo_asignatura",
             "split", "y", "banda_nota", "sexo_equidad")]


@pytest.mark.parametrize("corte", ["201610", "201710", "201810"])
def test_changing_facts_of_period_p_or_later_never_changes_features_up_to_p(corte):
    e, it, doc = _sintetico()
    base, _ = construir(e, it, docentes=doc)
    it2 = it.copy()
    tarde = it2["periodo"] >= corte
    rng = np.random.default_rng(5)
    ev = tarde & it2["es_intento_evaluado"]
    it2.loc[ev, "nota_numerica"] = rng.uniform(1, 7, int(ev.sum())).round(1)
    it2.loc[ev, "aprobado_curricular"] = it2.loc[ev, "nota_numerica"] >= 4.0
    pert, _ = construir(e, it2, docentes=doc)
    sel_b, sel_p = base[base["periodo"] <= corte], pert[pert["periodo"] <= corte]
    assert len(sel_b) > 30
    _comparar(sel_b, sel_p, FEATURES)
    assert (base["y"] != pert["y"]).any()                                          # the perturbation did something


@pytest.mark.parametrize("corte", ["201520", "201620"])
def test_deleting_later_periods_never_changes_features_up_to_p(corte):
    e, it, doc = _sintetico(seed=3)
    base, _ = construir(e, it, docentes=doc)
    corto, _ = construir(e, it[it["periodo"] <= corte].reset_index(drop=True), docentes=doc)
    sel = base[base["periodo"] <= corte]
    assert len(corto) == len(sel)
    _comparar(sel.assign(intento_id=sel["intento_id"]), corto, FEATURES)


def test_sex_and_labels_are_not_feature_columns():
    assert not {"sexo_equidad", "y", "nota", "split", "persona_key"} & set(FEATURES)
    assert not [c for c in FEATURES if "docente_key" in c]


# ---------------------------------------------------------------------------------------------
# P74 / P84 (DAI, 13-11-2026): grade band of each attempt (label side)
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("nota,banda", [
    (1.0, "reprobado"), (3.9, "reprobado"), (3.99, "reprobado"),
    (4.0, "unanimidad"), (5.0, "unanimidad"), (5.3, "unanimidad"), (5.39, "unanimidad"),
    (5.4, "distincion"), (6.0, "distincion"), (6.3, "distincion"), (6.39, "distincion"),
    (6.4, "maxima_distincion"), (6.9, "maxima_distincion"), (7.0, "maxima_distincion"),
])
def test_p84_grade_bands_follow_the_institutional_recognition_scale(nota, banda):
    """Aprobado por Unanimidad 4.0-5.3, con Distincion 5.4-6.3, con Maxima Distincion 6.4-7.0; the cuts are the
    half-open intervals [4.0, 5.4), [5.4, 6.4) and [6.4, 7.0], so a grade with two decimals falls in one band only."""
    assert R2.banda_nota(nota) == banda


def test_p84_bands_are_the_documented_four_and_a_missing_grade_has_none():
    assert R2.BANDAS == ("reprobado", "unanimidad", "distincion", "maxima_distincion")
    assert R2.banda_nota(None) is None and R2.banda_nota(float("nan")) is None
    assert R2.CORTES_BANDA == (4.0, 5.4, 6.4)
    assert set(R2.ETIQUETA_BANDA) == set(R2.BANDAS)


def test_p84_the_migration_allows_exactly_the_new_band_values():
    import re
    from pathlib import Path
    texto = (Path(__file__).resolve().parents[2] / "sql" / "core" / "022_banda_nota_p84.sql").read_text(encoding="utf-8")
    assert set(re.findall(r"'(\w+)'", texto.split("CHECK")[1])) == set(R2.BANDAS)


def test_p74_snapshot_carries_the_band_and_it_agrees_with_the_binary_label():
    e = episodios(ep(1, "p1"))
    it = intentos(("p1", 1, "201510", "A", 3.9), ("p1", 1, "201510", "B", 4.0), ("p1", 1, "201520", "A", 5.5),
                  ("p1", 1, "201520", "B", 6.4))
    snap, _ = construir(e, it)
    bandas = {(r.periodo, r.codigo_asignatura): r.banda_nota for r in snap.itertuples()}
    assert bandas == {("201510", "A"): "reprobado", ("201510", "B"): "unanimidad", ("201520", "A"): "distincion",
                      ("201520", "B"): "maxima_distincion"}
    assert ((snap["banda_nota"] == "reprobado").astype(int) == snap["y"]).all()


def test_p74_band_is_label_side_never_a_feature():
    assert "banda_nota" not in set(F2.FEATURE_COLS_ESTUDIANTE + F2.FEATURE_COLS_CURSO + F2.FEATURE_COLS_CARGA)
    assert "banda_nota" in F2.SNAPSHOT_COLS_T2


# ---------------------------------------------------------------------------------------------
# P54 (DAI, 13-11-2026): a replaced row of the same period is not an evaluated attempt
# ---------------------------------------------------------------------------------------------
def test_p54_a_replaced_row_is_neither_a_unit_nor_history():
    e = episodios(ep(1, "p1"))
    it = intentos(("p1", 1, "201510", "A", 2.0, {"oportunidad": 1}), ("p1", 1, "201510", "A", 5.0, {"oportunidad": 2}),
                  ("p1", 1, "201520", "A", 5.0, {"oportunidad": 3}))
    it["aprobado_curricular"] = it["aprobado_curricular"].astype(object)
    it.loc[0, "es_intento_evaluado"] = False                                        # what build_core writes (P54)
    it.loc[0, "aprobado_curricular"] = None
    it["reemplazada_mismo_periodo"] = [True, False, False]
    snap, _ = construir(e, it)
    assert sorted(zip(snap["periodo"], snap["codigo_asignatura"], snap["y"])) == [("201510", "A", 0), ("201520", "A", 0)]
    r = fila(snap, "p1", "201520", "A")
    assert r["n_intentos_acum"] == 1 and r["n_reprob_acum"] == 0           # the replaced failure is not history
