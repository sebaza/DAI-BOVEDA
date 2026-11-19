-- DAI Neural 002: control tables, dictionaries and the period calendar (neural_meta).
-- Idempotent: safe to run more than once. Rules: docs/03_reglas_academicas.md, model: docs/05_modelo_datos.md.

CREATE TABLE IF NOT EXISTS neural_meta.schema_migraciones (
    nombre      text        PRIMARY KEY,
    sha256      text        NOT NULL,
    aplicado_en timestamptz NOT NULL DEFAULT now()
);

-- Extraction runs and provenance. A source + Warehouse load timestamp is loaded once (only 'ok' runs count).
CREATE TABLE IF NOT EXISTS neural_meta.carga_extraccion (
    carga_id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fuente             text        NOT NULL,
    timestamp_carga_wh bigint,
    filas_origen       bigint,
    filas_insertadas   bigint,
    sql_sha256         text,
    iniciado_en        timestamptz NOT NULL DEFAULT now(),
    terminado_en       timestamptz,
    estado             text        NOT NULL DEFAULT 'en_curso' CHECK (estado IN ('en_curso', 'ok', 'error'))
);

CREATE UNIQUE INDEX IF NOT EXISTS carga_extraccion_fuente_ts_ok_uq
    ON neural_meta.carga_extraccion (fuente, timestamp_carga_wh)
    WHERE estado = 'ok';

-- Reconciliation results (Gate 2).
CREATE TABLE IF NOT EXISTS neural_meta.auditoria_resultado (
    carga_id        bigint      NOT NULL REFERENCES neural_meta.carga_extraccion (carga_id),
    chequeo         text        NOT NULL,
    valor_esperado  text,
    valor_obtenido  text,
    ok              boolean     NOT NULL,
    medido_en       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (carga_id, chequeo)
);

-- State dictionary (R01). es_terminal stays NULL: the business definition is not confirmed.
CREATE TABLE IF NOT EXISTS neural_meta.dic_estado (
    cod_estado            text    PRIMARY KEY,
    nombre_estado         text    NOT NULL,
    clase_estado          text    NOT NULL CHECK (clase_estado IN (
        'matricula', 'interrupcion', 'salida', 'reingreso', 'cambio_ciclo',
        'egreso_titulacion', 'correccion_sistema', 'otro')),
    es_terminal           boolean,
    es_correccion_sistema boolean NOT NULL DEFAULT false,
    fuente_regla          text
);

INSERT INTO neural_meta.dic_estado (cod_estado, nombre_estado, clase_estado, es_correccion_sistema, fuente_regla)
VALUES
    ('M', 'Matriculado', 'matricula', false, 'R01 + 05 s3'),
    ('J', 'Matrícula en Trámite', 'matricula', false, 'R01 + 05 s3'),
    ('N', 'Nuevo', 'matricula', false, 'R01 + 05 s3'),
    ('Ñ', 'Matricula Fuera Periodo', 'matricula', false, 'R01 + 05 s3'),
    ('P', 'Retiro Temporal', 'interrupcion', false, 'R01 + 05 s3'),
    ('Q', 'Retiro Temporal Excepción', 'interrupcion', false, 'R01 + 05 s3'),
    ('4', 'Suspensión Temporal', 'interrupcion', false, 'R01 + 05 s3'),
    ('A', 'Anulación de Semestre', 'interrupcion', false, 'R01 + 05 s3'),
    ('S', 'Intercambio Saliente Total', 'interrupcion', false, 'R01 + 05 s3'),
    ('#', 'Intercambio Saliente Parcial', 'interrupcion', false, 'R01 + 05 s3'),
    ('E', 'Eliminado', 'salida', false, 'R01 + 05 s3'),
    ('B', 'Renuncia Alumno', 'salida', false, 'R01 + 05 s3'),
    ('F', 'Renuncia Admisión', 'salida', false, 'R01 + 05 s3'),
    ('O', 'No Continuidad', 'salida', false, 'R01 + 05 s3'),
    ('R', 'Retracto', 'salida', false, 'R01 + 05 s3'),
    ('3', 'No Matricula Admision', 'salida', false, 'R01 + 05 s3'),
    ('9', 'Matricula Anulada', 'salida', false, 'R01 + 05 s3'),
    ('X', 'Expulsado', 'salida', false, 'R01 + 05 s3'),
    ('6', 'Sancionado Eliminado', 'salida', false, 'R01 + 05 s3'),
    ('H', 'Sancionado', 'salida', false, 'R01 + 05 s3'),
    ('I', 'Reintegro', 'reingreso', false, 'R01 + 05 s3'),
    ('Y', 'Reintegro por Rectificación', 'reingreso', false, 'R01 + 05 s3'),
    ('D', 'Cambio de Ciclo', 'cambio_ciclo', false, 'R01 + 05 s3'),
    ('G', 'Egresado', 'egreso_titulacion', false, 'R01 + 05 s3'),
    ('Z', 'Malla Completa', 'egreso_titulacion', false, 'R01 + 05 s3'),
    ('K', 'Expediente Titulo', 'egreso_titulacion', false, 'R01 + 05 s3'),
    ('L', 'Licenciado', 'egreso_titulacion', false, 'R01 + 05 s3'),
    ('U', 'Titulado', 'egreso_titulacion', false, 'R01 + 05 s3'),
    ('1', 'Reversa Cambio Ciclo Prof', 'correccion_sistema', true, 'R01 + RA06'),
    ('2', 'Reversa G, K, Reciclaje, CPlan', 'correccion_sistema', true, 'R01 + RA06'),
    ('5', 'Reversa Malla Completa', 'correccion_sistema', true, 'R01 + RA06'),
    ('T', 'Intercambio Entrante', 'otro', false, 'R01 + 05 s3'),
    ('0', 'No Regular', 'otro', false, 'R01 + 05 s3')
