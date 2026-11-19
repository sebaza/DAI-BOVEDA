-- DAI Neural 012: point-in-time snapshot of task T2 ("aprobacion por intento", docs/09_benchmark_t2.md).
-- Rebuilt as a whole by `python -m pipelines.snapshots.t2`. One row per EVALUATED attempt (numeric grade, not
-- convalidation / renuncia / in progress) of a regular period 2015-2025 of an undergraduate episode. Event y = 1 when
-- the grade is below 4.0 (reprobacion). Every history feature uses only facts with periodo STRICTLY before the
-- attempt's period; what is taken from the attempt's own period is known at enrollment (course, attempt number,
-- roster of courses, section). Compact types (real / smallint): about one million rows. Pseudonymous keys only.
-- `sexo_equidad` exists for fairness evaluation and is NEVER a model feature (decision M1). Teacher history is kept
-- as aggregates; the teacher key itself is not stored here. Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t2 (
    intento_id               bigint   NOT NULL PRIMARY KEY,
    episodio_id              bigint   NOT NULL,
    persona_key              text     NOT NULL,
    periodo                  text     NOT NULL,
    cod_programa             text     NOT NULL,
    catalogo                 text,
    codigo_asignatura        text     NOT NULL,
    split                    text     NOT NULL CHECK (split IN ('train', 'valid', 'test', 'posterior')),
    y                        smallint NOT NULL CHECK (y IN (0, 1)),
    -- student, as of the end of the previous period
    k                        smallint NOT NULL,
    prom_acum                real,
    n_notas_acum             integer,
    creditos_aprob_acum      real,
    tasa_aprob_acum          real,
    n_reprob_acum            integer,
    n_intentos_acum          integer,
    n_interrupcion           integer,
    sem_matriculados         integer,
    oportunidad              smallint,
    n_prev_curso             integer,
    mejor_nota_prev_curso    real,
    aprobo_antes_curso       boolean,
    cohorte_anio             integer,
    preferencia              real,
    con_postulacion          boolean,
    pct_leng                 real,
    pct_mat                  real,
    pct_ciencias             real,
    pct_historia             real,
    pct_nem                  real,
    pct_ranking              real,
    pct_notas_em             real,
    pct_ponderado            real,
    via_clase                text,
    cod_admision             text,
    sede                     text,
    tipo_colegio             text,
    depend_colegio           text,
    region_colegio           text,
    -- load of the period (known at enrollment)
    n_cursos_carga           real,
    creditos_carga           real,
    n_repetidos_carga        real,
    -- course
    creditos                 real,
    sem_malla                real,
    en_malla                 boolean,
    desfase                  real,
    tasa_hist_curso          real,
    n_hist_curso             real,
    prom_hist_curso          real,
    tasa_hist_curso_suav     real,
    tasa_hist_curso_prog     real,
    n_hist_curso_prog        real,
    tasa_hist_media_carga    real,
    formacion                text,
    depto                    text,
    -- explicit prerequisite graph (NULL when the course has no malla / prerequisite information)
    malla_conocida           boolean,
    info_prereq              boolean,
    n_prereq                 real,
    n_prereq_aprob           real,
    n_prereq_conva           real,
    n_prereq_pend_reprob     real,
    n_prereq_en_carga        real,
    min_nota_prereq          real,
    mean_nota_prereq         real,
    -- teacher / section context (ablation; only where the offer table has the section)
    tiene_docente            boolean,
    doc_tasa_suav            real,
    doc_n                    real,
    doc_curso_tasa_suav      real,
    doc_curso_n              real,
    -- fairness only (never a feature)
    sexo_equidad             text
);

CREATE INDEX IF NOT EXISTS snapshot_t2_split_ix ON neural_mart.snapshot_t2 (split, periodo);

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t2_resumen (
    clave  text PRIMARY KEY,
    valor  text NOT NULL,
    nota   text
);
