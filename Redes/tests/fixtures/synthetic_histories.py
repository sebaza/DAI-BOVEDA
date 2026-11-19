"""Three synthetic control histories (no real data, obviously fake RUTs).

(i)   admission -> enrollment -> courses -> degree
(ii)  elimination -> readmission -> real change of program (CC); also holds a
      reversal code, a NULL state date and rows out of ``sorlcur`` period order
(iii) internal cycle change (D, same program) + catalog change + practicum /
      capstone; also holds a DPA row and a CONVA row

``sorlcur`` is deliberately sparse, as in the real data.
"""
from __future__ import annotations

from datetime import date

from pipelines.normalize.models import EstadoRow, NotaRow

CORTE = date(2026, 11, 11)

RUT_I = "11111111-1"
RUT_II = "22222222-2"
RUT_III = "33333333-3"


# ---------------------------------------------------------------------------
# (i) straight path: ingreso -> matricula -> cursos -> titulo
# ---------------------------------------------------------------------------
def _e(sorlcur, periodo, cod, prog, adm, pa, cat, fecha=None):
    return EstadoRow(sorlcur, periodo, prog, cod, adm, pa, cat, fecha)


HISTORY_I_ESTADOS = [
    _e(1, "201910", "N", "C101", "LS", "201910", "2019", date(2019, 3, 4)),
    _e(2, "201910", "M", "C101", "LS", "201910", "2019", date(2019, 3, 5)),
    _e(4, "201920", "M", "C101", "LS", "201910", "2019", date(2019, 8, 1)),
    _e(6, "202010", "M", "C101", "LS", "201910", "2019", date(2020, 3, 2)),
    _e(9, "202020", "M", "C101", "LS", "201910", "2019", date(2020, 8, 3)),
    _e(15, "202110", "G", "C101", "LS", "201910", "2019", date(2021, 3, 1)),
    _e(20, "202120", "K", "C101", "LS", "201910", "2019", date(2021, 8, 2)),
    _e(40, "202120", "U", "C101", "LS", "201910", "2019", date(2021, 12, 15)),
]


def _n(periodo, cod, cat, materia, curso, nota, opor="1", nrc="1001", com="", cred=6):
    return NotaRow(periodo, cod, cat, materia, curso, nota, com, opor, nrc, cred)


HISTORY_I_NOTAS = [
    _n("201910", "C101", "2019", "MAT", "00001", "5,2"),
    _n("201910", "C101", "2019", "FIS", "00001", "3,9", nrc="1002"),
    _n("201920", "C101", "2019", "FIS", "00001", "4,0", opor="2", nrc="1002"),  # exact 4.0 passes on 2nd try
    _n("202010", "C101", "2019", "MAT", "00002", "4,1", nrc="1003"),
    _n("202020", "C101", "2019", "PRAC", "04001", "6,0", nrc="1004"),
]

# P54 (a person with grade rows only): three evaluated rows of ONE (persona, periodo, asignatura) in the same period: the last attempt (highest
# oportunidad) is the result even when it fails; the other two are replaced.
HISTORY_P54_NOTAS = [
    _n("201910", "C101", "2019", "ZZZ", "00001", "2,0", opor="1", nrc="1101"),
    _n("201910", "C101", "2019", "ZZZ", "00001", "5,0", opor="2", nrc="1102"),
    _n("201910", "C101", "2019", "ZZZ", "00001", "3,0", opor="3", nrc="1103"),
]

# ---------------------------------------------------------------------------
# (ii) eliminacion -> reintegro -> cambio real de carrera (CC)
# ---------------------------------------------------------------------------
HISTORY_II_ESTADOS = [
    _e(1, "201810", "N", "C201", "LS", "201810", "2018", date(2018, 3, 5)),
    _e(2, "201810", "M", "C201", "LS", "201810", "2018", date(2018, 3, 6)),
    _e(3, "201820", "M", "C201", "LS", "201810", "2018", date(2018, 8, 6)),
    _e(10, "201910", "E", "C201", "LS", "201810", "2018", date(2019, 3, 20)),
    _e(11, "202010", "I", "C201", "LS", "201810", "2018", None),                  # NULL date
    _e(12, "202010", "M", "C201", "LS", "201810", "2018", date(2020, 3, 9)),
    _e(13, "202010", "2", "C201", "LS", "201810", "2018", date(2020, 3, 10)),     # reversal code
    _e(15, "202020", "M", "C201", "LS", "201810", "2018", date(2020, 8, 10)),
    _e(20, "202110", "M", "C305", "CC", "202110", "2021", date(2021, 3, 8)),      # real program change
    _e(21, "202120", "M", "C305", "CC", "202110", "2021", date(2021, 8, 9)),
    # same person, written later but with an EARLIER period than sorlcur 21:
    _e(22, "202115", "M", "C305", "CC", "202110", "2021", date(2021, 7, 1)),
]

HISTORY_II_NOTAS = [
    _n("201810", "C201", "2018", "QUI", "00001", "4,5"),
    _n("201820", "C201", "2018", "QUI", "00002", "3,2", nrc="2001"),
    _n("201915", "C201", "2018", "QUI", "00002", "4,0", opor="2", nrc="2002"),   # summer course inside the episode
    _n("202020", "C201", "2018", "BIO", "00001", "5,0", nrc="2003"),
    _n("202110", "C305", "2021", "QUI", "00001", "DPA", nrc="0"),                 # DPA after the change
    _n("202120", "C305", "2021", "ING", "00001", "6,1", nrc="2004"),
    _n("200510", "C999", "2005", "OLD", "00001", "4,5", nrc="3000"),              # no episode for this program
]

# ---------------------------------------------------------------------------
# (iii) cambio de ciclo interno (D) + cambio de catalogo + practica/capstone
# ---------------------------------------------------------------------------
HISTORY_III_ESTADOS = [
    _e(1, "201710", "N", "C401", "LS", "201710", "2017", date(2017, 3, 6)),
    _e(2, "201710", "M", "C401", "LS", "201710", "2017", date(2017, 3, 7)),
    _e(5, "201720", "M", "C401", "LS", "201710", "2017", date(2017, 8, 7)),
    _e(8, "201810", "D", "C401", "LS", "201710", "2017", date(2018, 3, 5)),   # internal cycle change
    _e(9, "201810", "M", "C401", "LS", "201710", "2018", date(2018, 3, 6)),   # new catalog, same episode
    _e(14, "201820", "M", "C401", "LS", "201710", "2018", date(2018, 8, 6)),
    _e(25, "201910", "M", "C401", "LS", "201710", "2018", date(2019, 3, 4)),
    _e(30, "201920", "G", "C401", "LS", "201710", "2018", date(2019, 8, 5)),
]

HISTORY_III_NOTAS = [
    _n("201710", "C401", "2017", "ALG", "00001", "5,5"),
    _n("201810", "C401", "2018", "ALG", "00002", "DPA", nrc="0"),                       # convalidation
    _n("201810", "C401", "2018", "FIS", "00003", "5,5", nrc="4001", com="CONVA"),       # CONVA with inherited grade
    _n("201910", "C401", "2018", "PRAC", "04001", "6,5", nrc="4002"),                   # practicum
    _n("201910", "C401", "2018", "CAPS", "04002", "4,0", nrc="4003"),                   # capstone
]

HISTORY_III_COURSE_NAMES = {
    "PRAC-04001": "PRACTICA PROFESIONAL",
    "CAPS-04002": "CAPSTONE PROJECT",
    "ALG-00001": "ALGEBRA I",
}
