-- DAI Neural 025: benefit features of the T1 snapshot (banner.banner_beneficios, DAI 16-11-2026; decisions D90-D95).
-- Point in time: the facts of the calendar year of the cut period for the episode's program; the second-semester amounts and the total are never
-- used (see pipelines/snapshots/rules_beneficios.py). A year without data is unknown (NULL) and flagged by `ben_sin_dato`; the
-- year-over-year loss variables exist only at k = 4 (NULL elsewhere, `perdida_sin_dato` = 1).
-- Idempotent: safe to run more than once. Pseudonymous keys only.

ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS ben_sin_dato smallint;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS tiene_gratuidad real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS tiene_credito real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS tiene_beca_estatal real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS tiene_beca_ucn real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS merito_ingreso real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS merito_e1 real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS banda_decil text;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS expiro_gratuidad real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS etapa_capstone real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS n_beneficios real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS monto_sem1 double precision;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS perdida_sin_dato smallint;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS perdio_gratuidad real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS perdio_credito real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS perdio_cualquier_beneficio real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS obtuvo_gratuidad real;
