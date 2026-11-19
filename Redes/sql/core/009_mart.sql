-- DAI Neural 009: gold (neural_mart). Tables rebuilt as a whole by `python -m pipelines.marts`
-- (docs/07_diseno_fase3.md). Rules: docs/03_reglas_academicas.md (averages only over evaluated attempts with a
-- non-inherited numeric grade; approval rate per attempt excludes convalidations and renuncias; curricular
-- progress counts each approved course once, convalidations included). Denominators are always stored.
-- Statistics over fewer than 10 people are NULL with a `suprimido` flag; windows not fully observed are NULL
-- with a `censurado` flag. No personal attribute and no teacher key lives here.
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.mart_construccion (
    mart           text        PRIMARY KEY,
    filas          bigint      NOT NULL,
    construido_en  timestamptz NOT NULL DEFAULT now(),
    periodo_maximo text,                                    -- latest regular period present in the states
    n_min          integer     NOT NULL
);

-- One row per (episode, period) in which the person has a state or an attempt of the episode.
CREATE TABLE IF NOT EXISTS neural_mart.indicador_periodo (
    episodio_id                     bigint  NOT NULL,
    periodo                         text    NOT NULL,
    persona_key                     text    NOT NULL,
    cod_programa                    text    NOT NULL,
    semestre_k                      integer,                -- regular periods since admission; NULL if not regular
    periodo_regular                 boolean NOT NULL,
    intentos_evaluados              integer NOT NULL,
    aprobados_evaluados             integer NOT NULL,
    reprobados                      integer NOT NULL,
    convalidaciones                 integer NOT NULL,
    creditos_aprobados_curriculares numeric NOT NULL,       -- first approval of each course, convalidations included
    promedio_periodo                numeric,
    n_notas_promedio                integer NOT NULL,       -- denominator of promedio_periodo
    creditos_acumulados             numeric NOT NULL,
    promedio_acumulado              numeric,
    n_notas_acumulado               integer NOT NULL,       -- denominator of promedio_acumulado
    ramos_aprobados_acumulados      integer NOT NULL,
    intentos_evaluados_acumulados   integer NOT NULL,
    aprobados_evaluados_acumulados  integer NOT NULL,
    PRIMARY KEY (episodio_id, periodo)
);

CREATE INDEX IF NOT EXISTS indicador_periodo_persona_ix ON neural_mart.indicador_periodo (persona_key, periodo);
CREATE INDEX IF NOT EXISTS indicador_periodo_k_ix ON neural_mart.indicador_periodo (cod_programa, semestre_k);

CREATE TABLE IF NOT EXISTS neural_mart.ficha_episodio (
    episodio_id                  bigint  PRIMARY KEY,
    persona_key                  text    NOT NULL,
    cod_programa                 text    NOT NULL,
    nombre_programa              text,
    cod_admision                 text    NOT NULL,
    admision                     text,
    periodo_admision             text,
    primer_periodo               text    NOT NULL,
    ultimo_periodo               text    NOT NULL,
    semestres_regulares_cursados integer NOT NULL,
    ultimo_cod_estado            text,
    ultimo_estado_clase          text,
    titulado                     boolean NOT NULL,
    egresado                     boolean NOT NULL,
    periodo_titulacion           text,                      -- U state period, else period of the titulacion date
    creditos_acumulados          numeric NOT NULL,
    promedio_acumulado           numeric,
    n_notas_acumulado            integer NOT NULL,
    tasa_aprobacion_intento      numeric,
    intentos_evaluados           integer NOT NULL,          -- denominator of tasa_aprobacion_intento
    aprobados_evaluados          integer NOT NULL,
    retencion_1er_anio           boolean                    -- NULL when semester 3 is not observed yet
);

CREATE INDEX IF NOT EXISTS ficha_episodio_persona_ix ON neural_mart.ficha_episodio (persona_key);
CREATE INDEX IF NOT EXISTS ficha_episodio_cohorte_ix ON neural_mart.ficha_episodio (cod_programa, periodo_admision);

