-- DAI Neural 033: no group-size suppression. Aggregate figures are published for any group size (decision of 2026-11-18).
-- Drops the n >= 10 / eventos >= 10 CHECKs of the per-task summaries (023, replaced in 028) and every suppression
-- column of the marts. Constraint names are the ones PostgreSQL generated; IF EXISTS keeps it idempotent.
-- Still no person key, no name, no row-level prediction: only the size rule goes away.
ALTER TABLE IF EXISTS neural_mart.resumen_tarea_calibracion DROP CONSTRAINT IF EXISTS resumen_tarea_calibracion_n_check;
ALTER TABLE IF EXISTS neural_mart.resumen_tarea_grupo DROP CONSTRAINT IF EXISTS resumen_tarea_grupo_n_check;
ALTER TABLE IF EXISTS neural_mart.resumen_tarea_grupo DROP CONSTRAINT IF EXISTS resumen_tarea_grupo_eventos_check;

ALTER TABLE IF EXISTS neural_mart.cohorte_semestre DROP COLUMN IF EXISTS suprimido, DROP COLUMN IF EXISTS suprimido_promedio;
ALTER TABLE IF EXISTS neural_mart.programa_semestre DROP COLUMN IF EXISTS suprimido, DROP COLUMN IF EXISTS suprimido_promedio;
ALTER TABLE IF EXISTS neural_mart.cohorte_resultado DROP COLUMN IF EXISTS suprimido;
ALTER TABLE IF EXISTS neural_mart.postulante_contexto DROP COLUMN IF EXISTS suprimido;
ALTER TABLE IF EXISTS neural_mart.mart_construccion DROP COLUMN IF EXISTS n_min;
ALTER TABLE IF EXISTS neural_mart.resumen_tarea_grupo_resumen
    DROP COLUMN IF EXISTS grupos_suprimidos, DROP COLUMN IF EXISTS n_min, DROP COLUMN IF EXISTS eventos_min;
