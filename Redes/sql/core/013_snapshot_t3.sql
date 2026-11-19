-- DAI Neural 013: point-in-time snapshots of task T3 ("tiempo hasta titulacion", docs/10_benchmark_t3.md).
-- Rebuilt as a whole by `python -m pipelines.snapshots.t3`. One row per (episode, k): the episode is at risk at the end
-- of the k-th REGULAR semester since admission (k = 0: at enrollment, only admission facts). Features use only facts of
-- the slots <= k; the label is the time (in regular semesters since admission, `tiempo`) and the cause of the first
-- event after the cut: 1 = egreso/titulacion of the episode, 2 = definitive exit (competing), 0 = administratively
-- censored at the last closed regular period (or at slot 20). Pseudonymous keys only (persona_key).
-- `sexo_equidad` exists for fairness evaluation and is NEVER a model feature (decision M1).
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t3 (
    episodio_id              bigint   NOT NULL,
    k                        smallint NOT NULL CHECK (k >= 0),
    persona_key              text     NOT NULL,
    cod_programa             text     NOT NULL,
    periodo_admision         text     NOT NULL,
    cohorte_anio             integer  NOT NULL,
    split                    text     NOT NULL CHECK (split IN ('train', 'valid', 'test', 'posterior')),
    -- label (time and cause after the cut)
    seguimiento_max          smallint NOT NULL,
    tiempo                   smallint NOT NULL,
    causa                    smallint NOT NULL CHECK (causa IN (0, 1, 2)),
    salida_tipo              text     CHECK (salida_tipo IN ('explicita', 'ausencia')),
    salida_a_otro_programa   boolean,
    tiempo_titulacion        smallint,
    -- pre-entry
    via_clase                text,
    cod_admision             text,
    sede                     text,
    tipo_colegio             text,
    depend_colegio           text,
    region_colegio           text,
    preferencia              real,
    con_postulacion          boolean  NOT NULL,
    pct_leng                 real,
    pct_mat                  real,
    pct_ciencias             real,
    pct_historia             real,
    pct_nem                  real,
    pct_ranking              real,
    pct_notas_em             real,
    pct_ponderado            real,
    -- program (static)
    duracion_nominal         real,
    creditos_malla_total     real,
    malla_conocida           boolean  NOT NULL,
    -- academic, up to the cut
    creditos_aprobados       real     NOT NULL,
    intentos_evaluados       integer  NOT NULL,
    aprobados                integer  NOT NULL,
    reprobados               integer  NOT NULL,
    tasa_aprobacion          real,
    promedio_evaluado        real,
    n_notas_promedio         integer  NOT NULL,
    convalidaciones          integer  NOT NULL,
    cursos_verano_invierno   integer  NOT NULL,
    n_interrupcion           integer  NOT NULL,
    cambios_catalogo         integer  NOT NULL,
    semestres_matriculados   integer  NOT NULL,
    intentos_ult_semestre    integer  NOT NULL,
    tasa_ult_semestre        real,
    promedio_ult_semestre    real,
    creditos_esperados       real,
    avance_malla             real,
    fraccion_malla           real,
    n_sem_sin_reprobacion    smallint NOT NULL,
    -- fairness only (never a feature)
    sexo_equidad             text,
    PRIMARY KEY (episodio_id, k)
);

CREATE INDEX IF NOT EXISTS snapshot_t3_split_ix ON neural_mart.snapshot_t3 (k, split);

-- One row per (episode, regular semester j <= 4): the GRU input. Row j only holds facts with
-- periodo in (regular period j-1, regular period j]; summer/winter periods (15/25) fall in the next regular slot.
-- Attempts of the periods without recorded failures (201920, 202010) do not count as evaluated attempts here (P58).
CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t3_semestre (
    episodio_id            bigint  NOT NULL,
    j                      integer NOT NULL CHECK (j >= 1),
    matriculado            boolean NOT NULL,
    interrupcion           boolean NOT NULL,
    intentos_evaluados     integer NOT NULL,
    aprobados              integer NOT NULL,
    reprobados             integer NOT NULL,
    convalidaciones        integer NOT NULL,
    creditos_aprobados     real    NOT NULL,
    cursos_verano_invierno integer NOT NULL,
    promedio               real,
    n_notas_promedio       integer NOT NULL,
    creditos_acumulados    real    NOT NULL,
    PRIMARY KEY (episodio_id, j)
);

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t3_resumen (
    clave   text PRIMARY KEY,
    valor   text NOT NULL,
    nota    text
);
