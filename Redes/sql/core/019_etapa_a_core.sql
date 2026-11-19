-- DAI Neural 019: stage A of the consolidated rebuild (DAI answers of 13-11-2026), core and meta layers.
-- * P54: several evaluated rows of one (persona, periodo, asignatura) -> the row with the highest `oportunidad` is the
--   result; the earlier rows stay in core flagged `reemplazada_mismo_periodo`, leave the evaluated attempts
--   (`es_intento_evaluado` = false) and carry no pass/fail (`aprobado_curricular` = NULL). Applied by build_core.
-- * P45: the period label `verano_invierno` splits into `verano` (suffix 25) and `invierno` (suffix 15); suffix 21 is
--   `excepcional` (still atypical). Mirrors pipelines/normalize/periods.py (tested).
-- * P76: faculty names (common.facultad_d through programa_d.facultad) and P77: postgrado program names and states
--   (banner.ban_estados_academicos_pos).
-- Idempotent: safe to run more than once. Pseudonymous keys only.

ALTER TABLE neural_core.intento_asignatura ADD COLUMN IF NOT EXISTS reemplazada_mismo_periodo boolean NOT NULL DEFAULT false;

ALTER TABLE neural_meta.calendario_periodo DROP CONSTRAINT IF EXISTS calendario_periodo_tipo_periodo_check;
UPDATE neural_meta.calendario_periodo SET tipo_periodo = 'invierno' WHERE sufijo = '15';
UPDATE neural_meta.calendario_periodo SET tipo_periodo = 'verano' WHERE sufijo = '25';
UPDATE neural_meta.calendario_periodo SET tipo_periodo = 'excepcional' WHERE sufijo = '21';
ALTER TABLE neural_meta.calendario_periodo DROP CONSTRAINT IF EXISTS calendario_periodo_tipo_check;
ALTER TABLE neural_meta.calendario_periodo ADD CONSTRAINT calendario_periodo_tipo_check CHECK (tipo_periodo IN (
    'regular_1', 'regular_2', 'verano', 'invierno', 'excepcional', 'postgrado', 'otro'));

-- ---- faculty dictionary (P76) -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS neural_stg.facultad_d (
    stg_id              bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id            bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    id                  bigint,
    cod_unidad_organica text,
    nombre_unidad       text,
    nivel_jerarquico    text,
    cod_sede            text,
    nombre_vigente      text
);

CREATE TABLE IF NOT EXISTS neural_core.facultad (
    facultad_id         bigint  PRIMARY KEY,                  -- = programa.facultad
    cod_unidad_organica text,
    nombre_facultad     text    NOT NULL,                     -- facultad_d.nombre_unidad
    nombre_vigente      text,
    nivel_jerarquico    text,                                 -- 3 = faculty / vice-rectorate, 4 = school / institute
    cod_sede            text
);

-- ---- postgrado states and programs (P77, P78, P79) ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS neural_stg.ban_estados_academicos_pos (
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
    nombre_banner    text,
    nombre_estandar  text,
    cod_estado       text,
    nombre_estado    text,
    fecha_estado     timestamp
);

CREATE INDEX IF NOT EXISTS ban_estados_academicos_pos_carga_ix ON neural_stg.ban_estados_academicos_pos (carga_id);
CREATE INDEX IF NOT EXISTS ban_estados_academicos_pos_persona_ix ON neural_stg.ban_estados_academicos_pos (persona_key, periodo);

CREATE TABLE IF NOT EXISTS neural_core.programa_postgrado (
    cod_programa         text    PRIMARY KEY,
    nombre_banner        text,
    nombre_estandar      text,                                -- NULL for the fictitious programs and for most diplomados (Banner is normalising)
    nivel_derivado       text    NOT NULL CHECK (nivel_derivado IN ('magister', 'doctorado', 'diplomado', 'otro', 'sin_nombre')),
    id_nivel_diccionario bigint,                              -- programa_d.id_nivel when the code is in the program dictionary
    primer_periodo       text,
    ultimo_periodo       text,
    filas                integer NOT NULL
);

-- One row per state row of the source; no foreign key to persona (most postgrado persons are not pregrado trajectories).
CREATE TABLE IF NOT EXISTS neural_core.estado_postgrado (
    estado_postgrado_id bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    persona_key         text    NOT NULL,
    sorlcur             numeric,
    periodo             text    NOT NULL,
    cod_programa        text,
    cod_estado          text,
    nombre_estado       text,
    fecha_estado        timestamp,
    cod_admision        text,
    periodo_admision    text,
    catalogo            text,
    carga_id            bigint  NOT NULL
);

CREATE INDEX IF NOT EXISTS estado_postgrado_persona_ix ON neural_core.estado_postgrado (persona_key, periodo);
