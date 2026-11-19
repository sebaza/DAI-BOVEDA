-- DAI Neural 031: new variables of T3, T4, T5 and T6 (DAI answers P117-P127, 18-11-2026; viability study
-- evidencia/viabilidad_variables_2026-11-18.md).
-- DESIGN: SIDE tables, not new columns of snapshot_t3 / snapshot_t45 / snapshot_t6 (as 027 does for the benefits). The official
-- snapshots keep their columns and values, so the kept models stay reproducible; the loaders merge the side tables by key.
-- `python -m pipelines.snapshots.variables_nuevas` rebuilds them after every rebuild of snapshot_t3 / snapshot_t6.
-- Grain: one row per (episode, k) of snapshot_t3 (the T4 / T5 rows are a subset: same units and same cuts) and one row per
-- episode of snapshot_t6 (k = the graduation semester). Pseudonymous keys only: no persona_key here at all.
-- Every attempt feature reads attempts of slots <= k; k = 0 only has the static malla facts (see features_variables.py).
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_variables_nuevas (
    episodio_id                bigint   NOT NULL,
    k                          smallint NOT NULL CHECK (k >= 0),
    -- regulatory risk under the old (Art. 50 / 52) and the new (Art. 46) regulation (P117, P118)
    reg_rep2_total             double precision,
    reg_rep2_cb                double precision,
    reg_rep2_cp                double precision,
    reg_rep3_cursos            double precision,
    reg_cursos_riesgo_3ra      double precision,
    reg_pendientes_reprobados  double precision,
    reg_ciclo_cb_actual        double precision,
    reg_sem_en_cb              double precision,
    reg_dist_2da_antiguo       double precision,
    reg_dist_3ra_antiguo       double precision,
    reg_dist_2da_nuevo         double precision,
    reg_dist_3ra_nuevo         double precision,
    reg_n_sem_avance_lt50      double precision,
    reg_consec_avance_lt50     double precision,
    reg_dist_avance_antiguo    double precision,
    -- reach rule (P121)
    alc_sem_pendiente_antiguo  double precision,
    alc_rezago                 double precision,
    alc_pendiente_gt4          boolean  NOT NULL,
    alc_n_bloqueados           double precision,
    -- credits (P126), speed and Capstone / practice (P125)
    creditos_malla_total_corr  double precision,
    malla_creditos_confiable   boolean  NOT NULL,
    creditos_restantes         double precision,
    velocidad_aprobacion       double precision,
    velocidad_relativa         double precision,
    cap_inscrito               double precision,
    cap_aprobado               double precision,
    prac_inscrita              double precision,
    prac_aprobada              double precision,
    malla_tiene_capstone       boolean  NOT NULL,
    malla_tiene_practica       boolean  NOT NULL,
    -- own versus general formation, earlier program changes (T4)
    n_propios_eval             double precision,
    tasa_propios               double precision,
    prom_propios               double precision,
    n_generales_eval           double precision,
    tasa_generales             double precision,
    prom_generales             double precision,
    brecha_propios_generales   double precision,
    n_episodios_previos        double precision,
    n_cc_previos               double precision,
    PRIMARY KEY (episodio_id, k)
);

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_variables_nuevas_t6 (
    episodio_id          bigint PRIMARY KEY,
    ranking_prom_egreso  double precision,
    nota_titulo          double precision,
    nota_practica        double precision
);

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_variables_nuevas_resumen (
    clave   text PRIMARY KEY,
    valor   text NOT NULL,
    nota    text
);
