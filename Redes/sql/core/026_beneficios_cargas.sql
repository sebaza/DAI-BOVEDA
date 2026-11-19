-- DAI Neural 026: load history of the student benefits (banner.banner_beneficios_full, DAI 16-11-2026, P90/P91/P93), staging.
-- * neural_stg.banner_beneficios_cargas: the history compressed to ONE row per (year, person, program, benefit code, coverage):
--   the first and last Warehouse load (timestamp_carga, epoch ms) in which the row appears, how many loads contain it, whether it
--   is in the last load, and the first-semester / second-semester amounts at the first and at the last load. The person is a
--   pseudonymous key (HMAC); no RUT is stored.
-- * neural_stg.banner_beneficios_cargas_cal: calendar of the loads per year (timestamp_carga, year, rows). It lets a consumer
--   find "the last load on or before a cut date" and detect rows that disappear and reappear (n_loads below the loads of the
--   year between first_ts and last_ts).
-- Idempotent: safe to run more than once. Pseudonymous keys only.

CREATE TABLE IF NOT EXISTS neural_stg.banner_beneficios_cargas (
    stg_id                  bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id                bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    periodo                 integer NOT NULL,
    persona_key             text    NOT NULL,
    cod_carrera             text,
    codigo                  text,
    cobertura               text,
    first_ts                bigint  NOT NULL,
    last_ts                 bigint  NOT NULL,
    n_loads                 integer NOT NULL,
    presente_ultima_carga   boolean NOT NULL,
    sem1_primera            numeric,
    sem2_primera            numeric,
    sem1_ultima             numeric,
    sem2_ultima             numeric
);
CREATE INDEX IF NOT EXISTS banner_beneficios_cargas_carga_ix ON neural_stg.banner_beneficios_cargas (carga_id);
CREATE INDEX IF NOT EXISTS banner_beneficios_cargas_persona_ix ON neural_stg.banner_beneficios_cargas (persona_key, periodo);

CREATE TABLE IF NOT EXISTS neural_stg.banner_beneficios_cargas_cal (
    stg_id          bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id        bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    timestamp_carga bigint  NOT NULL,
    periodo         integer NOT NULL,
    filas           integer NOT NULL
);
CREATE INDEX IF NOT EXISTS banner_beneficios_cargas_cal_carga_ix ON neural_stg.banner_beneficios_cargas_cal (carga_id);