ON CONFLICT (cod_estado) DO NOTHING;

-- Admission types (R02). A NULL cod_admision in the source is imputed to 'NN' (flagged) in core.
CREATE TABLE IF NOT EXISTS neural_meta.dic_tipo_admision (
    cod_admision      text    PRIMARY KEY,
    admision          text    NOT NULL,
    tipo_qualitas     text,
    tipo_cna          text,
    ingreso_ordinario boolean,
    ingreso_total     boolean,
    -- Route priority (RA30): 1 special, 2 regular selection, 3 waitlist LE, 4 rest. Lower wins.
    prioridad_via     smallint GENERATED ALWAYS AS (
        CASE
            WHEN tipo_qualitas LIKE '2.%' THEN 1
            WHEN cod_admision IN ('LS', 'RP', 'OV', 'OA') THEN 2
            WHEN cod_admision = 'LE' THEN 3
            ELSE 4
        END) STORED
);

INSERT INTO neural_meta.dic_tipo_admision (cod_admision, admision, tipo_qualitas, tipo_cna, ingreso_ordinario, ingreso_total)
VALUES
    ('AR', 'IEP-Ingreso de Artista', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('BE', 'IEP-Ingreso Cupo Especial BEA', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', true, true),
    ('CC', 'Cambio de Carrera', '3. Otros Ingresos o Cambio de Carrera', '4. Otros Ingresos o Cambio de Carrera', false, true),
    ('CE', 'IEP-Ceduc', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('CN', 'Carrera Continuidad', 'Carrera Continuidad', 'Carrera Continuidad', false, true),
    ('CO', 'IEP-Ingreso Especial Teologico', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('CS', 'Cambio de Sede (Misma Carrera)', '3. Otros Ingresos o Cambio de Carrera', '4. Otros Ingresos o Cambio de Carrera', false, true),
    ('DE', 'IEP-Ingreso Deportista', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('EB', 'IEP-Lista Espera BEA', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('EC', 'IEP-Lista Espera Pace', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('EE', 'IEP-Enlace Escolar', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('EM', 'IEP-Lista Espera Mujeres cient', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('EP', 'IEP-Excepción Lista espera Rep', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('ES', 'Elección Especialidad', 'Elección Especialidad', 'Elección Especialidad', false, false),
    ('EX', 'IEP-Ingreso Extranjero', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('G9', 'IEP-Convenio G9', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('GE', 'IEP-Ingreso Equidad de Género', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('H3', 'IEP-Habilitación Pedagogía 30%', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('H4', 'IEP-Habilitación Pedagogía 33P', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('H5', 'IEP-Habilitación Pedagogía 50P', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('HP', 'IEP-Habilitación Pedagogía PAP', '2. Ingreso Especial o Directo', '3. Ingreso PAP', false, true),
    ('ID', 'Ingreso Especial Discapacidad', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('IE', 'OI-Alumno Especial', '3. Otros Ingresos o Cambio de Carrera', '4. Otros Ingresos o Cambio de Carrera', false, false),
    ('IH', 'Ingreso Especial Historia', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('IN', 'OI-Ingreso por Intercambio', '3. Otros Ingresos o Cambio de Carrera', '4. Otros Ingresos o Cambio de Carrera', false, false),
    ('LE', 'IRP-Lista de espera', '1. Ingreso Regular o Centralizada', '1. Ingreso Regular o Centralizado', true, true),
    ('LS', 'IRP-Lista de selección', '1. Ingreso Regular o Centralizada', '1. Ingreso Regular o Centralizado', true, true),
    ('LV', 'IEP-Ingreso Esp. Licenciatura', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('MC', 'IEP-Mas Mujeres Científicas', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('NC', 'IEP-Inclusion', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('NN', 'Desconocido', 'Desconocido', 'Desconocido', false, false),
    ('OA', 'IRP-Oficio Verif. Excep. DEMRE', '1. Ingreso Regular o Centralizada', '1. Ingreso Regular o Centralizado', true, true),
    ('OO', 'OO-Otros Ingresos', '3. Otros Ingresos o Cambio de Carrera', '4. Otros Ingresos o Cambio de Carrera', false, true),
    ('OV', 'IRP-Oficio de Verificación', '1. Ingreso Regular o Centralizada', '1. Ingreso Regular o Centralizado', true, true),
    ('P1', 'IEP-Prog. Esp. Acceso PEA', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('PA', 'IEP-Ingreso por Pastoral (OBS)', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('PC', 'IEP-Ingreso Cupo PACE', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', true, true),
    ('PD', 'Prosecución de Estudios', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('PE', 'OI-Planes Especiales', '3. Otros Ingresos o Cambio de Carrera', '4. Otros Ingresos o Cambio de Carrera', false, false),
    ('PL', 'IEP-Ley 20.903', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('PO', 'IEP-Ingreso Pueblos Originario', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('PP', 'IEP-Propedéutico', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('PR', 'IEP-Ingreso Profesional', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('PS', 'IEP-Trayectoria Pastoral', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('PU', 'IEP-Ingreso Puntaje Ranking', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('RA', 'Repostulación PACE', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('RP', 'IRP-Repostulación', '1. Ingreso Regular o Centralizada', '1. Ingreso Regular o Centralizado', true, true),
    ('TP', 'IEP-Ingr. Tecnico Profesional', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('TR', 'IEP-Ingreso de Trabajador', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('TU', 'IEP-Ingreso Traslado de Univ', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true),
    ('UD', 'OI-Ingreso UDM', '3. Otros Ingresos o Cambio de Carrera', '4. Otros Ingresos o Cambio de Carrera', false, true),
    ('VO', 'IEP-Definición Vocacional', '2. Ingreso Especial o Directo', '2. Ingreso Especial o Directo', false, true)
ON CONFLICT (cod_admision) DO NOTHING;

-- Grade comment codes (R17). Only CONVA is confirmed (P36); the rest are preserved as plain codes.
CREATE TABLE IF NOT EXISTS neural_meta.dic_comentario_nota (
    comentario_codigo text    PRIMARY KEY,
    significado       text,
    es_convalidacion  boolean NOT NULL DEFAULT false,
    confirmado        boolean NOT NULL DEFAULT false
);

INSERT INTO neural_meta.dic_comentario_nota (comentario_codigo, significado, es_convalidacion, confirmado)
VALUES
    ('CONVA', 'Convalidación', true, true),
    ('CCAT', NULL, false, false),
    ('CCAR', NULL, false, false),
    ('RCONV', NULL, false, false),
    ('RCRED', NULL, false, false),
    ('TRSLD', NULL, false, false),
    ('PESP', NULL, false, false),
    ('INPRO', NULL, false, false),
    ('CDEP', NULL, false, false),
    ('CSEDE', NULL, false, false),
    ('REXTC', NULL, false, false),
    ('CRVE', NULL, false, false),
    ('ENLC', NULL, false, false)
ON CONFLICT (comentario_codigo) DO NOTHING;

-- Period calendar (RA11). Mirrors pipelines/normalize/periods.py; unknown suffixes are kept as 'otro'.
CREATE TABLE IF NOT EXISTS neural_meta.calendario_periodo (
    periodo         text     PRIMARY KEY CHECK (periodo ~ '^[0-9]{6}$'),
    anio            smallint NOT NULL,
    sufijo          text     NOT NULL,
    tipo_periodo    text     NOT NULL CHECK (tipo_periodo IN (
        'regular_1', 'regular_2', 'verano_invierno', 'postgrado', 'otro')),
    periodo_atipico boolean  NOT NULL,
    orden_regular   integer
);

INSERT INTO neural_meta.calendario_periodo (periodo, anio, sufijo, tipo_periodo, periodo_atipico, orden_regular)
SELECT y::text || s.sufijo,
       y,
       s.sufijo,
       s.tipo_periodo,
       s.tipo_periodo = 'otro',
       CASE s.sufijo WHEN '10' THEN y * 2 WHEN '20' THEN y * 2 + 1 END
FROM generate_series(1980, 2035) AS y
CROSS JOIN (VALUES
    ('10', 'regular_1'), ('20', 'regular_2'),
    ('15', 'verano_invierno'), ('25', 'verano_invierno'),
    ('50', 'postgrado'), ('60', 'postgrado'),
    ('11', 'otro'), ('21', 'otro'), ('01', 'otro')
) AS s (sufijo, tipo_periodo)
ON CONFLICT (periodo) DO NOTHING;
