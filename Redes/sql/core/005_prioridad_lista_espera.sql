-- 005: waitlist routes of special programs (EB, EC, EM, EP) are waitlists (priority 3),
-- even though their tipo_qualitas is class 2. Decision DAI 11-11-2026 (RA30).
-- PostgreSQL 16 cannot change a generated expression in place, so the column is rebuilt.
-- Must stay in sync with pipelines/normalize/admission.py::via_priority
-- (tests/integration/test_schema.py::test_route_priority_sql_matches_python).

ALTER TABLE neural_meta.dic_tipo_admision DROP COLUMN IF EXISTS prioridad_via;

ALTER TABLE neural_meta.dic_tipo_admision ADD COLUMN prioridad_via smallint GENERATED ALWAYS AS (
    CASE
        WHEN cod_admision IN ('LE', 'EB', 'EC', 'EM', 'EP') THEN 3
        WHEN tipo_qualitas LIKE '2.%' THEN 1
        WHEN cod_admision IN ('LS', 'RP', 'OV', 'OA') THEN 2
        ELSE 4
    END) STORED;
