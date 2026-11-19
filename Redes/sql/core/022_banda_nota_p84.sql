-- DAI Neural 022: P84 (DAI, 13-11-2026). The T2 grade band follows the institutional recognition scale:
-- reprobado < 4.0, unanimidad [4.0, 5.4), distincion [5.4, 6.4), maxima_distincion [6.4, 7.0]. The column is label side
-- (never a feature) and is rewritten when `python -m pipelines.snapshots.t2` rebuilds the table.
-- Idempotent: safe to run more than once.

ALTER TABLE neural_mart.snapshot_t2 DROP CONSTRAINT IF EXISTS snapshot_t2_banda_nota_check;
UPDATE neural_mart.snapshot_t2 SET banda_nota = NULL;
ALTER TABLE neural_mart.snapshot_t2 ADD CONSTRAINT snapshot_t2_banda_nota_check CHECK (banda_nota IN ('reprobado', 'unanimidad', 'distincion', 'maxima_distincion'));
