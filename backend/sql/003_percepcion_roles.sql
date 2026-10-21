-- Percepción: DOS roles de base de datos, para que la API normal NO pueda leer texto crudo.
--
--   boveda_app      LOGIN. El rol de la API (PERCEPCION_DATABASE_URL). Lee todo MENOS
--                   percepcion_comentario.texto y percepcion_publicacion.caption (permisos por
--                   columna) y hace solo las escrituras que la Bóveda hace de verdad.
--   boveda_proceso  LOGIN. Lee TAMBIÉN texto y caption (PERCEPCION_PROCESO_DATABASE_URL). Lo usan
--                   la Curación de administradores, la lectura de captions del resumen semanal y
--                   los scripts (precálculo de tokens).
--
-- Requiere 001 y 002 (esquema `boveda`) y las tablas de Percepción ya creadas y migradas
-- (scripts/migrar_percepcion_postgres.py) y los derivados precalculados
-- (scripts/precalcular_tokens_percepcion.py). Se ejecuta como DUEÑO de las tablas o superusuario.
--
-- Idempotente: cada corrida revoca todo a PUBLIC y a los dos roles sobre ambos esquemas y vuelve a
-- otorgar lo de abajo, así que quitar un permiso de este archivo lo quita también en la base.
-- Los roles se crean SIN contraseña: ponla con `scripts/crear_roles_percepcion.py`, que lee
-- PERCEPCION_APP_DB_PASSWORD y PERCEPCION_PROCESO_DB_PASSWORD del entorno (nunca van en este archivo).
--
-- Las cuatro líneas marcadas `@param` son los nombres reales; el runner puede reemplazarlas para
-- probar con esquemas y roles descartables.
--
-- TABLAS NUEVAS: este archivo otorga por lo que existe HOY. Una tabla creada después no es legible
-- por boveda_app hasta volver a correr este archivo (falla cerrado a propósito: así una tabla con
-- texto nunca queda abierta por omisión). Para boveda_proceso sí hay permiso por defecto (SELECT).

DO $roles$
DECLARE
    esq_percepcion text := 'percepcion';    -- @param
    esq_boveda     text := 'boveda';        -- @param
    rol_app        text := 'boveda_app';    -- @param
    rol_proceso    text := 'boveda_proceso';-- @param

    -- Columnas que boveda_app NO puede leer (tabla -> columnas).
    sensibles jsonb := '{"percepcion_comentario": ["texto"],
                         "percepcion_publicacion": ["caption"]}';

    -- Escrituras de TABLA COMPLETA que la Bóveda hace hoy (curacion.py, eventos.py, calendario.py,
    -- resumen_llm.py). Los INSERT/UPDATE/DELETE de estas tablas nunca tocan texto ni caption.
    escrituras jsonb := '{"percepcion_tema_custom":      "INSERT",
                          "percepcion_hecho_diario":     "INSERT, DELETE",
                          "percepcion_correccion":       "INSERT",
                          "percepcion_evento":           "INSERT, UPDATE, DELETE",
                          "percepcion_resumen_semanal":  "INSERT, UPDATE, DELETE"}';

    -- Escrituras por COLUMNA sobre tablas del worker: la curación reasigna tema y corrige el score.
    -- Nada más (en particular, ni texto ni caption).
    escrituras_columna jsonb := '{"percepcion_comentario": ["tema", "tema_confianza"],
                                  "percepcion_score": ["modelo", "sentimiento", "prob_pos", "prob_neu",
                                                       "prob_neg", "emocion", "prob_emocion"]}';

    -- Tablas derivadas del texto: solo las reconstruye el rol de proceso.
    derivadas text[] := ARRAY['percepcion_comentario_token', 'percepcion_comentario_familia',
                              'percepcion_publicacion_rasgo'];
    t record;
    cols text;
    priv text;
    sens text[];
