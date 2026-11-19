-- DAI Neural 023: per-task summary (T1-T6) for the "Modelos" view of the Boveda.
-- Filled by `python tools/exportar_resumen_modelos.py` from artefactos/resultados_t{1,2,3,45,6}.json (gitignored) and the
-- program / faculty dictionary of neural_core. Complements 016 (which keeps serving the architecture diagrams).
-- AGGREGATES ONLY: metrics with their bootstrap intervals, paired differences, calibration deciles and expected-versus-
-- observed rates by program and faculty. No row-level prediction, no person key, and no group below the publication rules
-- (n < 10 people, or a rate over fewer than 10 events) ever lives here. Individual predictions are not approved for use.
-- `variante`: T5 evaluation of the label (actual, efectiva, sin_dudosos), T6 horizon (h2 = 1 year, h4 = 2 years), else base.
-- `corte_k`: cut semester (T1: 1-2, T3: 0/2/4, T4-T5: 2/4); 0 when it does not apply (T2, T6).
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.resumen_tarea (
    tarea              text    PRIMARY KEY CHECK (tarea IN ('t1', 't2', 't3', 't4', 't5', 't6')),
    orden              integer NOT NULL,
    nombre             text    NOT NULL,
    pregunta           text    NOT NULL,                  -- what is predicted, in plain Spanish
    poblacion          text    NOT NULL,                  -- population, cut, horizon and splits
    evento             text    NOT NULL,                  -- name of the event ("no continuidad observada", ...)
    estado             text    NOT NULL CHECK (estado IN ('completo', 'exploratorio', 'dato_en_revision')),
    estado_etiqueta    text    NOT NULL,
    veredicto_redes    text    NOT NULL,                  -- do the neural nets add signal (from the reports)
    metrica_titular    text    NOT NULL,
    metrica_secundaria text
);

CREATE TABLE IF NOT EXISTS neural_mart.resumen_tarea_nota (
    tarea  text    NOT NULL CHECK (tarea IN ('t1', 't2', 't3', 't4', 't5', 't6')),
    tipo   text    NOT NULL CHECK (tipo IN ('dato', 'pendiente', 'limite')),
    orden  integer NOT NULL,
    texto  text    NOT NULL,
    PRIMARY KEY (tarea, tipo, orden)
);

CREATE TABLE IF NOT EXISTS neural_mart.resumen_tarea_vista (
    tarea               text    NOT NULL CHECK (tarea IN ('t1', 't2', 't3', 't4', 't5', 't6')),
    variante            text    NOT NULL,
    corte_k             integer NOT NULL,
    etiqueta            text    NOT NULL,
    principal           boolean NOT NULL,                 -- the view shown first (exactly one per task)
    conservado_modelo   text,                             -- the kept model of the benchmark
    referencia_modelo   text,                             -- the baseline it is compared with
    metrica_titular     text    NOT NULL,
    metrica_secundaria  text,
    concluyente         boolean NOT NULL,
    pronostico_agregado text    NOT NULL CHECK (pronostico_agregado IN ('confiable', 'descriptivo', 'no_confiable', 'no_disponible')),
    nota                text,
    PRIMARY KEY (tarea, variante, corte_k)
);

CREATE TABLE IF NOT EXISTS neural_mart.resumen_tarea_particion (
    tarea     text    NOT NULL CHECK (tarea IN ('t1', 't2', 't3', 't4', 't5', 't6')),
    variante  text    NOT NULL,
    corte_k   integer NOT NULL,
    particion text    NOT NULL,                           -- train, valid, test, posterior, todas
    n         integer NOT NULL,
    eventos   integer,
    tasa      numeric,
    tasa_inf  numeric,
    tasa_sup  numeric,
    PRIMARY KEY (tarea, variante, corte_k, particion)
);

