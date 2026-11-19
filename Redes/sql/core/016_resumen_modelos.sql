-- DAI Neural 016: aggregate benchmark results of the models for the "Modelos" view of the Boveda.
-- Filled by `python -m tools.exportar_resumen_modelos` from artefactos/resultados_t{1,2,3}.json (gitignored).
-- AGGREGATES ONLY: metrics with their bootstrap intervals, paired differences, architecture sizes and the
-- headline conclusions. No row-level prediction, no person key and no group below the minimum size ever lives here.
-- Individual predictions are not approved for use until the institutional review (Gate 4).
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.resumen_modelos (
    tarea        text    NOT NULL CHECK (tarea IN ('t1', 't2', 't3')),
    corte_k      integer NOT NULL,                      -- cut semester (T1: 1-2, T3: 0/2/4, T2: 0 = not applicable)
    conjunto     text    NOT NULL,                      -- 'test'
    modelo       text    NOT NULL,
    modelo_nombre text   NOT NULL,
    familia      text    NOT NULL,                      -- referencia, regresion, arboles, red, red_grafo
    escalon      integer NOT NULL,                      -- rung of the ablation ladder (0 = reference)
    escalon_nombre text  NOT NULL,
    metrica      text    NOT NULL,
    valor        numeric,
    ic_inf       numeric,
    ic_sup       numeric,
    n_evaluacion integer,                               -- size of the evaluation set (aggregate)
    PRIMARY KEY (tarea, corte_k, conjunto, modelo, metrica)
);

CREATE TABLE IF NOT EXISTS neural_mart.resumen_modelos_delta (
    tarea        text    NOT NULL CHECK (tarea IN ('t1', 't2', 't3')),
    corte_k      integer NOT NULL,
    conjunto     text    NOT NULL,
    modelo_a     text    NOT NULL,                      -- difference A - B
    modelo_b     text    NOT NULL,
    metrica      text    NOT NULL,
    delta        numeric,
    ic_inf       numeric,
    ic_sup       numeric,
    veredicto    text    NOT NULL CHECK (veredicto IN ('mejora', 'sin_diferencia', 'empeora')),
    PRIMARY KEY (tarea, corte_k, conjunto, modelo_a, modelo_b, metrica)
);

CREATE TABLE IF NOT EXISTS neural_mart.resumen_modelos_info (
    tarea        text    NOT NULL CHECK (tarea IN ('t1', 't2', 't3')),
    corte_k      integer NOT NULL,
    modelo       text    NOT NULL,
    clave        text    NOT NULL,                      -- n_parametros, hidden, gru_hidden, n_variables, ...
    valor_num    numeric,
    valor_texto  text,
    PRIMARY KEY (tarea, corte_k, modelo, clave)
);

CREATE TABLE IF NOT EXISTS neural_mart.resumen_modelos_titular (
    tarea        text    NOT NULL CHECK (tarea IN ('t1', 't2', 't3')),
    orden        integer NOT NULL,
    clave        text    NOT NULL,                      -- stable identifier of the conclusion
    texto        text    NOT NULL,
    PRIMARY KEY (tarea, orden)
);

CREATE TABLE IF NOT EXISTS neural_mart.resumen_modelos_construccion (
    id            smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    construido_en timestamptz NOT NULL DEFAULT now(),
    filas         integer NOT NULL
);
