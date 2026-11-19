-- DAI Neural 030: new point-in-time variables requested by the DAI (P117-P127, viability study of 18-11-2026) for T1 and T2.
-- T1 (`snapshot_t1`, one row per episode and k): credits approved and average change in the last semester, second / third
-- opportunity failures, curricular lag (malla), load evolution and temporary withdrawal / annulment before the cut.
-- T2 (`snapshot_t2`, one row per evaluated attempt): the student's average in the same department and the recent performance
-- (previous regular semester with evaluated attempts). Every value uses only facts known at the cut (T1) or strictly before the
-- attempt's period (T2); see pipelines/snapshots/features_t1_nuevas.py and features_t2.py. NULL = not defined (no previous
-- semester, malla unknown, no department). Idempotent: safe to run more than once. Only adds columns; no existing column or
-- row is touched.

ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS creditos_aprob_ult_sem real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS delta_promedio_sem real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS delta_promedio_acum real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS repro_oport2 real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS repro_oport3 real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS ramos_repetidos real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS n_sem_sin_reprob real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS creditos_esperados real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS avance_malla real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS fraccion_malla real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS ramos_ins_ult real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS delta_ramos_ins real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS creditos_ins_ult real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS delta_creditos_ins real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS n_retiro_temporal real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS n_anulacion real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS sem_desde_ultimo_retiro real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS dias_desde_ultimo_retiro real;

ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS prom_depto real;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS n_depto real;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS dif_prom_depto real;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS prom_sem_prev real;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS tasa_sem_prev real;
