-- DAI Neural 010: fingerprint of the HMAC key used for the loaded data (a different key is detected, not silent).
-- Idempotent: safe to run more than once. Holds a non-reversible fingerprint, never the key.

CREATE TABLE IF NOT EXISTS neural_meta.huella_clave (
    id            smallint    PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    huella        text        NOT NULL CHECK (huella ~ '^[0-9a-f]{64}$'),
    registrada_en timestamptz NOT NULL DEFAULT now()
);
