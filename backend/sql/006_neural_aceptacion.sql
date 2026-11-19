-- Aceptación de la declaración de confidencialidad por módulo (hoy: DAI Neural).
--
-- Quién aceptó, cuándo y qué versión del texto. Una fila por (módulo, correo, versión): aceptar una versión
-- nueva no borra las anteriores y una versión antigua no desbloquea la actual.
-- Vive en el esquema `boveda` (la conexión de Neural es de solo lectura). Falla cerrado: sin fila, no hay acceso.
-- Requiere 001_boveda_access.sql. Idempotente: se puede ejecutar más de una vez.

CREATE TABLE IF NOT EXISTS boveda.aceptaciones_modulo (
    modulo_id     text        NOT NULL REFERENCES boveda.modulos (id) ON DELETE CASCADE,
    -- Minúsculas, igual que accesos_modulo: la búsqueda no depende de cómo Google devuelve el correo.
    email         text        NOT NULL CHECK (email = lower(email) AND position('@' IN email) > 1),
    version_texto text        NOT NULL CHECK (version_texto <> ''),
    aceptado_en   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (modulo_id, email, version_texto)
);
