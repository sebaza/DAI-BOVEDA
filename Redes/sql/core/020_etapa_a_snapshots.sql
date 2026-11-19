-- DAI Neural 020: stage A of the consolidated rebuild, snapshot columns (all added with defaults, so the tables can be
-- rebuilt by `python -m pipelines.snapshots.t1|t2|t3|t45|t6`). Pseudonymous keys only.
-- * P47: admission test (`prueba_admision`: PSU up to the 2020 process, PDT 2021-2022, PAES from 2023) and every score
--   min-max scaled within (test, year) (`mm_*`); the within-year percentiles `pct_*` are kept. Admission facts, never labels.
-- * P74: T2 grade band of the attempt (`banda_nota`), label side.
-- * P72 / P75: T4/T5 elimination with / without reintegro within the horizon and the doubtful-recording horizon flag.
-- * P77: T6 event and level from the postgrado state source (`ban_estados_academicos_pos`).
-- Idempotent: safe to run more than once.

ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS prueba_admision text;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS mm_leng real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS mm_mat real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS mm_ciencias real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS mm_historia real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS mm_nem real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS mm_ranking real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS mm_notas_em real;
ALTER TABLE neural_mart.snapshot_t1 ADD COLUMN IF NOT EXISTS mm_ponderado real;

ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS prueba_admision text;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS mm_leng real;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS mm_mat real;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS mm_ciencias real;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS mm_historia real;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS mm_nem real;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS mm_ranking real;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS mm_notas_em real;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS mm_ponderado real;
ALTER TABLE neural_mart.snapshot_t2 ADD COLUMN IF NOT EXISTS banda_nota text CHECK (banda_nota IN ('reprobado', 'minima', 'aprobatoria', 'sobresaliente'));

ALTER TABLE neural_mart.snapshot_t3 ADD COLUMN IF NOT EXISTS prueba_admision text;
ALTER TABLE neural_mart.snapshot_t3 ADD COLUMN IF NOT EXISTS mm_leng real;
ALTER TABLE neural_mart.snapshot_t3 ADD COLUMN IF NOT EXISTS mm_mat real;
ALTER TABLE neural_mart.snapshot_t3 ADD COLUMN IF NOT EXISTS mm_ciencias real;
ALTER TABLE neural_mart.snapshot_t3 ADD COLUMN IF NOT EXISTS mm_historia real;
ALTER TABLE neural_mart.snapshot_t3 ADD COLUMN IF NOT EXISTS mm_nem real;
ALTER TABLE neural_mart.snapshot_t3 ADD COLUMN IF NOT EXISTS mm_ranking real;
ALTER TABLE neural_mart.snapshot_t3 ADD COLUMN IF NOT EXISTS mm_notas_em real;
ALTER TABLE neural_mart.snapshot_t3 ADD COLUMN IF NOT EXISTS mm_ponderado real;

ALTER TABLE neural_mart.snapshot_t45 ADD COLUMN IF NOT EXISTS prueba_admision text;
ALTER TABLE neural_mart.snapshot_t45 ADD COLUMN IF NOT EXISTS mm_leng real;
ALTER TABLE neural_mart.snapshot_t45 ADD COLUMN IF NOT EXISTS mm_mat real;
ALTER TABLE neural_mart.snapshot_t45 ADD COLUMN IF NOT EXISTS mm_ciencias real;
ALTER TABLE neural_mart.snapshot_t45 ADD COLUMN IF NOT EXISTS mm_historia real;
ALTER TABLE neural_mart.snapshot_t45 ADD COLUMN IF NOT EXISTS mm_nem real;
ALTER TABLE neural_mart.snapshot_t45 ADD COLUMN IF NOT EXISTS mm_ranking real;
ALTER TABLE neural_mart.snapshot_t45 ADD COLUMN IF NOT EXISTS mm_notas_em real;
ALTER TABLE neural_mart.snapshot_t45 ADD COLUMN IF NOT EXISTS mm_ponderado real;
ALTER TABLE neural_mart.snapshot_t45 ADD COLUMN IF NOT EXISTS eliminacion_con_reintegro boolean NOT NULL DEFAULT false;
ALTER TABLE neural_mart.snapshot_t45 ADD COLUMN IF NOT EXISTS eliminacion_efectiva boolean NOT NULL DEFAULT false;
ALTER TABLE neural_mart.snapshot_t45 ADD COLUMN IF NOT EXISTS horizonte_e_dudoso boolean NOT NULL DEFAULT false;

ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS prueba_admision text;
ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS mm_leng real;
ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS mm_mat real;
ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS mm_ciencias real;
ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS mm_historia real;
ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS mm_nem real;
ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS mm_ranking real;
ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS mm_notas_em real;
ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS mm_ponderado real;
ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS previo_estados boolean NOT NULL DEFAULT false;
ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS evento_estados smallint NOT NULL DEFAULT 0 CHECK (evento_estados IN (0, 1));
ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS tiempo_estados smallint NOT NULL DEFAULT 1 CHECK (tiempo_estados >= 1);
ALTER TABLE neural_mart.snapshot_t6 ADD COLUMN IF NOT EXISTS nivel_estados text CHECK (nivel_estados IN ('magister', 'doctorado', 'diplomado', 'otro'));
