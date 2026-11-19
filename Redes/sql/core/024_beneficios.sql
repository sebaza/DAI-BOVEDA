-- DAI Neural 024: student financial benefits (banner.banner_beneficios, DAI 16-11-2026), staging table.
-- * neural_stg.banner_beneficios: one row per (year, person, program, benefit, coverage); `periodo` is the YEAR (integer),
--   the person is a pseudonymous key (HMAC), the program name (`carrera`) is not extracted (the code is enough).
-- Idempotent: safe to run more than once. Pseudonymous keys only.

CREATE TABLE IF NOT EXISTS neural_stg.banner_beneficios (
    stg_id          bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id        bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    periodo         integer,
    persona_key     text    NOT NULL,
    id_sede         integer,
    cod_carrera     text,
    financiamiento  text,
    cobertura       text,
    codigo          text,
    beneficio       text,
    benef_sem1      numeric,
    benef_sem2      numeric,
    total           numeric
);
CREATE INDEX IF NOT EXISTS banner_beneficios_carga_ix ON neural_stg.banner_beneficios (carga_id);
CREATE INDEX IF NOT EXISTS banner_beneficios_persona_ix ON neural_stg.banner_beneficios (persona_key, periodo);
