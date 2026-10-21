-- Boveda access control: one allowlist per module.
--
-- Lives in its own `boveda` schema, never in the worker's Percepcion database.
-- Fail closed: a module with no rows in accesos_modulo lets nobody in.
-- Idempotent: safe to run more than once.

CREATE SCHEMA IF NOT EXISTS boveda;

CREATE TABLE IF NOT EXISTS boveda.modulos (
    id          text        PRIMARY KEY CHECK (id ~ '^[a-z][a-z0-9_]*$'),
    nombre      text        NOT NULL,
    descripcion text,
    activo      boolean     NOT NULL DEFAULT true,
    creado_en   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS boveda.accesos_modulo (
    id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    modulo_id   text        NOT NULL REFERENCES boveda.modulos (id) ON DELETE CASCADE,
    -- Stored lowercased so lookups match regardless of how Google returns the address.
    email       text        NOT NULL CHECK (email = lower(email) AND position('@' IN email) > 1),
    -- lector: read only. equipo: read and write (events, curation, regenerate summary).
    rol         text        NOT NULL CHECK (rol IN ('lector', 'equipo')),
    creado_en   timestamptz NOT NULL DEFAULT now(),
    creado_por  text,
    CONSTRAINT accesos_modulo_modulo_email_uq UNIQUE (modulo_id, email)
);

-- The lobby lists every module a given email can open.
CREATE INDEX IF NOT EXISTS accesos_modulo_email_idx ON boveda.accesos_modulo (email);

INSERT INTO boveda.modulos (id, nombre, descripcion)
VALUES (
    'percepcion',
    'Termómetro Institucional',
    'Percepción de la comunidad UCN en redes sociales.'
)
ON CONFLICT (id) DO NOTHING;
