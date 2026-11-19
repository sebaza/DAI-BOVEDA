-- DAI Neural 007: the official malla (ban_malla_programa) repeats 5.233 of 29.614 (programa, catalogo, asignatura)
-- groups, and 5.199 of those repeats differ in some attribute (measured on neural_stg during Gate 2). The core keeps one row
-- per group (lowest semester, deterministic) and records how many source rows it stands for and whether they
-- disagreed, so nothing is merged silently. semestre_texto keeps the original label ('Semestre 09 CP', 'Año 01 CP').
-- Idempotent: safe to run more than once.

ALTER TABLE neural_core.asignatura_malla ADD COLUMN IF NOT EXISTS semestre_texto text;
ALTER TABLE neural_core.asignatura_malla ADD COLUMN IF NOT EXISTS filas_origen integer NOT NULL DEFAULT 1;
ALTER TABLE neural_core.asignatura_malla ADD COLUMN IF NOT EXISTS atributos_conflicto boolean NOT NULL DEFAULT false;
