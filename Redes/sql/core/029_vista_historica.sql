-- DAI Neural 029: executive view "Lo que pasó" (parte A: lo histórico). One row per block and filter ("Toda la UCN" or a faculty
-- name) with its content as JSON. Filled by `python tools/exportar_resumen_modelos.py` from artefactos/vista_historica.json
-- (gitignored), written by `python -m evaluation.vista_historica`.
-- AGGREGATES ONLY: counts and rates of groups of 10 or more people; no row-level prediction, no person key, no cell of 1-9 people.
-- Blocks: meta (filters, cohort ranges, models), semestres, siguieron, por_facultad (always under "Toda la UCN"), eliminados, alcance.
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.vista_historica (
    bloque    text        NOT NULL CHECK (bloque IN ('meta', 'semestres', 'siguieron', 'por_facultad', 'eliminados', 'alcance')),
    facultad  text        NOT NULL,
    contenido jsonb       NOT NULL,
    PRIMARY KEY (bloque, facultad)
);
