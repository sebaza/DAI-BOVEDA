-- DAI Neural 011: point-in-time snapshots of task T1 ("continuidad a un anio", docs/08_benchmark_t1.md).
-- Rebuilt as a whole by `python -m pipelines.snapshots.t1`. One row per (episode, k) with the features known at
-- the cutoff (end of the k-th regular semester) and the label observed one year later. Features use only facts with
-- periodo <= periodo_corte; the label uses only periods strictly after it. Pseudonymous keys only (persona_key).
-- `sexo_equidad` exists for fairness evaluation and is NEVER a model feature (decision M1).
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t1 (
    episodio_id              bigint  NOT NULL,
    k                        integer NOT NULL CHECK (k >= 1),
    persona_key              text    NOT NULL,
    cod_programa             text    NOT NULL,
    periodo_admision         text    NOT NULL,
    cohorte_anio             integer NOT NULL,
    periodo_corte            text    NOT NULL,
    periodo_horizonte        text    NOT NULL,
    split                    text    NOT NULL CHECK (split IN ('train', 'valid', 'test', 'posterior')),
    estado_muestra           text    NOT NULL CHECK (estado_muestra IN ('observada', 'censurada', 'sin_cobertura')),
    -- label (NULL unless estado_muestra = 'observada')
    continua                 boolean,
    continua_mismo_programa  boolean,
    no_continua_tipo         text    CHECK (no_continua_tipo IN ('salida', 'interrupcion', 'ausencia')),
    -- pre-entry
    cod_admision             text,
    via_clase                text,
    sede                     text,
    tipo_colegio             text,
    depend_colegio           text,
    region_colegio           text,
    preferencia              numeric,
    con_postulacion          boolean NOT NULL,
    pct_leng                 numeric,
    pct_mat                  numeric,
    pct_ciencias             numeric,
    pct_historia             numeric,
    pct_nem                  numeric,
    pct_ranking              numeric,
    pct_notas_em             numeric,
    pct_ponderado            numeric,
    -- academic, up to the cutoff
    creditos_aprobados       numeric NOT NULL,
    intentos_evaluados       integer NOT NULL,
    aprobados                integer NOT NULL,
    reprobados               integer NOT NULL,
    tasa_aprobacion          numeric,
    promedio_evaluado        numeric,
    n_notas_promedio         integer NOT NULL,
    convalidaciones          integer NOT NULL,
    cursos_verano_invierno   integer NOT NULL,
    n_interrupcion           integer NOT NULL,
    cambios_catalogo         integer NOT NULL,
    semestres_matriculados   integer NOT NULL,
    intentos_ult_semestre    integer NOT NULL,
    tasa_ult_semestre        numeric,
    promedio_ult_semestre    numeric,
    -- fairness only (never a feature)
    sexo_equidad             text,
    PRIMARY KEY (episodio_id, k)
);

CREATE INDEX IF NOT EXISTS snapshot_t1_split_ix ON neural_mart.snapshot_t1 (k, split, estado_muestra);

-- One row per (episode, regular semester j): the GRU input. Row j only holds facts with
-- periodo in (regular period j-1, regular period j]; summer/winter periods (15/25) fall in the next regular slot.
CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t1_semestre (
    episodio_id            bigint  NOT NULL,
    j                      integer NOT NULL CHECK (j >= 1),
    matriculado            boolean NOT NULL,
    interrupcion           boolean NOT NULL,
    intentos_evaluados     integer NOT NULL,
    aprobados              integer NOT NULL,
    reprobados             integer NOT NULL,
    convalidaciones        integer NOT NULL,
    creditos_aprobados     numeric NOT NULL,
    cursos_verano_invierno integer NOT NULL,
    promedio               numeric,
    n_notas_promedio       integer NOT NULL,
    creditos_acumulados    numeric NOT NULL,
    PRIMARY KEY (episodio_id, j)
);

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t1_resumen (
    clave   text PRIMARY KEY,
    valor   text NOT NULL,
    nota    text
);
