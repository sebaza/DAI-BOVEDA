-- DAI Neural 003: staging (neural_stg). Pseudonymized 1:1 copy of the needed columns of each current
-- Warehouse view. RUT and teacher RUT are replaced by persona_key / docente_key (HMAC) before insert.
-- Excluded on purpose (see docs/05_modelo_datos.md, principle 5): names, e-mails, phones, birth date,
-- passport, nationality, school name/code, city/province/commune of residence.
-- Allowed context (decisions M1/M2): sexo (fairness evaluation only, never a filter or feature for
-- decisions), region_colegio, comuna_colegio, cod_comuna.
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_stg.ban_estados_academicos (
    stg_id           bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id         bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    persona_key      text    NOT NULL,
    sorlcur          numeric,
    periodo          text,
    plan_estudios    numeric,
    catalogo         text,
    cod_admision     text,
    admision         text,
    periodo_admision text,
    cod_programa     text,
    cod_estado       text,
    nombre_estado    text,
    fecha_estado     timestamp,
    cod_causal       text,
    causal           text,
    sexo             text
);

CREATE TABLE IF NOT EXISTS neural_stg.ban_historia_notas (
    stg_id       bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id     bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    persona_key  text    NOT NULL,
    periodo      text,
    cod_carrera  text,
    catalogo     text,
    plan_estudio numeric,
    materia      text,
    curso        text,
    titulo       text,
    nota         text,
    creditos     numeric,
    oportunidad  text,
    nrc          text,
    comentario   text,
    cod_depto    text,
    nom_depto    text
);

CREATE TABLE IF NOT EXISTS neural_stg.ban_inscripciones (
    stg_id                 bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id               bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    persona_key            text    NOT NULL,
    nivel                  text,
    catalogo_malla         text,
    materia_curso_catalogo text,
    titulo_catalogo        text,
    materia_curso_inscrito text,
    titulo_inscrito        text,
    nrc                    text,
    nota                   text,
    aprobacion             text,
    oportunidad            numeric,
    estado                 text,
    periodo                text
);

CREATE TABLE IF NOT EXISTS neural_stg.ban_oferta_academica (
    stg_id        bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id      bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    periodo       text,
    nrc           text,
    paralelo      text,
    carrera       text,
    sede          text,
    departamento  text,
    cod_asignatura text,
    asignatura    text,
    tipo_clase    text,
    cupo          text,
    utilizado     text,
    docente_key   text,
    tipo_profesor text
);

CREATE TABLE IF NOT EXISTS neural_stg.banner_admision (
    stg_id                bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id              bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    persona_key           text,
    year_admision         text,
    cod_carrera           text,
    id_sede               integer,
    cod_demre             text,
    pref_demre            text,
    preferencia           text,
    cod_admision          text,
    desc_admision         text,
    matricula             text,
    fecha_matricula       text,
    tipo_colegio          text,
    depend_colegio        text,
    region_colegio        text,
    comuna_colegio        text,
    cod_comuna            text,
    sexo                  text,
    puntaje_leng          text,
    puntaje_mat           text,
    puntaje_ciencias      text,
    puntaje_historia      text,
    puntaje_nem           text,
    puntaje_ranking       text,
    notas_em              text,
    promedio_lm           text,
    ponderado             text,
    ponderado_normalizado text
);

CREATE TABLE IF NOT EXISTS neural_stg.banner_matricula (
    stg_id           bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id         bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    persona_key      text    NOT NULL,
    year             integer,
    cod_carrera      text,
    catalogo         text,
    year_admision    integer,
    periodo_admision text,
    cod_admision     text,
    tipo_admision    text,
    fecha_estado     date,
    sede             text,
    facultad         text
);

CREATE TABLE IF NOT EXISTS neural_stg.banner_titulados (
    stg_id                    bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id                  bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    persona_key               text    NOT NULL,
    codigo_carrera            text,
    codigo_sies               text,
    catalogo                  text,
    sede                      text,
    year_ingreso              integer,
    semestre_ingreso          integer,
    duracion                  integer,
    year_titulacion           integer,
    fecha_titulacion          date,
    semestres_suspendidos     integer,
    semestres_suspendidos_old integer,
    tipo_admision             text
);

