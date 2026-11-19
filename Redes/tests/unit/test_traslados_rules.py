"""Pure rules of the program-transfer mart (D48-D52, P61): classification of one origin -> destination transition."""
import pytest

from pipelines.marts import rules_traslados as RT


def clasif(**kw):
    base = dict(cod_origen="C101", cod_destino="C201", cod_admision_destino="LS", clase_origen="salida",
                primer_origen="201910", ultimo_origen="201920", primer_destino="202010")
    base.update(kw)
    return RT.clasificar(**base)


def rel(**kw):
    base = dict(cod_origen="C101", cod_destino="C201", cod_admision_destino="LS", clase_origen="salida",
                primer_origen="201910", ultimo_origen="201920", primer_destino="202010")
    base.update(kw)
    return RT.relacion_sin_traslado(**base)


def test_the_types_and_which_ones_count_as_abandonment():
    # P69 (DAI, 13-11-2026): studying something else after graduating is NOT a transfer, so it is not a type
    assert set(RT.TIPOS) == {"eleccion_especialidad", "cambio_ciclo", "cambio_carrera", "traslado_sede", "traslado_otro"}
    assert RT.CUENTA_ABANDONO == {"eleccion_especialidad": False, "cambio_ciclo": False, "cambio_carrera": True,
                                  "traslado_sede": True, "traslado_otro": True}
    assert set(RT.RELACIONES_SIN_TRASLADO) == {"continuacion_estudios", "doble_programa", "superposicion_con_baja"}


@pytest.mark.parametrize("ultimo,primer,esperado", [
    ("201920", "202010", 1), ("201920", "201920", 0), ("201910", "202010", 2), ("201920", "201910", -1),
    ("201910", "201915", 1), ("201920", "202025", 3), (None, "202010", None), ("201920", "x", None),
])
def test_gap_is_counted_in_regular_slots(ultimo, primer, esperado):
    assert RT.brecha(ultimo, primer) == esperado


def test_a_change_of_degree_inside_the_window_is_abandonment_of_the_origin():
    assert clasif(cod_admision_destino="CC") == "cambio_carrera"
    assert clasif(cod_admision_destino="CS") == "traslado_sede"
    assert clasif(cod_admision_destino="LS") == "traslado_otro"
    assert clasif(cod_admision_destino="NN") == "traslado_otro"


def test_same_program_is_never_a_transfer():
    assert clasif(cod_destino="C101") is None


def test_exchange_programs_are_out_on_either_side():
    assert clasif(cod_origen="0003") is None and clasif(cod_destino="0006") is None


@pytest.mark.parametrize("primer,esperado", [("201920", "traslado_otro"), ("202010", "traslado_otro"),
                                              ("202020", "traslado_otro"), ("202110", None), ("201910", None)])
def test_only_destinations_that_start_zero_to_two_slots_after_the_last_period_count(primer, esperado):
    # origin last period 201920: gap 0, 1, 2 inside; 3 and -2 outside
    assert clasif(primer_destino=primer) == esperado


def test_plan_comun_to_an_engineering_specialty_is_a_specialty_election_not_a_loss():
    for pc in ("8633", "8643"):
        assert clasif(cod_origen=pc, cod_destino="8553", primer_origen="201910", ultimo_origen="201920",
                      primer_destino="202010", cod_admision_destino="ES") == "eleccion_especialidad"
        # the D47 rule does not need ES nor the same admission period
        assert clasif(cod_origen=pc, cod_destino="8553", primer_origen="201910", ultimo_origen="201920",
                      primer_destino="202010", cod_admision_destino="LS") == "eleccion_especialidad"


def test_d47_window_is_two_regular_periods_after_the_last_plan_comun_period():
    kw = dict(cod_origen="8643", cod_destino="8553", primer_origen="201910", ultimo_origen="201920",
              cod_admision_destino="LS")
    assert clasif(primer_destino="202020", **kw) == "eleccion_especialidad"      # +2
    assert clasif(primer_destino="202110", **kw) is None                         # +3 is outside D47 and the window


