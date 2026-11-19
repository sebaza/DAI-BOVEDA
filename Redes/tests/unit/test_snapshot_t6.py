"""T6 snapshot ("matricula en postgrado UCN despues del egreso", docs/12_benchmark_t6.md): pure rules (label, censoring,
exclusion of a postgraduate enrollment that precedes the egress), funnel, point-in-time features and the perturbation
leakage guards. No database."""
import itertools

import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from pipelines.marts.rules import base_ordinal                    # noqa: E402
from pipelines.snapshots import features_t3 as F3                  # noqa: E402
from pipelines.snapshots import features_t6 as F6                  # noqa: E402
from pipelines.snapshots import rules_t3 as R3                     # noqa: E402
from pipelines.snapshots import rules_t6 as R6                     # noqa: E402
from tests.unit.test_snapshot_t3 import (                          # noqa: E402
    LATEST, MALLA, NO_EGRESO, NO_INTENTOS, NO_VIA, PROG_CAT, ep, episodios, estados, intentos, matriculado, per)

ADM = "201610"          # cohort 2016, base ordinal 4032; slot j <-> ordinal 4031 + j; LATEST 202620 -> last closed slot 21
ORD_CIERRE = 4052       # 202610


def periodo_pg(adm: str, j: int) -> str:
    """Postgraduate period (50 = first semester, 60 = second) that falls in slot ``j`` of an admission period."""
    o = base_ordinal(adm) + j - 1
    return f"{o // 2}{'50' if o % 2 == 0 else '60'}"


def postgrado(*rows):
    """(persona, slot, matriculado, programa)."""
    cols = ["persona_key", "cod_programa", "periodo", "estado_matricula", "cod_estado"]
    return pd.DataFrame([{"persona_key": p, "cod_programa": prog, "periodo": periodo_pg(ADM, j),
                          "estado_matricula": "MATRICULADO" if m else "NO MATRICULADO", "cod_estado": "M" if m else "W"}
                         for p, j, m, prog in rows], columns=cols)


NO_POSTGRADO = postgrado()


def construir6(e, s, a=NO_INTENTOS, pg=NO_POSTGRADO, egreso=NO_EGRESO, malla=MALLA, prog_cat=PROG_CAT, latest=LATEST):
    return F6.construir_snapshot_t6(e, s, a, NO_VIA, egreso, malla, prog_cat, pg, latest)


def fila(snap, eid):
    r = snap[snap["episodio_id"] == eid]
    assert len(r) == 1, (eid, len(r))
    return r.iloc[0]


# ---------------------------------------------------------------------------------------------
# pure rules
# ---------------------------------------------------------------------------------------------
def test_postgraduate_periods_map_to_the_calendar_semester():
    assert R6.ordinal_postgrado("202650") == 4052 and R6.ordinal_postgrado("202660") == 4053
    assert R6.ordinal_postgrado("201650") == R6.ORDINAL_INICIO_FUENTE == 4032
    for malo in ("202610", "202620", "20265", None, "abcdef", "201615"):
        assert R6.ordinal_postgrado(malo) is None


def test_the_closed_limit_is_the_last_closed_regular_period():
    assert R6.ordinal_cierre("202620") == ORD_CIERRE        # the 60 period of 2026 is NOT closed
    assert R6.ordinal_cierre("202610") == 4051


def test_split_is_by_year_of_egress():
    assert [R6.split_egreso(a) for a in (2019, 2022, 2023, 2024, 2026)] == ["train", "train", "valid", "test", "test"]
    assert R6.HORIZONTES == (2, 4, 8)


