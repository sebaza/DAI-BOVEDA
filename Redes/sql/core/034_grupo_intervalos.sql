-- DAI Neural 034: every group with its 95 % intervals. Adds the bootstrap intervals of the model figures of a group
-- (AP, ROC-AUC, observed rate, expected rate) and the "pocos casos" mark (n < 10: a mark, never a filter), and opens
-- the level column to the other dimensions of the group tables (sex, admission route, school type).
-- Aggregates only: no person key, no name, no row-level prediction. Idempotent (the CHECK is dropped by its real name).
ALTER TABLE neural_mart.resumen_tarea_grupo
    ADD COLUMN IF NOT EXISTS ap_lo numeric,
    ADD COLUMN IF NOT EXISTS ap_hi numeric,
    ADD COLUMN IF NOT EXISTS auc_lo numeric,
    ADD COLUMN IF NOT EXISTS auc_hi numeric,
    ADD COLUMN IF NOT EXISTS tasa_lo numeric,
    ADD COLUMN IF NOT EXISTS tasa_hi numeric,
    ADD COLUMN IF NOT EXISTS esperado_lo numeric,
    ADD COLUMN IF NOT EXISTS esperado_hi numeric,
    ADD COLUMN IF NOT EXISTS pocos_casos boolean NOT NULL DEFAULT false;
ALTER TABLE neural_mart.resumen_tarea_grupo DROP CONSTRAINT IF EXISTS resumen_tarea_grupo_nivel_check;
ALTER TABLE neural_mart.resumen_tarea_grupo
    ADD CONSTRAINT resumen_tarea_grupo_nivel_check
    CHECK (nivel IN ('programa', 'facultad', 'nivel_postgrado', 'sexo', 'via', 'tipo_colegio'));