CREATE TABLE IF NOT EXISTS neural_mart.avance_malla (
    episodio_id            bigint  NOT NULL,
    codigo_asignatura      text    NOT NULL,
    cod_programa           text    NOT NULL,
    catalogo               text    NOT NULL,
    semestre               integer,
    creditos               numeric,
    nombre_asignatura      text,
    es_hito                boolean NOT NULL,
    tipo_hito              text,
    estado_ramo            text    NOT NULL CHECK (estado_ramo IN
        ('aprobada', 'convalidada', 'reprobada_pendiente', 'en_curso', 'no_cursada')),
    n_intentos_evaluados   integer NOT NULL,
    mejor_nota             numeric,
    ultimo_periodo         text,
    PRIMARY KEY (episodio_id, codigo_asignatura)
);

CREATE TABLE IF NOT EXISTS neural_mart.cohorte_semestre (
    cod_programa          text    NOT NULL,
    cohorte               text    NOT NULL,                  -- periodo_admision
    semestre_k            integer NOT NULL,
    n_episodios           integer NOT NULL,                  -- episodes of the cohort
    n_activos             integer NOT NULL,                  -- with an enrolled state in that semester
    n_promedio            integer NOT NULL,                  -- active with at least one evaluated grade
    suprimido             boolean NOT NULL,
    suprimido_promedio    boolean NOT NULL,
    creditos_p25          numeric,
    creditos_p50          numeric,
    creditos_p75          numeric,
    promedio_p25          numeric,
    promedio_p50          numeric,
    promedio_p75          numeric,
    PRIMARY KEY (cod_programa, cohorte, semestre_k)
);

-- Same statistics over every cohort of the program (auxiliary comparison population).
CREATE TABLE IF NOT EXISTS neural_mart.programa_semestre (
    cod_programa          text    NOT NULL,
    semestre_k            integer NOT NULL,
    n_episodios           integer NOT NULL,
    n_activos             integer NOT NULL,
    n_promedio            integer NOT NULL,
    suprimido             boolean NOT NULL,
    suprimido_promedio    boolean NOT NULL,
    creditos_p25          numeric,
    creditos_p50          numeric,
    creditos_p75          numeric,
    promedio_p25          numeric,
    promedio_p50          numeric,
    promedio_p75          numeric,
    PRIMARY KEY (cod_programa, semestre_k)
);

CREATE TABLE IF NOT EXISTS neural_mart.cohorte_resultado (
    cod_programa          text    NOT NULL,
    cohorte               text    NOT NULL,
    n_ingreso             integer NOT NULL,
    suprimido             boolean NOT NULL,
    duracion              integer,                           -- semesters (mode over the cohort's catalogs)
    duracion_anios        integer,
    censurado_d           boolean NOT NULL,                  -- window of duracion_anios years not fully observed
    censurado_d1          boolean NOT NULL,                  -- duracion_anios + 1
    censurado_d2          boolean NOT NULL,                  -- duracion_anios + 2
    titulados_d           integer,
    titulados_d1          integer,
    titulados_d2          integer,
    censurado_retencion   boolean NOT NULL,
    n_retencion_obs       integer,                           -- denominator of retention
    n_retenidos           integer,
    PRIMARY KEY (cod_programa, cohorte)
);

CREATE TABLE IF NOT EXISTS neural_mart.postulante_contexto (
    cod_carrera           text    NOT NULL,
    year_admision         text    NOT NULL,                  -- application period (YYYY10 / YYYY20 / YYYY01)
    banda_ponderado       integer NOT NULL CHECK (banda_ponderado BETWEEN 1 AND 5),
    n_postulantes         integer NOT NULL,                  -- applicants of the band with a weighted score
    n_matriculados        integer NOT NULL,                  -- of them, matricula = Y
    n_vinculados          integer NOT NULL,                  -- enrolled and linked to an episode
    suprimido             boolean NOT NULL,                  -- n_vinculados below the minimum
    n_retencion_obs       integer,
    n_retenidos           integer,
    censurado_titulacion  boolean NOT NULL,
    duracion_anios        integer,
    n_titulacion_obs      integer,                           -- denominator; titulation within duracion_anios + 1 years
    n_titulados           integer,
    PRIMARY KEY (cod_carrera, year_admision, banda_ponderado)
);
