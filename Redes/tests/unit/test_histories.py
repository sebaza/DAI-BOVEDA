"""The three synthetic control histories run through the pure functions."""
from decimal import Decimal

from pipelines.normalize.assignment import assign_episode
from pipelines.normalize.catalog import detect_hito
from pipelines.normalize.grades import (
    approval_rate_by_attempt,
    average_grade,
    classify_historia,
)
from pipelines.normalize.timeline import build_timeline
from tests.fixtures import synthetic_histories as H

D = Decimal


def tl(estados):
    return build_timeline(estados, H.CORTE)


def assigned(timeline, nota):
    return assign_episode(nota.periodo, nota.cod_carrera, timeline.episodes)


# ---- history i --------------------------------------------------------------
def test_history_i_single_episode_straight_path():
    t = tl(H.HISTORY_I_ESTADOS)
    assert len(t.episodes) == 1
    ep = t.episodes[0]
    assert (ep.primer_periodo, ep.ultimo_periodo) == ("201910", "202120")
    assert ep.n_tramos == 1 and ep.n_estados == 8
    assert ep.ultimo_estado_clase == "egreso_titulacion"
    assert [e.estado.cod_estado for e in t.events] == list("NMMMMGKU")


def test_history_i_every_grade_lands_in_the_episode():
    t = tl(H.HISTORY_I_ESTADOS)
    results = [assigned(t, n) for n in H.HISTORY_I_NOTAS]
    assert all(r.episodio_key == t.episodes[0].key for r in results)


def test_history_i_grades_pass_and_fail_by_rule():
    res = [classify_historia(n.nota, n.comentario, n.oportunidad) for n in H.HISTORY_I_NOTAS]
    assert [r.aprobado_curricular for r in res] == [True, False, True, True, True]
    assert approval_rate_by_attempt(res) == (4, 5)


# ---- history ii -------------------------------------------------------------
def test_history_ii_two_episodes_and_reversal_ignored():
    t = tl(H.HISTORY_II_ESTADOS)
    assert len(t.episodes) == 2
    c201 = next(e for e in t.episodes if e.key.cod_programa == "C201")
    c305 = next(e for e in t.episodes if e.key.cod_programa == "C305")
    assert c305.key.cod_admision == "CC"
    assert c201.n_tramos == 1 and c201.no_contiguo is False
    rev = next(e for e in t.events if e.estado.cod_estado == "2")
    assert rev.es_correccion_sistema and rev.episodio_key is None
    assert c201.n_estados == 7  # N M M E I M M (reversal excluded)


def test_history_ii_order_continues_across_programs_and_uses_periodo_first():
    t = tl(H.HISTORY_II_ESTADOS)
    assert [e.orden_canonico for e in t.events] == list(range(1, 12))
    # sorlcur 22 has periodo 202115, so it sorts BEFORE sorlcur 21 (202120)
    sorlcurs = [e.estado.sorlcur for e in t.events]
    assert sorlcurs.index(22) < sorlcurs.index(21)
    # sorlcur is kept untouched and still strictly increases inside each program's states
    assert sorted(sorlcurs) == [1, 2, 3, 10, 11, 12, 13, 15, 20, 21, 22]


def test_history_ii_null_date_gets_interval_and_nothing_else():
    t = tl(H.HISTORY_II_ESTADOS)
    reintegro = next(e for e in t.events if e.estado.cod_estado == "I")
    assert reintegro.fecha.fecha_estado is None
    assert reintegro.fecha.fecha_aproximada is True
    assert reintegro.fecha.fecha_min == H.date(2019, 3, 20)
    assert reintegro.fecha.fecha_max == H.date(2020, 3, 9)
    assert len(t.events) == len(H.HISTORY_II_ESTADOS)


def test_history_ii_grade_assignment_follows_r36():
    t = tl(H.HISTORY_II_ESTADOS)
    by_key = {(n.periodo, n.materia, n.curso): assigned(t, n) for n in H.HISTORY_II_NOTAS}
    assert by_key[("201915", "QUI", "00002")].episodio_key.cod_programa == "C201"
    assert by_key[("202120", "ING", "00001")].episodio_key.cod_programa == "C305"
    old = by_key[("200510", "OLD", "00001")]
    assert old.episodio_key is None and old.sin_episodio is True and old.episodio_ambiguo is False


def test_history_ii_dpa_is_out_of_means_and_rates():
    results = [classify_historia(n.nota, n.comentario, n.oportunidad) for n in H.HISTORY_II_NOTAS]
    dpa = [r for r in results if r.resultado_tipo == "convalidacion"]
    assert len(dpa) == 1 and dpa[0].nota_numerica is None and dpa[0].aprobado_curricular is True
    non_dpa = [r for r in results if r.resultado_tipo != "convalidacion"]
    assert average_grade(results) == average_grade(non_dpa)
    assert approval_rate_by_attempt(results) == approval_rate_by_attempt(non_dpa)


# ---- history iii ------------------------------------------------------------
def test_history_iii_cycle_change_and_catalog_change_stay_one_episode():
    t = tl(H.HISTORY_III_ESTADOS)
    assert len(t.episodes) == 1
    ep = t.episodes[0]
    assert ep.catalogos == ("2017", "2018") and ep.n_tramos == 1
    d_event = next(e for e in t.events if e.estado.cod_estado == "D")
    assert d_event.info.clase_estado == "cambio_ciclo" and d_event.tramo_n == 1


def test_history_iii_conva_and_dpa_rows():
    res = {(n.materia, n.curso): classify_historia(n.nota, n.comentario, n.oportunidad) for n in H.HISTORY_III_NOTAS}
    conva = res[("FIS", "00003")]
    assert conva.nota_numerica == D("5.5") and conva.nota_es_heredada and not conva.es_intento_evaluado
    assert conva.aprobado_curricular is True
    dpa = res[("ALG", "00002")]
    assert dpa.nota_numerica is None and dpa.aprobado_curricular is True
    evaluated = [r for r in res.values() if r.es_intento_evaluado]
    assert average_grade(list(res.values())) == (D("5.5") + D("6.5") + D("4.0")) / 3
    assert len(evaluated) == 3


def test_history_iii_practicum_and_capstone_are_detected_by_name():
    found = {c: detect_hito(n) for c, n in H.HISTORY_III_COURSE_NAMES.items()}
    assert found["PRAC-04001"].tipo_hito == "practica"
    assert found["CAPS-04002"].tipo_hito == "capstone"
    assert found["ALG-00001"] is None
