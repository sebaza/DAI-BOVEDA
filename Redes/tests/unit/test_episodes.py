from datetime import date

from pipelines.normalize.assignment import assign_episode
from pipelines.normalize.models import EstadoRow
from pipelines.normalize.timeline import build_timeline

CORTE = date(2026, 11, 11)


def E(sorlcur, periodo, cod_estado="M", prog="P1", adm="LS", pa="201910", cat="2019", fecha=None):
    return EstadoRow(sorlcur, periodo, prog, cod_estado, adm, pa, cat, fecha)


def tl(rows):
    return build_timeline(rows, CORTE)


def test_n_cambio_de_ciclo_same_program_does_not_create_episode():
    t = tl([E(1, "201910"), E(2, "201920", "D"), E(3, "202010")])
    assert len(t.episodes) == 1
    assert [e.tramo_n for e in t.events] == [1, 1, 1]


def test_o_program_change_creates_new_episode_and_order_continues():
    t = tl(
        [
            E(1, "201910"),
            E(5, "202010", prog="P2", adm="CC", pa="202010"),
            E(9, "202020", prog="P2", adm="CC", pa="202010"),
        ]
    )
    assert len(t.episodes) == 2
    assert [e.orden_canonico for e in t.events] == [1, 2, 3]
    assert [e.sorlcur for e in (ev.estado for ev in t.events)] == [1, 5, 9]
    assert t.events[0].episodio_key != t.events[1].episodio_key
    assert t.events[1].episodio_key == t.events[2].episodio_key


def test_p_two_catalogs_still_one_episode():
    t = tl([E(1, "201910", cat="2019"), E(2, "202010", cat="2020"), E(3, "202110", cat="2020")])
    assert len(t.episodes) == 1
    ep = t.episodes[0]
    assert ep.catalogos == ("2019", "2020")
    assert (ep.catalogo_inicial, ep.catalogo_final) == ("2019", "2020")


def test_q_q_ah_non_contiguous_same_key_is_one_episode_with_tramos():
    t = tl(
        [
            E(1, "201910"),
            E(2, "201920"),
            E(3, "202010", prog="P2", adm="CC", pa="202010"),
            E(4, "202110"),  # back to P1 with the same key
            E(5, "202120"),
        ]
    )
    assert len(t.episodes) == 2
    p1 = next(e for e in t.episodes if e.key.cod_programa == "P1")
    assert p1.no_contiguo is True and p1.n_tramos == 2 and p1.n_estados == 4
    assert [ev.tramo_n for ev in t.events] == [1, 1, 1, 2, 2]
    p2 = next(e for e in t.episodes if e.key.cod_programa == "P2")
    assert p2.no_contiguo is False and p2.n_tramos == 1


def test_ah_consecutive_semesters_are_not_fragmented():
    t = tl([E(i + 1, p) for i, p in enumerate(["201910", "201920", "202010", "202020"])])
    assert len(t.episodes) == 1 and t.episodes[0].n_tramos == 1


def test_ah_null_admission_becomes_nn_flagged():
    t = tl([E(1, "201910", adm=None), E(2, "201920", adm=None)])
    ep = t.episodes[0]
    assert ep.key.cod_admision == "NN" and ep.cod_admision_imputado is True
    assert all(ev.cod_admision_imputado for ev in t.events)
    assert t.events[0].estado.cod_admision is None  # original preserved


def test_ag_reversal_after_terminal_state_is_flagged_and_changes_nothing():
    base = [E(1, "201910"), E(2, "202010", "G"), E(3, "202020", "K")]
    for code in ("1", "2", "5"):
        # the reversal row even carries a different program: it must not split anything
        t = tl(base + [E(4, "202020", code, prog="P9", adm="CC", pa="202020")])
        rev = t.events[-1]
        assert rev.es_correccion_sistema is True
        assert rev.episodio_key is None and rev.tramo_n is None
        assert len(t.episodes) == 1
        ep = t.episodes[0]
        assert ep.n_estados == 3 and ep.n_tramos == 1
        assert ep.ultimo_estado_clase == "egreso_titulacion"  # previous state still stands
        assert [e.cod_estado for e in (ev.estado for ev in t.events)] == ["M", "G", "K", code]


def test_ag_reversal_does_not_bridge_two_tramos():
    # P1 -> reversal (P1) -> P1 must stay a single tramo
    t = tl([E(1, "201910"), E(2, "201920", "1"), E(3, "202010")])
    assert t.episodes[0].n_tramos == 1


def test_episode_period_range_ignores_reversals():
    t = tl([E(1, "201910"), E(2, "202010"), E(3, "202110", "2")])
    ep = t.episodes[0]
    assert (ep.primer_periodo, ep.ultimo_periodo) == ("201910", "202010")


def test_unknown_and_null_codes_do_not_break_episodes():
    t = tl([E(1, "201910", None), E(2, "201920", "?"), E(3, "202010")])
    assert len(t.episodes) == 1
    assert t.events[0].info.sin_codigo and not t.events[1].info.conocido


def test_empty_history_gives_empty_timeline():
    t = tl([])
    assert t.events == [] and t.episodes == []


# ---- R36 assignment ---------------------------------------------------------
def _eps():
    t = tl(
        [
            E(1, "201910"),
            E(2, "202010"),
            E(3, "202020", prog="P2", adm="CC", pa="202020"),
            E(4, "202110", prog="P2", adm="CC", pa="202020"),
        ]
    )
    return t.episodes


def test_r36_single_candidate_is_assigned():
    a = assign_episode("201920", "P1", _eps())
    assert a.episodio_key is not None and a.episodio_key.cod_programa == "P1"
    assert (a.episodio_ambiguo, a.sin_episodio) == (False, False)


def test_r36_zero_candidates_is_sin_episodio():
    for periodo, prog in (("201810", "P1"), ("202120", "P1"), ("202010", "P9")):
        a = assign_episode(periodo, prog, _eps())
        assert a.episodio_key is None and a.sin_episodio is True and a.episodio_ambiguo is False


def test_r36_multiple_candidates_is_ambiguous_not_picked():
    eps = tl(
        [
            E(1, "201910"),
            E(2, "202010"),
            E(3, "202010", adm="CC", pa="202010"),  # same program, different key, overlapping range
            E(4, "202110", adm="CC", pa="202010"),
        ]
    ).episodes
    assert len(eps) == 2
    a = assign_episode("202010", "P1", eps)
    assert a.episodio_key is None and a.episodio_ambiguo is True and a.sin_episodio is False


def test_r36_range_bounds_are_inclusive():
    eps = _eps()
    assert assign_episode("201910", "P1", eps).episodio_key is not None
    assert assign_episode("202010", "P1", eps).episodio_key is not None
