-- DAI Neural 027: student-benefit features of task T3 (banner.banner_beneficios, DAI 16-11-2026; decisions D100-D109).
-- DESIGN: a SIDE table, not new columns of snapshot_t3. `python -m pipelines.snapshots.t3` truncates and refills snapshot_t3, and
-- the benefit features exist under TWO point-in-time rules (`previo` = only years strictly before the cut year, the default;
-- `con_t` = also the cut year at an end-of-year cut, a sensitivity), so one row per (episode, k, rule) is the natural grain.
-- The benefit snapshot is rebuilt by `python -m pipelines.snapshots.t3_beneficios` after every rebuild of snapshot_t3.
-- `banda_decil` (rule-specific) and `banda_decil_eq` (cut year, descriptive grouping only) are NEVER model features: they exist
-- for the fairness tables. `benef_sem2` and `total` are never stored. Pseudonymous keys only (no persona_key here at all).
--
-- EXTENSION CUTS: the expiry-of-gratuity and Capstone flags appear 4-6 years after admission, so they are invisible at the official
-- cuts k = 2, 4. `snapshot_t3_ext*` hold the same snapshot built at the late cuts k = 8, 10 (same construction, same columns, same
-- splits); they are an extension for the benefit analysis and leave the official snapshot untouched.
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t3_beneficios (
    episodio_id                bigint   NOT NULL,
    k                          smallint NOT NULL CHECK (k >= 1),
    regla                      text     NOT NULL CHECK (regla IN ('previo', 'con_t')),
    ben_sin_dato               smallint NOT NULL,
    anio_ben                   smallint,
    tiene_gratuidad            real,
    tiene_credito              real,
    tiene_beca_estatal         real,
    tiene_beca_ucn             real,
    merito_ingreso             real,
    merito_e1                  real,
    n_beneficios               real,
    monto_sem1                 double precision,
    anios_con_gratuidad        real,
    expiro_gratuidad           real,
    etapa_capstone             real,
    expiro_alguna              real,
    capstone_alguna            real,
    perdida_sin_dato           smallint NOT NULL,
    perdio_gratuidad           real,
    perdio_credito             real,
    perdio_cualquier_beneficio real,
    obtuvo_gratuidad           real,
    banda_decil                text,
    banda_decil_eq             text,
    PRIMARY KEY (episodio_id, k, regla)
);

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t3_beneficios_resumen (
    clave   text PRIMARY KEY,
    valor   text NOT NULL,
    nota    text
);

-- Late cuts of T3 (extension): same columns and constraints as the official tables.
CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t3_ext (LIKE neural_mart.snapshot_t3 INCLUDING ALL);
CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t3_ext_semestre (LIKE neural_mart.snapshot_t3_semestre INCLUDING ALL);
CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t3_ext_resumen (LIKE neural_mart.snapshot_t3_resumen INCLUDING ALL);
