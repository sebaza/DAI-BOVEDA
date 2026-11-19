-- DAI Neural published responses in the institutional warehouse (read by wh-api for the GitHub Pages site).
--
-- Applied by scripts/publicar_warehouse_neural.py, which replaces the placeholder __ESQUEMA__ (after validating it against
-- ^[a-z_][a-z0-9_]*$) and runs it inside the same transaction as the load. Plain statements only (no psql meta-commands, no
-- DO blocks): the script splits on semicolons, so keep semicolons out of comments.
--
-- Grants are NOT here: the script copies the SELECT grants of __ESQUEMA__.percepcion_hecho_diario onto both tables.
-- Idempotent: CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS __ESQUEMA__.neural_respuesta (
    ruta        text        NOT NULL,
    consulta    text        NOT NULL,
    contenido   jsonb       NOT NULL,
    generado_en timestamptz NOT NULL,
    PRIMARY KEY (ruta, consulta)
);

CREATE TABLE IF NOT EXISTS __ESQUEMA__.neural_publicacion (
    id                 smallint    PRIMARY KEY CHECK (id = 1),
    publicado_en       timestamptz NOT NULL,
    version_exportador text        NOT NULL,
    respuestas         int         NOT NULL,
    bytes              bigint      NOT NULL
);