def test_d47_may_start_before_the_last_plan_comun_period_but_never_before_its_first():
    kw = dict(cod_origen="8643", cod_destino="8553", ultimo_origen="202010", cod_admision_destino="LS",
              primer_origen="201910")
    assert clasif(primer_destino="201920", **kw) == "eleccion_especialidad"      # starts while Plan Comun records
    assert clasif(primer_destino="201910", **kw) is None                         # not later than the Plan Comun


def test_plan_comun_to_a_non_engineering_program_is_a_normal_transfer():
    assert clasif(cod_origen="8643", cod_destino="C201", cod_admision_destino="CC") == "cambio_carrera"


def test_other_plan_comun_programs_use_the_es_admission_code():
    assert clasif(cod_origen="8496", cod_destino="8403", cod_admision_destino="ES") == "eleccion_especialidad"


def test_p69_graduates_who_study_something_else_are_not_a_transfer_but_keep_a_note():
    assert clasif(clase_origen="egreso_titulacion") is None
    assert clasif(clase_origen="egreso_titulacion", cod_admision_destino="CC") is None
    assert rel(clase_origen="egreso_titulacion") == "continuacion_estudios"
    assert rel(clase_origen="egreso_titulacion", cod_admision_destino="CC") == "continuacion_estudios"
    assert rel(clase_origen="salida") is None                                   # an ordinary transfer has no such note


def test_state_d_in_the_origin_is_a_cycle_change():
    assert clasif(clase_origen="cambio_ciclo") == "cambio_ciclo"


def test_every_type_returned_is_declared():
    for adm in ("CC", "CS", "LS", "ES"):
        for clase in ("salida", "matricula", "egreso_titulacion", "cambio_ciclo"):
            t = clasif(cod_admision_destino=adm, clase_origen=clase)
            assert t is None or t in RT.TIPOS                      # None: P69, a continuation after graduating


# ---- P64 (DAI, 13-11-2026): simultaneous programs ------------------------------------------------------------------------
def test_p64_overlapping_episodes_without_a_baja_are_a_double_program_not_a_transfer():
    kw = dict(primer_origen="201910", ultimo_origen="202020", primer_destino="201920")     # destination starts inside the origin
    for clase in ("matricula", "egreso_titulacion", "reingreso", "interrupcion"):
        assert clasif(clase_origen=clase, **kw) is None
        assert rel(clase_origen=clase, **kw) == "doble_programa"


def test_p64_a_baja_in_the_origin_of_an_overlap_is_an_exit_of_that_program_not_a_transfer():
    kw = dict(primer_origen="201910", ultimo_origen="202020", primer_destino="201920")
    assert clasif(clase_origen="salida", **kw) is None
    assert rel(clase_origen="salida", **kw) == "superposicion_con_baja"


def test_p64_the_overlap_needs_two_different_undergraduate_programs():
    kw = dict(primer_origen="201910", ultimo_origen="202020", primer_destino="201920")
    assert rel(cod_destino="C101", **kw) is None
    assert rel(cod_origen="0003", **kw) is None and rel(cod_destino="0006", **kw) is None


def test_p64_the_gap_decides_overlap_versus_transfer_window():
    # gap -1 (starts one slot before the origin ends) = overlap; 0 and 2 = the transfer window; 3 = neither
    assert rel(ultimo_origen="201920", primer_destino="201910") == "superposicion_con_baja"
    assert rel(ultimo_origen="201920", primer_destino="201920") is None
    assert clasif(ultimo_origen="201920", primer_destino="201920") == "traslado_otro"
    assert rel(ultimo_origen="201920", primer_destino="202110") is None


def test_p64_the_d47_specialty_link_is_never_a_double_program():
    assert rel(cod_origen="8643", cod_destino="8553", primer_origen="201910", ultimo_origen="202010",
               primer_destino="201920", cod_admision_destino="LS") is None