@pytest.mark.parametrize("args,esperado", [
    # ord_egreso, ord_primera_matricula, ord_cierre
    ((4037, 4040, ORD_CIERRE), ("evento", 3, 1)),                       # enrolled 3 semesters after the egress
    ((4037, None, ORD_CIERRE), ("censurado", 15, 0)),                   # never: censored at the last closed period
    ((4037, 4037, ORD_CIERRE), ("previo", None, None)),                 # same semester as the egress: concurrent
    ((4037, 4030, ORD_CIERRE), ("previo", None, None)),                 # before
    ((4037, 4038, ORD_CIERRE), ("evento", 1, 1)),                       # the next semester is the first at risk
    ((4037, 4052, ORD_CIERRE), ("evento", 15, 1)),                      # exactly at the limit is observed
    ((4037, 4053, ORD_CIERRE), ("censurado", 15, 0)),                   # beyond the closed limit: not observed
    ((4051, 4052, ORD_CIERRE), ("evento", 1, 1)),
    ((4052, None, ORD_CIERRE), ("sin_seguimiento", None, None)),        # egress in the last closed period: no follow-up
    ((4052, 4053, ORD_CIERRE), ("sin_seguimiento", None, None)),
    ((4031, None, ORD_CIERRE), ("antes_de_la_fuente", None, None)),     # the source starts at 201650 (ordinal 4032)
    ((4031, 4020, ORD_CIERRE), ("antes_de_la_fuente", None, None)),
    ((4032, None, ORD_CIERRE), ("censurado", 20, 0)),
])
def test_resolution_of_the_event(args, esperado):
    assert R6.resolver_evento(*args) == esperado


def test_prior_enrollment_wins_over_follow_up_and_the_source_start_wins_over_everything():
    assert R6.resolver_evento(4052, 4050, ORD_CIERRE)[0] == "previo"
    assert R6.resolver_evento(4031, 4031, ORD_CIERRE)[0] == "antes_de_la_fuente"


def test_vectorized_resolution_equals_the_scalar_rule_on_a_grid():
    egresos = [4020, 4031, 4032, 4037, 4051, 4052, 4053]
    primeras = [None, 4010, 4032, 4037, 4038, 4045, 4052, 4053]
    filas = list(itertools.product(egresos, primeras))
    d = pd.DataFrame({"ord_egreso": [a for a, _ in filas], "ord_primera": [np.nan if b is None else b for _, b in filas]})
    v = F6.resolver_estados(d, ORD_CIERRE)
    for i, (a, b) in enumerate(filas):
        est, t, ev = R6.resolver_evento(a, b, ORD_CIERRE)
        assert v.loc[i, "estado"] == est
        if est in ("evento", "censurado"):
            assert (v.loc[i, "tiempo"], v.loc[i, "evento"]) == (t, ev)


def test_horizon_outcome_uses_only_rows_followed_up_to_the_horizon():
    tiempo = np.array([3, 3, 15, 1, 9])
    evento = np.array([1, 0, 0, 1, 1])
    seg = np.array([15, 3, 15, 1, 15])
    elegible, y = R6.resultado_horizonte(tiempo, evento, seg, 4)
    assert elegible.tolist() == [True, False, True, False, True]
    assert y.tolist() == [1, 0, 0, 1, 0]


def test_viability_gate_counts_events_per_split():
    assert R6.viable({"train": 50, "valid": 34, "test": 58})
    assert not R6.viable({"train": 15, "valid": 32, "test": 8})
    assert not R6.viable({"train": 50, "valid": 34})                      # a missing split is not viable
    assert R6.viable({"train": 30, "valid": 30, "test": 30})
    assert not R6.viable({"train": 29, "valid": 30, "test": 30})
    assert R6.MIN_EVENTOS_CLASICO == 30 and R6.MIN_EVENTOS_CATBOOST > R6.MIN_EVENTOS_CLASICO