BEGIN
    -- ---------------------------------------------------------------- roles
    FOREACH priv IN ARRAY ARRAY[rol_app, rol_proceso] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = priv) THEN
            EXECUTE format('CREATE ROLE %I LOGIN', priv);
        END IF;
        EXECUTE format('ALTER ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', priv);
    END LOOP;

    -- ----------------------------------------------- reinicio de permisos
    FOREACH priv IN ARRAY ARRAY[esq_percepcion, esq_boveda] LOOP
        EXECUTE format('REVOKE ALL ON SCHEMA %I FROM PUBLIC, %I, %I', priv, rol_app, rol_proceso);
        EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM PUBLIC, %I, %I', priv, rol_app, rol_proceso);
        EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA %I FROM PUBLIC, %I, %I', priv, rol_app, rol_proceso);
    END LOOP;

    -- ----------------------------------------------------- esquema percepcion
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I, %I', esq_percepcion, rol_app, rol_proceso);
    EXECUTE format('GRANT USAGE ON ALL SEQUENCES IN SCHEMA %I TO %I, %I', esq_percepcion, rol_app, rol_proceso);

    FOR t IN
        SELECT c.oid, c.relname
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = esq_percepcion AND c.relkind IN ('r', 'p')
         ORDER BY c.relname
    LOOP
        -- boveda_proceso: lectura completa, incluido el texto crudo.
        EXECUTE format('GRANT SELECT ON TABLE %I.%I TO %I', esq_percepcion, t.relname, rol_proceso);

        -- boveda_app: lectura de todo salvo las columnas sensibles (permiso por columna).
        sens := ARRAY(SELECT jsonb_array_elements_text(COALESCE(sensibles -> t.relname, '[]'::jsonb)));
        IF cardinality(sens) = 0 THEN
            EXECUTE format('GRANT SELECT ON TABLE %I.%I TO %I', esq_percepcion, t.relname, rol_app);
        ELSE
            SELECT string_agg(quote_ident(a.attname), ', ' ORDER BY a.attnum) INTO cols
              FROM pg_attribute a
             WHERE a.attrelid = t.oid AND a.attnum > 0 AND NOT a.attisdropped
               AND a.attname <> ALL (sens);
            EXECUTE format('GRANT SELECT (%s) ON TABLE %I.%I TO %I', cols, esq_percepcion, t.relname, rol_app);
        END IF;

        -- Escrituras de tabla completa (app y proceso).
        priv := escrituras ->> t.relname;
        IF priv IS NOT NULL THEN
            EXECUTE format('GRANT %s ON TABLE %I.%I TO %I, %I', priv, esq_percepcion, t.relname, rol_app, rol_proceso);
        END IF;

        -- Escrituras por columna (app y proceso).
        IF escrituras_columna ? t.relname THEN
            SELECT string_agg(quote_ident(x), ', ') INTO cols
              FROM jsonb_array_elements_text(escrituras_columna -> t.relname) AS x;
            EXECUTE format('GRANT UPDATE (%s) ON TABLE %I.%I TO %I, %I',
                           cols, esq_percepcion, t.relname, rol_app, rol_proceso);
        END IF;

        -- Derivados: solo el rol de proceso los reconstruye (vaciar y volver a llenar).
        IF t.relname = ANY (derivadas) THEN
            EXECUTE format('GRANT INSERT, DELETE ON TABLE %I.%I TO %I', esq_percepcion, t.relname, rol_proceso);
        END IF;
    END LOOP;

    -- ----------------------------------------------------------- esquema boveda
    -- La API solo LEE las listas de acceso y AÑADE filas a la auditoría. Administrar las listas
    -- (scripts/boveda_accesos.py) se hace con otra credencial, no con esta.
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I', esq_boveda, rol_app);
    FOR t IN
        SELECT c.relname
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = esq_boveda AND c.relkind IN ('r', 'p')
    LOOP
        IF t.relname IN ('modulos', 'accesos_modulo', 'administradores') THEN
            EXECUTE format('GRANT SELECT ON TABLE %I.%I TO %I', esq_boveda, t.relname, rol_app);
        ELSIF t.relname = 'auditoria_texto' THEN
            EXECUTE format('GRANT INSERT ON TABLE %I.%I TO %I', esq_boveda, t.relname, rol_app);
        END IF;
    END LOOP;
    EXECUTE format('GRANT USAGE ON ALL SEQUENCES IN SCHEMA %I TO %I', esq_boveda, rol_app);

    -- --------------------------------------------- permisos por defecto (futuro)
    -- Una tabla nueva de Percepción: nadie en PUBLIC y solo lectura para el rol de proceso.
    -- boveda_app NO recibe nada por omisión (ver la nota de arriba). Aplica a las tablas que cree
    -- el rol que ejecuta este archivo.
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL ON TABLES FROM PUBLIC', esq_percepcion);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT ON TABLES TO %I', esq_percepcion, rol_proceso);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL ON TABLES FROM PUBLIC', esq_boveda);
END
$roles$;
