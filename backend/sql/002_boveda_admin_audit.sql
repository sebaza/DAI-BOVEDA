-- Boveda global administrators + audit of raw comment text.
--
-- Requires 001_boveda_access.sql (references boveda.modulos).
-- Administrators are GLOBAL (not per module): they can open every active module and are the
-- only role allowed into the curation endpoints that return raw comment text.
-- Fail closed: an empty `administradores` table means nobody is an administrator.
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS boveda.administradores (
    -- Stored lowercased so lookups match regardless of how Google returns the address.
    email       text        PRIMARY KEY CHECK (email = lower(email) AND position('@' IN email) > 1),
    creado_en   timestamptz NOT NULL DEFAULT now(),
    creado_por  text
);

-- One row per request that returned raw comment text to an administrator.
-- Append-only by convention: the application only ever INSERTs here.
CREATE TABLE IF NOT EXISTS boveda.auditoria_texto (
    id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    admin_email     text        NOT NULL,
    modulo_id       text        NOT NULL REFERENCES boveda.modulos (id),
    endpoint        text        NOT NULL,
    comentario_ids  bigint[]    NOT NULL,
    visto_en        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS auditoria_texto_admin_visto_idx
    ON boveda.auditoria_texto (admin_email, visto_en);