# ---------------------------------------------------------------------------------------------
# a small world: one unit per situation
# ---------------------------------------------------------------------------------------------
def mundo():
    adm = ADM
    eps, est, pg = [], [], []

    def unidad(i, egreso_slot=6, hasta=None, adm_=adm):
        eps.append(ep(i, adm=adm_))
        est.extend(matriculado(i, adm_, 1, (egreso_slot - 1) if hasta is None else hasta))
        if egreso_slot is not None:
            est.append((f"p{i}", i, per(adm_, egreso_slot), "Z"))

    unidad(1); pg.append(("p1", 9, True, "PG1"))                            # event 3 semesters after the egress
    unidad(2)                                                                # no postgraduate: censored
    unidad(3); pg.append(("p3", 4, True, "PG1"))                            # enrolled DURING the undergraduate episode
    unidad(4); pg.append(("p4", 6, True, "PG1"))                            # enrolled in the egress semester
    unidad(5); pg.append(("p5", 0, True, "PG1"))                            # enrolled BEFORE the admission
    unidad(6); pg.append(("p6", 8, False, "PG1"))                           # a row, but not enrolled
    unidad(7); pg += [("p7", 8, True, "PG2"), ("p7", 10, True, "PG1")]      # two programs: the first enrollment counts
    unidad(8, egreso_slot=20, hasta=19); pg.append(("p8", 21, True, "PG1"))  # egress one semester before the limit
    unidad(9, egreso_slot=21, hasta=20)                                      # egress in the last closed period: no follow-up
    eps.append(ep(10)); est.extend(matriculado(10, adm, 1, 3)); est.append(("p10", 10, per(adm, 4), "E"))   # no egress
    eps.append(ep(11)); est.extend(matriculado(11, adm, 1, 21)); est.append(("p11", 11, "202620", "Z"))    # egress in progress
    unidad(12); pg.append(("p12", 22, True, "PG1"))                          # enrolled in the period still open: censored
    eps.append(ep(13)); est.extend(matriculado(13, adm, 1, 4)); est.append(("p13", 13, per(adm, 5), "U"))   # titulado
    eps.append(ep(14, adm="201510")); est.extend(matriculado(14, "201510", 1, 1)); est.append(("p14", 14, per("201510", 2), "Z"))
    eps.append(ep(15, nivel=8)); est.extend(matriculado(15, adm, 1, 4))     # postgraduate episode: not a unit
    egreso = pd.DataFrame({"persona_key": ["p2"], "episodio_id": [2], "periodo": [per(adm, 6)]})   # a titulacion row at the egress
    return episodios(*eps), estados(*est), egreso, postgrado(*pg)


def test_labels_times_and_events():
    e, s, eg, pg = mundo()
    snap, embudo = construir6(e, s, pg=pg, egreso=eg)
    r = fila(snap, 1)
    assert (r["tiempo"], r["evento"], r["seguimiento"], r["semestres_a_egreso"]) == (3, 1, 15, 6)
    assert (fila(snap, 2)["tiempo"], fila(snap, 2)["evento"]) == (15, 0)
    assert (fila(snap, 6)["tiempo"], fila(snap, 6)["evento"]) == (15, 0)            # a non-enrolled row is not an enrollment
    assert (fila(snap, 6)["tiempo_cualquier_fila"], fila(snap, 6)["evento_cualquier_fila"]) == (2, 1)   # but it is in the sensitivity
    assert (fila(snap, 7)["tiempo"], fila(snap, 7)["evento"]) == (2, 1)             # the first enrollment of the person, any program
    assert (fila(snap, 8)["tiempo"], fila(snap, 8)["evento"], fila(snap, 8)["seguimiento"]) == (1, 1, 1)
    assert (fila(snap, 12)["tiempo"], fila(snap, 12)["evento"]) == (15, 0)          # the 60 period of 2026 is still open
    assert (fila(snap, 13)["seguimiento"], fila(snap, 13)["evento"]) == (16, 0)


def test_prior_and_concurrent_postgraduate_enrollments_are_excluded_and_counted():
    e, s, eg, pg = mundo()
    snap, embudo = construir6(e, s, pg=pg, egreso=eg)
    ids = set(snap["episodio_id"])
    assert {3, 4, 5} & ids == set()
    assert embudo["postgrado_previo_durante"] == 2 and embudo["postgrado_previo_antes"] == 1


