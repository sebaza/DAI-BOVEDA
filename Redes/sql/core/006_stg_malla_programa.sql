-- DAI Neural 006: staging of the legacy malla_programa (audit only; the official curriculum is
-- ban_malla_programa, P17). It is read to reproduce the prerequisite coverage of r3#R19.
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_stg.malla_programa (
    stg_id            bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id          bigint  NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    cod_programa      bigint,                                -- = programa_d.id
    catalogo          text,
    codigo_asignatura text,
    nombre_asignatura text,
    creditos          integer,
    nivel             integer
);

CREATE INDEX IF NOT EXISTS malla_programa_carga_ix ON neural_stg.malla_programa (carga_id);
