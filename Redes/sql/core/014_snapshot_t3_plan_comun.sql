-- DAI Neural 014: population change of task T3 (D47, P62): Ingenieria Civil Plan Comun merged with its specialty into one
-- trajectory (the unit is the Plan Comun admission) and the exchange programs excluded. Never edits the applied 013.
-- * trayectoria_plan_comun: the unit was admitted to an Ingenieria Civil Plan Comun program (an admission fact, known at
--   enrollment; it does NOT say whether a specialty continuation exists).
-- * especialidad_conocida_al_corte: a state of the specialty episode is recorded at or before the cut (never at k = 0).
--   Program columns of the row (cod_programa, duracion_nominal, creditos_malla_total, malla_conocida, creditos_esperados)
--   describe the program in force at the cut: Plan Comun until then, the specialty afterwards.
-- * episodio_especialidad_id: audit trail of the link (decided with the future): NEVER a model feature.
-- Idempotent: safe to run more than once. The next `python -m pipelines.snapshots.t3` refills the table.

ALTER TABLE neural_mart.snapshot_t3 ADD COLUMN IF NOT EXISTS trayectoria_plan_comun boolean NOT NULL DEFAULT false;
ALTER TABLE neural_mart.snapshot_t3 ADD COLUMN IF NOT EXISTS especialidad_conocida_al_corte boolean NOT NULL DEFAULT false;
ALTER TABLE neural_mart.snapshot_t3 ADD COLUMN IF NOT EXISTS episodio_especialidad_id bigint;