def test_funnel_identity_and_population():
    e, s, eg, pg = mundo()
    snap, f = construir6(e, s, pg=pg, egreso=eg)
    assert f["poblacion"] == 14                                       # episode 15 (nivel) is out; 14 is cohort 2015
    assert f["sin_egreso"] == 2                                       # 10 (exit) and 11 (egress in the open period)
    assert f["egresados"] == f["poblacion"] - f["sin_egreso"] == 12
    assert f["egreso_antes_de_la_fuente"] == 1                        # episode 14
    assert f["sin_seguimiento"] == 1                                  # episode 9
    assert f["elegibles"] == len(snap) == 7 == f["egresados"] - f["egreso_antes_de_la_fuente"] - f["postgrado_previo_antes"] \
        - f["postgrado_previo_durante"] - f["sin_seguimiento"]
    assert f["eventos"] == int(snap["evento"].sum()) == 3
    assert sorted(snap["episodio_id"]) == [1, 2, 6, 7, 8, 12, 13]


def test_titulacion_u_by_the_cut():
    e, s, eg, pg = mundo()
    snap, _ = construir6(e, s, pg=pg, egreso=eg)
    assert bool(fila(snap, 13)["titulado_al_corte"]) is True           # state U in the egress slot
    assert bool(fila(snap, 2)["titulado_al_corte"]) is True            # a titulacion row in the egress slot
    assert bool(fila(snap, 1)["titulado_al_corte"]) is False           # Z only
    # a titulacion that happens AFTER the cut is the future: not known at the cut
    tarde = pd.DataFrame({"persona_key": ["p1"], "episodio_id": [1], "periodo": [per(ADM, 12)]})
    snap2, _ = construir6(e, s, pg=pg, egreso=pd.concat([eg, tarde], ignore_index=True))
    assert bool(fila(snap2, 1)["titulado_al_corte"]) is False


def test_program_duration_and_time_to_egress():
    e, s, eg, pg = mundo()
    snap, _ = construir6(e, s, pg=pg, egreso=eg)
    r = fila(snap, 1)
    assert r["duracion_nominal"] == 10 and r["semestres_a_egreso"] == 6
    assert r["exceso_duracion"] == -4 and r["razon_duracion"] == pytest.approx(0.6)


def test_split_follows_the_year_of_egress_not_the_cohort():
    e, s, eg, pg = mundo()
    snap, _ = construir6(e, s, pg=pg, egreso=eg)
    # slot 6 of 201610 is 201820 -> 2018: train; slot 20 = 202510 -> 2025: test
    assert fila(snap, 1)["anio_egreso"] == 2018 and fila(snap, 1)["split"] == "train"
    assert fila(snap, 8)["anio_egreso"] == 2025 and fila(snap, 8)["split"] == "test"
    assert fila(snap, 1)["cohorte_anio"] == 2016


def test_sex_cohort_year_and_labels_are_not_features():
    assert "sexo_equidad" in F6.SNAPSHOT_COLS_T6
    nofeat = {"sexo_equidad", "cohorte_anio", "anio_egreso", "split", "persona_key", "episodio_id", *F6.LABEL_COLS_T6}
    assert not nofeat & set(F6.FEATURE_COLS_T6)
    assert {"seguimiento", "tiempo", "evento", "tiempo_cualquier_fila", "evento_cualquier_fila"} <= F6.LABEL_COLS_T6
    assert "episodio_especialidad_id" in F6.LABEL_COLS_T6


# ---------------------------------------------------------------------------------------------
# leakage guards
# ---------------------------------------------------------------------------------------------
def _sintetico6(seed=0, n=80):
    rng = np.random.default_rng(seed)
    adms = ["201510", "201520", "201610", "201710", "201810"]
    eps, est, filas, pg = [], [], [], []
    for i in range(n):
        adm = str(rng.choice(adms))
        eid = i + 1
        eps.append(ep(eid, adm=adm))
        ult = int(rng.integers(3, 11))
        est += matriculado(eid, adm, 1, ult)
        est.append((f"p{eid}", eid, per(adm, ult + 1), "Z"))
        for j in range(1, ult + 1):
            for c in rng.choice(list("ABCD"), size=int(rng.integers(0, 3)), replace=False):
                filas.append((eid, per(adm, j), float(np.round(rng.uniform(2, 7), 1)), str(c)))
        if rng.random() < 0.4:
            o = base_ordinal(adm) + ult + int(rng.integers(1, 8))
            pg.append((f"p{eid}", f"{o // 2}{'50' if o % 2 == 0 else '60'}"))
    pgdf = pd.DataFrame([{"persona_key": p, "cod_programa": "PG1", "periodo": per_, "estado_matricula": "MATRICULADO",
                          "cod_estado": "M"} for p, per_ in pg],
                        columns=["persona_key", "cod_programa", "periodo", "estado_matricula", "cod_estado"])
    return episodios(*eps), estados(*est), intentos(*filas), pgdf


