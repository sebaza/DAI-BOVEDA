-- DAI Neural 004: silver (neural_core). Normalized entities with the academic rules applied
-- (docs/03_reglas_academicas.md) and natural-key constraints (docs/05_modelo_datos.md section 4).
-- No personal attributes: persons are persona_key (HMAC) only. sexo is kept for fairness evaluation.
-- FKs are declared only where the derivation guarantees the parent row (persona, episodio, seccion);
-- program/catalog references are not FKs because the dimensions do not cover every code (R14, R35).
-- Idempotent: safe to run more than once.

-- ---------------------------------------------------------------------------------------------
-- 4.1 Identity and academic catalog
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS neural_core.persona (
    persona_key                 text PRIMARY KEY,
    sexo                        text,                          -- M1: fairness evaluation only
    sexo_conflicto              boolean NOT NULL DEFAULT false, -- sources disagree; value is not guessed
    primer_periodo_estados      text,
    primer_periodo_historia     text,
    primer_periodo_inscripcion  text,
    creado_en                   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS neural_core.programa (
    cod_programa           text    PRIMARY KEY,               -- = programa_d.cod_banner
    programa_d_id          bigint  NOT NULL UNIQUE,
    valid_program          boolean NOT NULL,
    programa_predecesor    bigint,
    predecesor_inexistente boolean NOT NULL DEFAULT false,
    nombre_programa        text,
    id_nivel               bigint,
    area_conocimiento      text,
    facultad               bigint,
    sede                   bigint,
    cod_demre              text
);

CREATE TABLE IF NOT EXISTS neural_core.programa_catalogo (
    cod_programa text    NOT NULL,
    catalogo     text    NOT NULL,
    duracion     integer,
    PRIMARY KEY (cod_programa, catalogo)
);

CREATE TABLE IF NOT EXISTS neural_core.asignatura_malla (
    cod_programa      text    NOT NULL,
    catalogo          text    NOT NULL,
    codigo_asignatura text    NOT NULL,                       -- AAAA-99999
    formato_codigo    text    NOT NULL DEFAULT 'AAAA-99999' CHECK (formato_codigo IN ('AAAA-99999', 'AAA9-99999', 'otro')),
    semestre          integer,
    creditos          numeric,
    formacion         text,
    nombre_asignatura text,
    area              text,
    depto             text,
    depto_desc        text,
    PRIMARY KEY (cod_programa, catalogo, codigo_asignatura)
);

CREATE TABLE IF NOT EXISTS neural_core.prerrequisito (
    cod_programa          text    NOT NULL,
    catalogo              text    NOT NULL,
    codigo_requisito      text    NOT NULL,                   -- must be approved first (edge source)
    codigo_asignatura     text    NOT NULL,                   -- course that needs it (edge target)
    filas_origen          integer NOT NULL CHECK (filas_origen >= 1),
    asig_en_malla         boolean NOT NULL,
    req_en_malla          boolean NOT NULL,
    req_en_otro_programa  boolean NOT NULL,
    clasificacion         text    NOT NULL CHECK (clasificacion IN ('misma_malla', 'otro_catalogo', 'otro_programa', 'ninguna')),
    PRIMARY KEY (cod_programa, catalogo, codigo_requisito, codigo_asignatura)
);

CREATE TABLE IF NOT EXISTS neural_core.hito_formativo (
    cod_programa      text    NOT NULL,
    catalogo          text    NOT NULL,
    codigo_asignatura text    NOT NULL,
    tipo_hito         text    NOT NULL CHECK (tipo_hito IN ('practica', 'memoria', 'proyecto', 'seminario', 'capstone', 'titulacion')),
    metodo            text    NOT NULL,                       -- e.g. regex_nombre_v1
    validado          boolean NOT NULL DEFAULT false,         -- expert review (P26)
    version           text    NOT NULL,
    PRIMARY KEY (cod_programa, catalogo, codigo_asignatura)
);

-- ---------------------------------------------------------------------------------------------
-- 4.2 Admission
-- ---------------------------------------------------------------------------------------------
-- The full natural key (year, persona, program, route) is NOT verified unique (R23), so a surrogate
-- key is used and every source row is kept.
CREATE TABLE IF NOT EXISTS neural_core.postulacion_via (
    postulacion_via_id    bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    year_admision         text    NOT NULL,                   -- a period (YYYY10 / YYYY20 / YYYY01)
    persona_key           text    NOT NULL,
    cod_carrera           text    NOT NULL,
    cod_admision          text,
    id_sede               integer,
    pref_demre            text,
    preferencia           text,
    matricula             text    CHECK (matricula IN ('Y', 'N')),
    fecha_matricula       date,
    puntaje_leng          numeric,
    puntaje_mat           numeric,
    puntaje_ciencias      numeric,
    puntaje_historia      numeric,
    puntaje_nem           numeric,
    puntaje_ranking       numeric,
    notas_em              numeric,
    promedio_lm           numeric,
    ponderado             numeric,
    ponderado_normalizado numeric,
    puntaje_parse_ok      boolean NOT NULL DEFAULT true,
    tipo_colegio          text,
    depend_colegio        text,
    region_colegio        text,                               -- M2: descriptive context only
    comuna_colegio        text,
    cod_comuna            text,
    carga_id              bigint  NOT NULL
);

CREATE INDEX IF NOT EXISTS postulacion_via_nk_ix ON neural_core.postulacion_via (year_admision, persona_key, cod_carrera, cod_admision);

CREATE TABLE IF NOT EXISTS neural_core.postulacion (
    year_admision        text    NOT NULL,
    persona_key          text    NOT NULL,
    cod_carrera          text    NOT NULL,
    cod_admision_elegida text,
    matricula_elegida    text    CHECK (matricula_elegida IN ('Y', 'N')),
    alguna_via_matriculo boolean NOT NULL,
    n_vias               integer NOT NULL CHECK (n_vias >= 1),
    PRIMARY KEY (year_admision, persona_key, cod_carrera)
);

-- ---------------------------------------------------------------------------------------------
-- 4.3 Trajectory
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS neural_core.episodio_programa (
    episodio_id           bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    persona_key           text    NOT NULL REFERENCES neural_core.persona (persona_key),
    cod_programa          text    NOT NULL,
    cod_admision          text    NOT NULL,                   -- 'NN' when the source is NULL
    periodo_admision      text,
    cod_admision_imputado boolean NOT NULL DEFAULT false,
    primer_periodo        text    NOT NULL,
    ultimo_periodo        text    NOT NULL,
    n_tramos              integer NOT NULL CHECK (n_tramos >= 1),
    n_estados             integer NOT NULL CHECK (n_estados >= 1),
    no_contiguo           boolean NOT NULL DEFAULT false,
    catalogo_inicial      text,
    catalogo_final        text,
    ultimo_estado_clase   text,
    CONSTRAINT episodio_programa_nk_uq UNIQUE NULLS NOT DISTINCT (persona_key, cod_programa, cod_admision, periodo_admision),
    CONSTRAINT episodio_programa_periodos_ck CHECK (primer_periodo <= ultimo_periodo),
    CONSTRAINT episodio_programa_contiguo_ck CHECK (no_contiguo = (n_tramos > 1))
);

CREATE TABLE IF NOT EXISTS neural_core.evento_estado (
    persona_key           text    NOT NULL REFERENCES neural_core.persona (persona_key),
    sorlcur               bigint  NOT NULL,                   -- per-person sequence; not dense, not a key of anything else
    episodio_id           bigint  REFERENCES neural_core.episodio_programa (episodio_id),
    periodo               text    NOT NULL,
    orden_canonico        integer NOT NULL CHECK (orden_canonico >= 1),   -- rank by (periodo, sorlcur)
    tramo_n               integer CHECK (tramo_n >= 1),
    cod_programa          text    NOT NULL,
    cod_admision          text,                               -- original value (may be NULL)
    periodo_admision      text,
    catalogo              text,
    plan_estudios         numeric,
    cod_estado            text,                               -- kept as received; NULL = sin_codigo
    sin_codigo            boolean NOT NULL DEFAULT false,
    estado_conocido       boolean NOT NULL DEFAULT true,
    cod_causal            text,
    fecha_estado_original timestamp,                          -- never overwritten
    fecha_min             date,
    fecha_max             date,
    fecha_aproximada      boolean NOT NULL DEFAULT false,
    sin_intervalo         boolean NOT NULL DEFAULT false,
    intervalo_invertido   boolean NOT NULL DEFAULT false,
    fecha_marcador        boolean NOT NULL DEFAULT false,     -- date after the extraction cutoff (RA04)
    es_correccion_sistema boolean NOT NULL DEFAULT false,     -- reversal 1/2/5 (RA06)
    carga_id              bigint  NOT NULL,
    PRIMARY KEY (persona_key, sorlcur),
    CONSTRAINT evento_estado_orden_uq UNIQUE (persona_key, orden_canonico),
    CONSTRAINT evento_estado_reversa_ck CHECK (NOT es_correccion_sistema OR (episodio_id IS NULL AND tramo_n IS NULL)),
    CONSTRAINT evento_estado_intervalo_ck CHECK (fecha_min IS NULL OR fecha_max IS NULL OR fecha_min <= fecha_max)
);

CREATE INDEX IF NOT EXISTS evento_estado_episodio_ix ON neural_core.evento_estado (episodio_id);

-- ---------------------------------------------------------------------------------------------
-- 4.4 Courses
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS neural_core.intento_asignatura (
    intento_id            bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    periodo               text    NOT NULL,
    persona_key           text    NOT NULL REFERENCES neural_core.persona (persona_key),
    cod_carrera           text    NOT NULL,
    catalogo              text,
    materia               text    NOT NULL,
    curso                 text    NOT NULL,
    oportunidad           integer,
    nrc                   text,
    episodio_id           bigint  REFERENCES neural_core.episodio_programa (episodio_id),
    sin_episodio          boolean NOT NULL DEFAULT false,
    episodio_ambiguo      boolean NOT NULL DEFAULT false,
    codigo_asignatura     text    NOT NULL,                   -- materia || '-' || curso
    formato_codigo        text    NOT NULL DEFAULT 'AAAA-99999' CHECK (formato_codigo IN ('AAAA-99999', 'AAA9-99999', 'otro')),
    titulo                text,
    nota_texto            text,
    nota_parse            text    NOT NULL CHECK (nota_parse IN ('numeric', 'dpa', 'empty', 'invalid')),
    nota_numerica         numeric CHECK (nota_numerica BETWEEN 0 AND 7),
    nota_es_heredada      boolean NOT NULL DEFAULT false,
    resultado_tipo        text    NOT NULL CHECK (resultado_tipo IN ('evaluado', 'convalidacion', 'renuncia', 'en_curso', 'otro')),
    aprobado_curricular   boolean,
    es_intento_evaluado   boolean NOT NULL,
    creditos              numeric,
    creditos_reconocidos  numeric,
    comentario_codigo     text,
    fuente_resultado      text    NOT NULL DEFAULT 'historia' CHECK (fuente_resultado IN ('historia', 'inscripcion')),
    carga_id              bigint  NOT NULL,
    -- V08: verified unique in the source (0 repeated keys).
    CONSTRAINT intento_asignatura_nk_uq UNIQUE NULLS NOT DISTINCT
        (periodo, persona_key, cod_carrera, catalogo, materia, curso, oportunidad, nrc),
    CONSTRAINT intento_evaluado_ck CHECK (NOT es_intento_evaluado OR (resultado_tipo = 'evaluado' AND nota_numerica IS NOT NULL)),
    CONSTRAINT intento_aprobacion_ck CHECK (NOT es_intento_evaluado OR aprobado_curricular = (nota_numerica >= 4.0)),
    CONSTRAINT intento_heredada_ck CHECK (NOT nota_es_heredada OR resultado_tipo = 'convalidacion'),
    CONSTRAINT intento_episodio_ck CHECK (
        (episodio_id IS NOT NULL AND NOT sin_episodio AND NOT episodio_ambiguo)
        OR (episodio_id IS NULL AND (sin_episodio <> episodio_ambiguo))
    )
);

CREATE INDEX IF NOT EXISTS intento_asignatura_persona_ix ON neural_core.intento_asignatura (persona_key, periodo);
CREATE INDEX IF NOT EXISTS intento_asignatura_episodio_ix ON neural_core.intento_asignatura (episodio_id);

-- M3: one inscribed course may map to several catalog-equivalent courses (child table).
-- Grain: (periodo, persona, nrc, materia_curso_inscrito); the 8 groups with more than one estado are
-- kept as separate rows (estado is part of the key) and flagged estado_conflicto = true.
-- oportunidad varies inside some inscriptions (R31), so it also lives on the equivalence row.
CREATE TABLE IF NOT EXISTS neural_core.inscripcion_asignatura (
    inscripcion_id         bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    periodo                text    NOT NULL,
    persona_key            text    NOT NULL REFERENCES neural_core.persona (persona_key),
    nrc                    text,                              -- 36 source rows have an empty nrc
    materia_curso_inscrito text    NOT NULL,
    titulo_inscrito        text,
    estado                 text,
    aprobacion             text,
    oportunidad            integer,                           -- NULL when the equivalence rows disagree
    oportunidad_conflicto  boolean NOT NULL DEFAULT false,
    nota_texto             text,
    nota_parse             text    NOT NULL CHECK (nota_parse IN ('numeric', 'dpa', 'empty', 'invalid')),
    nota_numerica          numeric CHECK (nota_numerica BETWEEN 0 AND 7),
    nota_es_heredada       boolean NOT NULL DEFAULT false,
    resultado_tipo         text    NOT NULL CHECK (resultado_tipo IN ('evaluado', 'convalidacion', 'renuncia', 'en_curso', 'otro')),
    aprobado_curricular    boolean,
    es_intento_evaluado    boolean NOT NULL,
    aprobacion_discrepa    boolean NOT NULL DEFAULT false,
    es_renuncia            boolean NOT NULL,
    tipo_renuncia          text,
    renuncia_repetida      boolean NOT NULL DEFAULT false,    -- second renuncia to the same course (RA19)
    es_convalidacion       boolean NOT NULL,
    en_curso               boolean NOT NULL,
    estado_conflicto       boolean NOT NULL DEFAULT false,
    n_equivalencias        integer NOT NULL DEFAULT 1 CHECK (n_equivalencias >= 1),
    carga_id               bigint  NOT NULL,
    CONSTRAINT inscripcion_asignatura_nk_uq UNIQUE NULLS NOT DISTINCT (periodo, persona_key, nrc, materia_curso_inscrito, estado),
    CONSTRAINT inscripcion_flags_ck CHECK (
        es_renuncia = (resultado_tipo = 'renuncia')
        AND es_convalidacion = (resultado_tipo = 'convalidacion')
        AND en_curso = (resultado_tipo = 'en_curso')
    ),
    CONSTRAINT inscripcion_evaluado_ck CHECK (NOT es_intento_evaluado OR (resultado_tipo = 'evaluado' AND nota_numerica IS NOT NULL)),
    CONSTRAINT inscripcion_heredada_ck CHECK (NOT nota_es_heredada OR resultado_tipo = 'convalidacion')
);

CREATE INDEX IF NOT EXISTS inscripcion_asignatura_persona_ix ON neural_core.inscripcion_asignatura (persona_key, periodo);

CREATE TABLE IF NOT EXISTS neural_core.inscripcion_equivalencia (
    equivalencia_id         bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    inscripcion_id          bigint  NOT NULL REFERENCES neural_core.inscripcion_asignatura (inscripcion_id) ON DELETE CASCADE,
    materia_curso_catalogo  text    NOT NULL,                 -- AAAA-99999 (R33)
    titulo_catalogo         text,
    catalogo_malla          text,
    nivel                   text,
    oportunidad             integer,
    filas_origen            integer NOT NULL DEFAULT 1 CHECK (filas_origen >= 1),
    CONSTRAINT inscripcion_equivalencia_nk_uq UNIQUE NULLS NOT DISTINCT
        (inscripcion_id, materia_curso_catalogo, catalogo_malla, oportunidad)
);

CREATE TABLE IF NOT EXISTS neural_core.seccion (
    periodo        text NOT NULL,
    nrc            text NOT NULL,
    paralelo       text,
    carrera        text,
    sede           text,
    departamento   text,
    cod_asignatura text,
    asignatura     text,
    tipo_clase     text,
    cupo           text,
    utilizado      text,
    PRIMARY KEY (periodo, nrc)
);

CREATE TABLE IF NOT EXISTS neural_core.seccion_docente (
    periodo       text NOT NULL,
    nrc           text NOT NULL,
    docente_key   text NOT NULL,
    tipo_profesor text,
    PRIMARY KEY (periodo, nrc, docente_key),
    FOREIGN KEY (periodo, nrc) REFERENCES neural_core.seccion (periodo, nrc)
);

-- ---------------------------------------------------------------------------------------------
-- 4.5 Outcomes
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS neural_core.titulacion (
    titulacion_id             bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    persona_key               text    NOT NULL REFERENCES neural_core.persona (persona_key),
    codigo_carrera            text    NOT NULL,
    catalogo                  text,
    fecha_titulacion          date,
    episodio_id               bigint  REFERENCES neural_core.episodio_programa (episodio_id),
    codigo_sies               text,
    year_ingreso              integer,
    semestre_ingreso          integer,
    duracion                  integer,
    year_titulacion           integer,
    semestres_suspendidos     integer,
    semestres_suspendidos_old integer,
    tipo_admision             text,
    carga_id                  bigint  NOT NULL,
    CONSTRAINT titulacion_nk_uq UNIQUE NULLS NOT DISTINCT (persona_key, codigo_carrera, catalogo, fecha_titulacion)
);

CREATE TABLE IF NOT EXISTS neural_core.matricula_postgrado (
    persona_key      text NOT NULL REFERENCES neural_core.persona (persona_key),
    cod_programa     text NOT NULL,
    periodo          text NOT NULL,
    cod_estado       text,
    estado           text,
    estado_matricula text,
    periodo_admision text,
    cod_admision     text,
    tipo_admision    text,
    catalogo         text,
    carga_id         bigint NOT NULL,
    PRIMARY KEY (persona_key, cod_programa, periodo)
);
