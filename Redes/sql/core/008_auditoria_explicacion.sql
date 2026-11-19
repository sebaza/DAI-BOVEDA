-- DAI Neural 008: reconciliation results carry a short explanation (a mismatch is recorded, never hidden).
-- Idempotent: safe to run more than once.

ALTER TABLE neural_meta.auditoria_resultado ADD COLUMN IF NOT EXISTS explicacion text;