FEATURES = F6.FEATURE_COLS_T6


def _comparar(a, b):
    a, b = a.set_index("episodio_id"), b.set_index("episodio_id")
    comunes = a.index.intersection(b.index)
    assert len(comunes) > 40
    for c in FEATURES:
        x, y = a.loc[comunes, c], b.loc[comunes, c]
        assert ((x == y) | (x.isna() & y.isna())).all(), c
    return comunes


def test_changing_facts_after_the_egress_never_changes_the_features():
    e, s, a, pg = _sintetico6()
    base, _ = construir6(e, s, a, pg)
    rng = np.random.default_rng(9)
    adm = e.set_index("episodio_id")["periodo_admision"]
    k = base.set_index("episodio_id")["semestres_a_egreso"]
    corte = lambda eid: per(adm[eid], int(k[eid]))                                  # noqa: E731
    a2 = a.copy()
    lim = a2["episodio_id"].map(lambda i: corte(i) if i in k.index else "999999")
    tarde = a2["periodo"] > lim
    a2.loc[tarde, "nota_numerica"] = rng.uniform(1, 7, int(tarde.sum())).round(1)
    a2.loc[tarde, "aprobado_curricular"] = a2.loc[tarde, "nota_numerica"] >= 4.0
    s2 = s.copy()
    lim_s = s2["episodio_id"].astype(int).map(lambda i: corte(i) if i in k.index else "999999")
    s2 = s2.loc[~(s2["periodo"] > lim_s) | (rng.random(len(s2)) < 0.5)].copy()       # drop half of the later states
    extra = estados(*[(f"p{i}", i, per(adm[i], int(k[i]) + 1), "E") for i in k.index[::3]])
    s2 = pd.concat([s2, extra], ignore_index=True)
    # the postgraduate history is the label side: redraw it completely
    pg2 = pg.copy()
    pg2["periodo"] = [periodo_pg(ADM, int(rng.integers(8, 22))) for _ in range(len(pg2))]
    pert, _ = construir6(e, s2, a2, pg2)
    comunes = _comparar(base, pert)
    assert len(comunes) >= 0.5 * len(base)
    m = base.set_index("episodio_id").loc[comunes], pert.set_index("episodio_id").loc[comunes]
    assert (m[0]["tiempo"].to_numpy() != m[1]["tiempo"].to_numpy()).any()           # the perturbation did change labels


def test_deleting_all_later_periods_never_changes_the_features():
    e, s, a, pg = _sintetico6(seed=4)
    base, _ = construir6(e, s, a, pg)
    adm = e.set_index("episodio_id")["periodo_admision"]
    k = base.set_index("episodio_id")["semestres_a_egreso"]
    todos = {i: per(adm[i], int(k[i])) for i in k.index}
    lim_s = s["episodio_id"].astype(int).map(lambda i: todos.get(i, "999999"))
    corto_s = s.loc[s["periodo"] <= lim_s].reset_index(drop=True)
    lim_a = a["episodio_id"].map(lambda i: todos.get(i, "999999"))
    corto_a = a.loc[a["periodo"] <= lim_a].reset_index(drop=True)
    corto, _ = construir6(e, corto_s, corto_a, pg)
    assert set(base["episodio_id"]) == set(corto["episodio_id"])
    _comparar(base, corto)


