from datetime import datetime, timezone

import pytest

from pipelines.normalize.catalog import (
    classify_programa,
    classify_prereq_edge,
    codigo_asignatura,
    dedupe_prereq,
    detect_hito,
    is_takeable,
    prereq_graph,
)
from pipelines.normalize.cargas import epoch_ms_to_datetime, pick_vigente
from pipelines.normalize.sections import SeccionIndex, link_intento_to_section, titulacion_key


# ---- aa: course code --------------------------------------------------------
def test_aa_materia_curso_joins_with_hyphen():
    assert codigo_asignatura("ABCD", "01000").codigo == "ABCD-01000"
    assert codigo_asignatura(" abcd ", "01000").codigo == "ABCD-01000"


def test_aa_nonstandard_formats_are_marked_not_dropped():
    c = codigo_asignatura("ICI1", "02001")
    assert c.codigo == "ICI1-02001" and c.formato == "AAA9-99999"
    o = codigo_asignatura("AB", "1")
    assert o.codigo == "AB-1" and o.formato == "otro"
    assert codigo_asignatura("ABCD", "01000").formato == "AAAA-99999"


# ---- r: programs ------------------------------------------------------------
def test_r_invalid_program_and_missing_predecessor_are_kept_with_marks():
    ids = {1, 2, 3}
    ok = classify_programa(True, None, ids)
    assert not ok.programa_no_valido and not ok.predecesor_inexistente
    bad = classify_programa(False, 99, ids)
    assert bad.programa_no_valido and bad.predecesor_inexistente
    assert classify_programa(True, 2, ids).predecesor_inexistente is False


# ---- z / ak: prerequisites --------------------------------------------------
ROWS = [
    # (cod_programa, catalogo, codigo_asignatura, codigo_asignatura_repreq)
    ("P1", "2020", "MAT-00002", "MAT-00001"),
    ("P1", "2020", "MAT-00002", "MAT-00001"),
    ("P1", "2020", "MAT-00003", "MAT-00002"),
    ("P1", "2020", "FIS-00001", "XXX-99999"),
]


def test_z_duplicated_edges_collapse_and_keep_source_count():
    edges = dedupe_prereq(ROWS)
    assert len(edges) == 3
    e = next(x for x in edges if x.codigo_asignatura == "MAT-00002")
    assert e.codigo_requisito == "MAT-00001" and e.filas_origen == 2


def test_z_edge_classification_keeps_edges_with_missing_nodes():
    malla_same = {"MAT-00001", "MAT-00002", "MAT-00003", "FIS-00001"}
    malla_other_cat = {"MAT-00001"}
    other_prog = {"XXX-99999"}
    edges = {e.codigo_requisito: e for e in dedupe_prereq(ROWS)}
    assert classify_prereq_edge(edges["MAT-00001"], malla_same, malla_other_cat, other_prog) == "misma_malla"
    assert classify_prereq_edge(edges["XXX-99999"], malla_same, set(), other_prog) == "otro_programa"
    assert classify_prereq_edge(edges["XXX-99999"], malla_same, {"XXX-99999"}, set()) == "otro_catalogo"
    assert classify_prereq_edge(edges["XXX-99999"], malla_same, set(), set()) == "ninguna"


def test_ak_direction_is_requirement_to_course_and_gates_taking():
    g = prereq_graph(dedupe_prereq(ROWS))
    assert ("MAT-00001", "MAT-00002") in g.edges  # A -> B
    assert ("MAT-00002", "MAT-00001") not in g.edges
    assert is_takeable("MAT-00002", g, approved={"MAT-00001"}) is True
    assert is_takeable("MAT-00002", g, approved=set()) is False
    assert is_takeable("MAT-00001", g, approved=set()) is True  # no prerequisites
    # inverted columns would make MAT-00001 depend on MAT-00002 and fail this:
    assert is_takeable("MAT-00001", g, approved={"MAT-00002"}) is True


# ---- hitos (RA29, versioned regex) -----------------------------------------
@pytest.mark.parametrize(
    "nombre,tipo",
    [
        ("PRACTICA PROFESIONAL I", "practica"),
        ("Práctica Intermedia", "practica"),
        ("CAPSTONE PROJECT", "capstone"),
        ("MEMORIA DE TITULO", "memoria"),
        ("SEMINARIO DE TITULO", "seminario"),
        ("PROYECTO DE TITULO", "proyecto"),
        ("CALCULO I", None),
    ],
)
def test_detect_hito_by_name(nombre, tipo):
    r = detect_hito(nombre)
    assert (r.tipo_hito if r else None) == tipo
    if r:
        assert r.metodo == "regex_nombre_v1" and r.validado is False


# ---- ab: vigente loads ------------------------------------------------------
def test_ab_picks_vigente_even_if_another_load_has_greater_timestamp():
    cargas = [
        {"timestamp_carga": 1_700_000_000_000, "vigente": True},
        {"timestamp_carga": 1_800_000_000_000, "vigente": False},
    ]
    assert pick_vigente(cargas)["timestamp_carga"] == 1_700_000_000_000


def test_ab_no_or_many_vigente_is_an_error_not_a_guess():
    with pytest.raises(ValueError):
        pick_vigente([{"timestamp_carga": 1, "vigente": False}])
    with pytest.raises(ValueError):
        pick_vigente([{"timestamp_carga": 1, "vigente": True}, {"timestamp_carga": 2, "vigente": True}])


def test_ab_epoch_ms_conversion():
    assert epoch_ms_to_datetime(1_700_000_000_000) == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)


# ---- x / y: sections and teachers ------------------------------------------
OFERTA = [
    ("202410", "1001", "DOC_A"),
    ("202410", "1001", "DOC_B"),
    ("202410", "1001", "DOC_C"),
    ("202410", "1001", "DOC_A"),  # repeated row
    ("202410", "1002", None),
]


def test_x_three_teachers_one_section_three_bridge_rows():
    idx = SeccionIndex.from_oferta(OFERTA)
    assert len(idx.secciones) == 2
    assert len([b for b in idx.puente if b[:2] == ("202410", "1001")]) == 3
    link = link_intento_to_section("202410", "1001", idx)
    assert link.tiene_seccion is True and len(link.docentes) == 3  # one intento -> one link object


def test_y_period_before_2016_has_null_teacher_and_flag():
    idx = SeccionIndex.from_oferta(OFERTA)
    link = link_intento_to_section("201510", "1001", idx)
    assert link.docentes is None and link.tiene_seccion is False
    assert link.anterior_a_oferta is True


def test_y_no_matching_section_after_2016_is_null_not_zero_teachers():
    idx = SeccionIndex.from_oferta(OFERTA)
    link = link_intento_to_section("202410", "9999", idx)
    assert link.docentes is None and link.anterior_a_oferta is False


# ---- ac: double graduation --------------------------------------------------
def test_ac_two_titulaciones_one_person_are_two_distinct_keys():
    k1 = titulacion_key("pk1", "C101", "2019", "2023-07-01")
    k2 = titulacion_key("pk1", "C202", "2020", "2024-07-01")
    assert k1 != k2 and k1[0] == k2[0] == "pk1"