CREATE TABLE IF NOT EXISTS neural_mart.resumen_tarea_metrica (
    tarea          text    NOT NULL CHECK (tarea IN ('t1', 't2', 't3', 't4', 't5', 't6')),
    variante       text    NOT NULL,
    corte_k        integer NOT NULL,
    modelo         text    NOT NULL,
    modelo_nombre  text    NOT NULL,
    familia        text    NOT NULL,                      -- referencia, regresion, arboles, red, red_grafo
    escalon        integer NOT NULL,
    escalon_nombre text    NOT NULL,
    metrica        text    NOT NULL,
    valor          numeric,
    ic_inf         numeric,
    ic_sup         numeric,
    n_evaluacion   integer,
    conservado     boolean NOT NULL,
    PRIMARY KEY (tarea, variante, corte_k, modelo, metrica)
);

CREATE TABLE IF NOT EXISTS neural_mart.resumen_tarea_delta (
    tarea     text    NOT NULL CHECK (tarea IN ('t1', 't2', 't3', 't4', 't5', 't6')),
    variante  text    NOT NULL,
    corte_k   integer NOT NULL,
    modelo_a  text    NOT NULL,                           -- difference A - B
    modelo_b  text    NOT NULL,
    metrica   text    NOT NULL,
    delta     numeric,
    ic_inf    numeric,
    ic_sup    numeric,
    veredicto text    NOT NULL CHECK (veredicto IN ('mejora', 'sin_diferencia', 'empeora')),
    PRIMARY KEY (tarea, variante, corte_k, modelo_a, modelo_b, metrica)
);

CREATE TABLE IF NOT EXISTS neural_mart.resumen_tarea_calibracion (
    tarea          text    NOT NULL CHECK (tarea IN ('t1', 't2', 't3', 't4', 't5', 't6')),
    variante       text    NOT NULL,
    corte_k        integer NOT NULL,
    modelo         text    NOT NULL,
    decil          integer NOT NULL,                      -- risk group (decile; T6 uses its own few groups)
    n              integer NOT NULL CHECK (n >= 10),
    riesgo_medio   numeric,
    tasa_observada numeric,
    PRIMARY KEY (tarea, variante, corte_k, modelo, decil)
);

CREATE TABLE IF NOT EXISTS neural_mart.resumen_tarea_grupo (
    tarea      text    NOT NULL CHECK (tarea IN ('t1', 't2', 't3', 't4', 't5', 't6')),
    variante   text    NOT NULL,
    corte_k    integer NOT NULL,
    nivel      text    NOT NULL CHECK (nivel IN ('programa', 'facultad', 'nivel_postgrado')),
    categoria  text    NOT NULL,                          -- T2: grade band; '' otherwise
    grupo      text    NOT NULL,                          -- program code, faculty name or postgrado level
    nombre     text    NOT NULL,                          -- program or faculty NAME (never a bare faculty code)
    facultad   text,                                      -- faculty name of a program
    n          integer NOT NULL CHECK (n >= 10),
    eventos    integer CHECK (eventos IS NULL OR eventos >= 10),
    observada  numeric,
    obs_inf    numeric,
    obs_sup    numeric,
    esperada   numeric,                                   -- aggregate forecast of the group (NULL when not reportable)
    esp_inf    numeric,
    esp_sup    numeric,
    referencia numeric,                                   -- historical-rate baseline
    ap         numeric,
    roc_auc    numeric,
    PRIMARY KEY (tarea, variante, corte_k, nivel, categoria, grupo)
);

CREATE TABLE IF NOT EXISTS neural_mart.resumen_tarea_grupo_resumen (
    tarea              text    NOT NULL CHECK (tarea IN ('t1', 't2', 't3', 't4', 't5', 't6')),
    variante           text    NOT NULL,
    corte_k            integer NOT NULL,
    nivel              text    NOT NULL CHECK (nivel IN ('programa', 'facultad', 'nivel_postgrado')),
    categoria          text    NOT NULL,
    grupos_total       integer,
    grupos_reportables integer,
    grupos_suprimidos  integer,
    mae_modelo         numeric,
    mae_base           numeric,
    spearman           numeric,
    n_min              integer,
    eventos_min        integer,
    PRIMARY KEY (tarea, variante, corte_k, nivel, categoria)
);