def test_the_guard_can_fail_a_pre_cut_fact_does_change_the_features():
    e, s, a, pg = _sintetico6(seed=2)
    base, _ = construir6(e, s, a, pg)
    adm = e.set_index("episodio_id")["periodo_admision"]
    a2 = a.copy()
    pre = a2["periodo"] <= a2["episodio_id"].map(adm).map(lambda p: per(p, 2))
    a2.loc[pre, "nota_numerica"] = 7.0
    a2.loc[pre, "aprobado_curricular"] = True
    pert, _ = construir6(e, s, a2, pg)
    with pytest.raises(AssertionError):
        _comparar(base, pert)


def test_postgraduate_rows_never_reach_a_feature():
    """Removing the whole postgraduate history changes the eligible set (nothing is excluded any more) but no feature."""
    e, s, a, pg = _sintetico6(seed=5)
    con, _ = construir6(e, s, a, pg)
    sin, _ = construir6(e, s, a, NO_POSTGRADO)
    assert (sin["evento"] == 0).all() and len(sin) >= len(con)
    _comparar(con, sin)


# ---------------------------------------------------------------------------------------------
# table preparation and hash (builder without a database)
# ---------------------------------------------------------------------------------------------
def test_tables_are_typed_for_copy_and_the_hash_depends_on_the_label():
    from pipelines.snapshots import t6 as T6

    e, s, eg, pg = mundo()
    snap, _ = construir6(e, s, pg=pg, egreso=eg)
    t = T6.preparar_tabla(snap)
    assert list(t.columns) == F6.SNAPSHOT_COLS_T6
    assert t["episodio_especialidad_id"].map(lambda v: v is None or isinstance(v, int)).all()
    for c in ("episodio_id", "tiempo", "evento", "seguimiento", "anio_egreso", "semestres_a_egreso"):
        assert str(t[c].dtype) == "int64"
    h0 = T6.hash_snapshot(snap)
    assert h0 == T6.hash_snapshot(snap.copy()) and len(h0) == 64
    cambiado = snap.copy()
    cambiado.loc[cambiado.index[0], "evento"] = 1 - cambiado.loc[cambiado.index[0], "evento"]
    assert T6.hash_snapshot(cambiado) != h0


def test_summary_counts_by_split_and_event():
    from pipelines.snapshots import t6 as T6

    e, s, eg, pg = mundo()
    snap, _ = construir6(e, s, pg=pg, egreso=eg)
    r = T6.resumen_filas(snap)
    assert set(r.columns) == {"split", "evento", "n"} and r["n"].sum() == len(snap)


# ---------------------------------------------------------------------------------------------
# P77 / P78 / P80 (DAI, 13-11-2026): event and level from the postgrado STATE source (ban_estados_academicos_pos)
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("args,esperado", [
    # ord_egreso, [(ordinal, nivel)], ord_cierre -> (previo, evento, tiempo, nivel)
    ((4037, [], ORD_CIERRE), (False, 0, 15, None)),
    ((4037, [(4040, "magister")], ORD_CIERRE), (False, 1, 3, "magister")),
    ((4037, [(4037, "magister"), (4040, "magister")], ORD_CIERRE), (True, 1, 3, "magister")),   # concurrent: flagged, still timed
    ((4037, [(4030, "doctorado")], ORD_CIERRE), (True, 0, 15, None)),
    ((4037, [(4053, "magister")], ORD_CIERRE), (False, 0, 15, None)),                           # beyond the closed limit
    ((4037, [(4052, "diplomado")], ORD_CIERRE), (False, 1, 15, "diplomado")),                   # exactly at the limit
    ((4037, [(4040, "magister"), (4040, "doctorado")], ORD_CIERRE), (False, 1, 3, "doctorado")),   # level priority
    ((4037, [(4039, "otro"), (4041, "doctorado")], ORD_CIERRE), (False, 1, 2, "otro")),           # the FIRST semester decides
])
def test_p77_event_from_the_state_source(args, esperado):
    assert R6.resolver_evento_estados(*args) == esperado


def test_p77_levels_have_a_priority_and_unknown_names_count_as_otro():
    assert R6.NIVELES_ESTADOS == ("doctorado", "magister", "diplomado", "otro")
    assert R6.nivel_evento(["otro", "diplomado"]) == "diplomado"
    assert R6.nivel_evento(["sin_nombre"]) == "otro"
    assert R6.nivel_evento([]) is None


