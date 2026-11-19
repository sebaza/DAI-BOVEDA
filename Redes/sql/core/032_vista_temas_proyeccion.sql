-- DAI Neural 032: "Lo que pasó" by topics and the new "Lo que viene" projection. Widens the block list of
-- neural_mart.vista_historica and creates neural_mart.vista_proyeccion (one row per block and filter, content as JSON).
-- AGGREGATES ONLY: groups of 10 or more people; no row-level prediction, no person key, no cell of 1-9 people.
-- Idempotent: safe to run more than once.
ALTER TABLE neural_mart.vista_historica DROP CONSTRAINT IF EXISTS vista_historica_bloque_check;
ALTER TABLE neural_mart.vista_historica
    ADD CONSTRAINT vista_historica_bloque_check CHECK (bloque IN (
        'meta', 'semestres', 'siguieron', 'por_facultad', 'eliminados', 'alcance',
        'perfil_ingreso', 'primer_semestre', 'ramos_reprobados', 'ramos_esperado', 'cuellos_botella',
        'semestre_malla', 'causales_programa', 'tiempo_egreso', 'senales', 'esperar_semestre'));

CREATE TABLE IF NOT EXISTS neural_mart.vista_proyeccion (
    bloque    text        NOT NULL CHECK (bloque IN ('meta', 'continuidad', 'eliminacion', 'egreso', 'umbral')),
    facultad  text        NOT NULL,
    contenido jsonb       NOT NULL,
    PRIMARY KEY (bloque, facultad)
);
