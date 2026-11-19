-- DAI Neural 017: point-in-time snapshots of tasks T4 ("transicion real de programa") and T5 ("eliminacion"),
-- docs/11_benchmark_t4_t5.md. Rebuilt as a whole by `python -m pipelines.snapshots.t45`. One row per (trajectory, k): the
-- T3 unit (D47) at risk at the end of the k-th REGULAR semester since admission, k in (2, 4). Features use only facts of
-- the slots <= k (they are the T3 features); the label is the MUTUALLY EXCLUSIVE outcome of the next two regular semesters:
--   continua | egreso | transicion (T4) | eliminacion (T5) | otra_salida | transicion_ambigua | censurado
-- (the last two are kept for audit and never used by a model). Pseudonymous keys only (persona_key).
-- `sexo_equidad` exists for fairness evaluation and is NEVER a model feature (decision M1); `cohorte_anio` only defines the
-- split and the subgroup tables. `episodio_especialidad_id` is the audit trail of the Plan Comun link (never a feature).
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t45 (
    episodio_id              bigint   NOT NULL,
    k                        smallint NOT NULL CHECK (k >= 1),
    persona_key              text     NOT NULL,
    cod_programa             text     NOT NULL,
    periodo_admision         text     NOT NULL,
    cohorte_anio             integer  NOT NULL,
    split                    text     NOT NULL CHECK (split IN ('train', 'valid', 'test', 'posterior')),
    -- label (outcome of the slots k+1 .. k+2)
    seguimiento_max          smallint NOT NULL,
    resultado                text     NOT NULL CHECK (resultado IN ('continua', 'egreso', 'transicion', 'eliminacion',
                                                                     'otra_salida', 'transicion_ambigua', 'censurado')),
    otra_salida_tipo         text     CHECK (otra_salida_tipo IN ('salida_explicita', 'interrupcion', 'ausencia')),
    hubo_transicion_en_horizonte boolean NOT NULL,
    hubo_eliminacion_en_horizonte boolean NOT NULL,
    episodio_especialidad_id bigint,
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
    -- program in force at the cut
    duracion_nominal         real,
    creditos_malla_total     real,
    malla_conocida           boolean  NOT NULL,
    trayectoria_plan_comun   boolean  NOT NULL,
    especialidad_conocida_al_corte boolean NOT NULL,
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

CREATE INDEX IF NOT EXISTS snapshot_t45_split_ix ON neural_mart.snapshot_t45 (k, split);

-- One row per (trajectory, regular semester j <= 4): the GRU input (same layout as snapshot_t3_semestre). Attempts of the
-- periods without recorded failures (201920, 202010) do not count as evaluated attempts here (P58).
CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t45_semestre (
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

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t45_resumen (
    clave   text PRIMARY KEY,
    valor   text NOT NULL,
    nota    text
);
