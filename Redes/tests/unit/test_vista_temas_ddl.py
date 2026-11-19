"""Static checks on migration 032 (new blocks of "Lo que pasó" and the projection table)."""
from pathlib import Path

from pipelines.migrate import validate_sql

SQL = Path(__file__).resolve().parents[2] / "sql" / "core" / "032_vista_temas_proyeccion.sql"

BLOQUES_HISTORICOS = ["meta", "semestres", "siguieron", "por_facultad", "eliminados", "alcance",
                      "perfil_ingreso", "primer_semestre", "ramos_reprobados", "ramos_esperado", "cuellos_botella",
                      "semestre_malla", "causales_programa", "tiempo_egreso", "senales", "esperar_semestre"]
BLOQUES_PROYECCION = ["meta", "continuidad", "eliminacion", "egreso", "umbral"]


def test_032_passes_the_schema_guard_and_lists_every_block():
    texto = SQL.read_text(encoding="utf-8")
    validate_sql(texto, "032_vista_temas_proyeccion.sql")
    for b in BLOQUES_HISTORICOS + BLOQUES_PROYECCION:
        assert f"'{b}'" in texto, b
    assert "neural_mart.vista_proyeccion" in texto
    low = texto.lower()
    assert "persona_key" not in low and "episodio_id" not in low
