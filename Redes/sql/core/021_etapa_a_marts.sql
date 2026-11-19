-- DAI Neural 021: notes on the pairs of episodes that are NOT transfers (P64, P69). Rebuilt as a whole by
-- `python -m pipelines.marts` together with `programa_traslados`. Aggregates only: one row per relation.
-- `continuacion_estudios` (studying again after graduating, P69) no longer appears in `programa_traslados`; the view may
-- cite this count as a note. `doble_programa` / `superposicion_con_baja` (P64): overlapping episodes without / with a baja.
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.programa_traslados_nota (
    clave text    PRIMARY KEY,
    valor integer NOT NULL,
    nota  text
);
