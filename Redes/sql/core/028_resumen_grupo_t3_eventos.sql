-- D116: T3 (time to egreso) publishes every group with n >= 10 whatever its number of events (the backend derives a
-- confidence bar). Every other task keeps the "at least 10 events" rule. Idempotent.
ALTER TABLE neural_mart.resumen_tarea_grupo DROP CONSTRAINT IF EXISTS resumen_tarea_grupo_eventos_check;
ALTER TABLE neural_mart.resumen_tarea_grupo
    ADD CONSTRAINT resumen_tarea_grupo_eventos_check CHECK (eventos IS NULL OR eventos >= 10 OR tarea = 't3');