def estados_pos(*rows):
    """(persona, slot, cod_estado, programa)."""
    cols = ["persona_key", "cod_programa", "periodo", "cod_estado"]
    return pd.DataFrame([{"persona_key": p, "cod_programa": prog, "periodo": periodo_pg(ADM, j), "cod_estado": c}
                         for p, j, c, prog in rows], columns=cols)


NIVELES_POS = pd.DataFrame({"cod_programa": ["MG", "DR", "OT"], "nivel_derivado": ["magister", "doctorado", "sin_nombre"]})


def _mundo_estados():
    e = episodios(ep(1, "pa"), ep(2, "pb"), ep(3, "pc"), ep(4, "pd"))
    s = estados(*[x for i, p in ((1, "pa"), (2, "pb"), (3, "pc"), (4, "pd")) for x in matriculado(i, ADM, 1, 8, persona=p)],
                *[(p, i, per(ADM, 9), "G") for i, p in ((1, "pa"), (2, "pb"), (3, "pc"), (4, "pd"))])
    return e, s


def test_p77_the_snapshot_carries_the_event_the_level_and_the_prior_flag_from_the_state_source():
    e, s = _mundo_estados()
    pos = estados_pos(("pa", 12, "M", "MG"),                      # 3 semesters after the egreso (slot 9), magister
                      ("pb", 9, "M", "DR"), ("pb", 11, "M", "DR"),  # concurrent with the egreso semester: previo
                      ("pc", 12, "J", "MG"),                      # J = Matricula en Tramite is NOT enrolled
                      ("pd", 12, "W", "MG"))                      # W = Post-Graduado is NOT enrolled
    snap, emb = F6.construir_snapshot_t6(e, s, NO_INTENTOS, NO_VIA, NO_EGRESO, MALLA, PROG_CAT, NO_POSTGRADO, LATEST,
                                         estados_pos=pos, programas_pos=NIVELES_POS)
    a, b, c, d = (fila(snap, i) for i in (1, 2, 3, 4))
    assert (a["evento_estados"], a["tiempo_estados"], a["nivel_estados"], bool(a["previo_estados"])) == (1, 3, "magister", False)
    assert bool(b["previo_estados"]) and b["evento_estados"] == 1 and b["tiempo_estados"] == 2 and b["nivel_estados"] == "doctorado"
    assert (c["evento_estados"], c["nivel_estados"], bool(c["previo_estados"])) == (0, None, False)
    assert (d["evento_estados"], d["nivel_estados"]) == (0, None)
    assert c["tiempo_estados"] == c["seguimiento"] == d["tiempo_estados"]
    assert emb["eventos_estados"] == 2 and emb["previo_estados"] == 1


def test_p77_the_legacy_label_columns_do_not_change_when_the_state_source_is_added():
    e, s = _mundo_estados()
    pg = postgrado(("pa", 12, True, "P9"))
    sin, _ = construir6(e, s, pg=pg)
    con, _ = F6.construir_snapshot_t6(e, s, NO_INTENTOS, NO_VIA, NO_EGRESO, MALLA, PROG_CAT, pg, LATEST,
                                      estados_pos=estados_pos(("pb", 12, "M", "MG")), programas_pos=NIVELES_POS)
    for col in ("tiempo", "evento", "seguimiento", "tiempo_cualquier_fila", "evento_cualquier_fila"):
        assert (sin[col].to_numpy() == con[col].to_numpy()).all()
    assert (sin["evento_estados"] == 0).all() and not sin["previo_estados"].any()          # no state source: nothing observed


def test_p77_state_source_columns_are_label_side_and_in_the_snapshot_columns():
    for c in ("previo_estados", "evento_estados", "tiempo_estados", "nivel_estados"):
        assert c in F6.SNAPSHOT_COLS_T6 and c in F6.LABEL_COLS_T6 and c not in F6.FEATURE_COLS_T6
