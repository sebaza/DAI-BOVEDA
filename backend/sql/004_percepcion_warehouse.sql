-- Percepción en el almacén institucional: permisos para DOS roles que crea el DBA.
--
--   rol_escritor  Los procesos Python (sincronización del worker, derivados, subtemas, resumen
--                 semanal) y la Curación local de la Bóveda (PERCEPCION_DATABASE_URL,
--                 PERCEPCION_PROCESO_DATABASE_URL, PERCEPCION_ADMIN_DATABASE_URL apuntando al
--                 almacén). SELECT/INSERT/UPDATE/DELETE en todas las tablas del esquema y uso de
--                 las secuencias (USAGE para nextval; UPDATE porque la sincronización reinicia la
--                 secuencia con setval). Sin TRUNCATE, sin DDL: crear tablas o columnas nuevas lo
--                 hace el DUEÑO (scripts/publicar_warehouse_percepcion.py o un ALTER del DBA).
--   rol_lector    La API Node (wh-api), solo lectura: SELECT en todas las tablas.
--                 Una lectura de TABLA COMPLETA es aceptable porque `texto` y `caption` llegan
--                 como texto CIFRADO (AES-256-GCM, clave que no está en el almacén) y `autor_hash`
--                 va seudonimizado con HMAC. Lo que SÍ queda legible para este rol: los
--                 `token` de los derivados, `percepcion_resumen_semanal.texto`, `justificacion` y
--                 `autor` (correo) de las correcciones, nombres manuales de subtemas y los
--                 `external_id` de la plataforma. Ver docs/warehouse-percepcion.md.
--
-- NO crea roles ni les pone contraseña: eso lo hace el DBA (por eso falla si faltan). Se ejecuta
-- como DUEÑO del esquema (o miembro de ese rol, o superusuario; si no, se niega), con scripts/otorgar_permisos_warehouse_percepcion.py,
-- que reemplaza las tres líneas marcadas `@param` (los nombres de los roles aún no se conocen).
--
-- Idempotente: cada corrida revoca todo a PUBLIC y a los dos roles sobre el esquema y vuelve a
-- otorgar lo de abajo, así que quitar un permiso de este archivo lo quita también en la base.
-- El esquema `boveda` (módulos, listas de acceso, auditoría) NO está en el almacén y no se toca.

DO $wh$
DECLARE
    esq_percepcion text := 'percepcion';   -- @param
    rol_escritor   text := '';             -- @param
    rol_lector     text := '';             -- @param
    r text;
    dueno text;
BEGIN
    -- ---------------------------------------------------------------- validaciones
    IF rol_escritor = '' OR rol_lector = '' THEN
        RAISE EXCEPTION 'Faltan los nombres de los roles (rol_escritor y rol_lector).';
    END IF;
    IF rol_escritor = rol_lector THEN
        RAISE EXCEPTION 'El escritor y el lector deben ser roles distintos.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = esq_percepcion) THEN
        RAISE EXCEPTION 'No existe el esquema %. Corre antes scripts/publicar_warehouse_percepcion.py.',
            esq_percepcion;
    END IF;
    FOREACH r IN ARRAY ARRAY[rol_escritor, rol_lector] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            RAISE EXCEPTION 'El rol % no existe: pídele al DBA que lo cree (este script no crea roles).', r;
        END IF;
    END LOOP;

    -- Dueño del esquema: los permisos por defecto (más abajo) valen solo para los objetos que cree
    -- ESE rol, y cambiarlos exige ser ese rol, miembro suyo o superusuario.
    SELECT r.rolname INTO dueno
      FROM pg_namespace n JOIN pg_roles r ON r.oid = n.nspowner
     WHERE n.nspname = esq_percepcion;
    IF NOT (current_user = dueno
            OR pg_has_role(current_user, dueno, 'MEMBER')
            OR (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)) THEN
        RAISE EXCEPTION 'Este script debe correr como el dueño del esquema % (%), miembro de ese rol o superusuario; se ejecutó como %.',
            esq_percepcion, dueno, current_user;
    END IF;

    -- ----------------------------------------------- reinicio de permisos
    EXECUTE format('REVOKE ALL ON SCHEMA %I FROM PUBLIC, %I, %I', esq_percepcion, rol_escritor, rol_lector);
    EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM PUBLIC, %I, %I', esq_percepcion, rol_escritor, rol_lector);
    EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA %I FROM PUBLIC, %I, %I', esq_percepcion, rol_escritor, rol_lector);

    -- ----------------------------------------------------------------- otorgamientos
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I, %I', esq_percepcion, rol_escritor, rol_lector);

    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO %I', esq_percepcion, rol_escritor);
    EXECUTE format('GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA %I TO %I', esq_percepcion, rol_escritor);

    EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO %I', esq_percepcion, rol_lector);

    -- --------------------------------------------- permisos por defecto (futuro)
    -- Tablas y secuencias que cree en adelante el DUEÑO DEL ESQUEMA (FOR ROLE, leído arriba): sin
    -- esa cláusula valdrían solo para quien ejecuta este archivo, que puede ser otro rol.
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I REVOKE ALL ON TABLES FROM PUBLIC',
                   dueno, esq_percepcion);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I REVOKE ALL ON SEQUENCES FROM PUBLIC',
                   dueno, esq_percepcion);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
                   dueno, esq_percepcion, rol_escritor);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO %I',
                   dueno, esq_percepcion, rol_escritor);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT SELECT ON TABLES TO %I',
                   dueno, esq_percepcion, rol_lector);
END
$wh$;
