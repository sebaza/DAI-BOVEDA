-- DAI Neural 015: transfers between programs (P61, D48-D52). Rebuilt as a whole by `python -m pipelines.marts`
-- (docs/00_plan.md). One row per transition of a person from an origin undergraduate episode to the next
-- episode of a different program, under the conservative rules of `pipelines/marts/rules_traslados.py`.
-- Pseudonymous keys only (persona_key, like the other episode-level marts); the API serves aggregates with
-- suppression of groups under 10 people and never a row.
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.programa_traslados (
    origen_episodio_id      bigint  PRIMARY KEY,               -- each origin episode has at most one transition
    destino_episodio_id     bigint  NOT NULL,
    persona_key             text    NOT NULL,
    cod_programa_origen     text    NOT NULL,
    cod_programa_destino    text    NOT NULL,
    periodo_admision_origen text,
    anio_cohorte_origen     integer,                           -- admission year of the origin episode
    ultimo_periodo_origen   text    NOT NULL,
    primer_periodo_destino  text    NOT NULL,
    anio_traslado           integer NOT NULL,                  -- year of the first period of the destination
    cod_admision_destino    text,
    ultimo_estado_clase_origen text,
    brecha_periodos         integer NOT NULL,                  -- regular slots between both episodes (D47 links may be negative)
    tipo                    text    NOT NULL CHECK (tipo IN ('eleccion_especialidad', 'cambio_ciclo',
                                'continuacion_estudios', 'cambio_carrera', 'traslado_sede', 'traslado_otro')),
    regla                   text    NOT NULL CHECK (regla IN ('d47', 'via_es', 'ventana')),
    cuenta_abandono         boolean NOT NULL,                  -- the transfer is a loss for the origin program
    ambiguo                 boolean NOT NULL                   -- another episode of a third program starts in the same window
);

CREATE INDEX IF NOT EXISTS programa_traslados_origen_ix ON neural_mart.programa_traslados (cod_programa_origen, anio_traslado);
CREATE INDEX IF NOT EXISTS programa_traslados_destino_ix ON neural_mart.programa_traslados (cod_programa_destino, anio_traslado);