CREATE TABLE IF NOT EXISTS neural_stg.banner_estudiantes_postgrado (
    stg_id           bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id         bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    persona_key      text    NOT NULL,
    cod_programa     text,
    periodo          text,
    cod_estado       text,
    estado           text,
    fecha_estado     date,
    estado_matricula text,
    periodo_admision text,
    cod_admision     text,
    tipo_admision    text,
    catalogo         text,
    codigo_sies      text
);

CREATE TABLE IF NOT EXISTS neural_stg.ban_malla_programa (
    stg_id              bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id            bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    malla_program_code  text,
    malla_ctlg          text,
    malla_materiacurso  text,
    malla_semestre      text,
    malla_formacion     text,
    malla_creditaje     text,
    malla_asignatura    text,
    malla_area          text,
    malla_depto         text,
    malla_depto_desc    text
);

CREATE TABLE IF NOT EXISTS neural_stg.malla_programa_prereq (
    stg_id                   bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id                 bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    cod_programa             text,
    catalogo                 text,
    codigo_asignatura        text,
    codigo_asignatura_repreq text
);

CREATE TABLE IF NOT EXISTS neural_stg.banner_catalogos (
    stg_id      bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id    bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    cod_carrera text,
    catalogo    text,
    duracion    integer
);

CREATE TABLE IF NOT EXISTS neural_stg.programa_d (
    stg_id             bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id           bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    id                 bigint,
    cod_banner         text,
    programa_predecesor bigint,
    valid_program      boolean,
    id_nivel           bigint,
    nombre_programa    text,
    area_conocimiento  text,
    facultad           bigint,
    sede               bigint,
    cod_demre          text
);

-- Lookups by load for idempotent re-extraction and reconciliation.
CREATE INDEX IF NOT EXISTS ban_estados_academicos_carga_ix ON neural_stg.ban_estados_academicos (carga_id);
CREATE INDEX IF NOT EXISTS ban_historia_notas_carga_ix ON neural_stg.ban_historia_notas (carga_id);
CREATE INDEX IF NOT EXISTS ban_inscripciones_carga_ix ON neural_stg.ban_inscripciones (carga_id);
CREATE INDEX IF NOT EXISTS ban_oferta_academica_carga_ix ON neural_stg.ban_oferta_academica (carga_id);
CREATE INDEX IF NOT EXISTS banner_admision_carga_ix ON neural_stg.banner_admision (carga_id);
CREATE INDEX IF NOT EXISTS banner_matricula_carga_ix ON neural_stg.banner_matricula (carga_id);
CREATE INDEX IF NOT EXISTS banner_titulados_carga_ix ON neural_stg.banner_titulados (carga_id);
CREATE INDEX IF NOT EXISTS banner_estudiantes_postgrado_carga_ix ON neural_stg.banner_estudiantes_postgrado (carga_id);
CREATE INDEX IF NOT EXISTS ban_malla_programa_carga_ix ON neural_stg.ban_malla_programa (carga_id);
CREATE INDEX IF NOT EXISTS malla_programa_prereq_carga_ix ON neural_stg.malla_programa_prereq (carga_id);
CREATE INDEX IF NOT EXISTS banner_catalogos_carga_ix ON neural_stg.banner_catalogos (carga_id);
CREATE INDEX IF NOT EXISTS programa_d_carga_ix ON neural_stg.programa_d (carga_id);
-- Natural-key probes used by the reconciliation queries (persona_key + period).
CREATE INDEX IF NOT EXISTS ban_estados_academicos_persona_ix ON neural_stg.ban_estados_academicos (persona_key, periodo, sorlcur);
CREATE INDEX IF NOT EXISTS ban_historia_notas_persona_ix ON neural_stg.ban_historia_notas (persona_key, periodo);
CREATE INDEX IF NOT EXISTS ban_inscripciones_persona_ix ON neural_stg.ban_inscripciones (persona_key, periodo);
