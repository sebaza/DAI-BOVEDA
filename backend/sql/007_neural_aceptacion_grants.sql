-- Permisos del rol de mínimo privilegio sobre la tabla de aceptaciones de DAI Neural.
--
-- 003_percepcion_roles.sql solo concede a `boveda_app` lectura de las listas de acceso y alta en la auditoría,
-- así que sin esto el repositorio de aceptaciones (SELECT para comprobar, INSERT para registrar) falla con
-- "permission denied" y la puerta de Neural queda cerrada para todos. Solo SELECT e INSERT: nunca UPDATE ni DELETE
-- (la aceptación es un registro de auditoría).
-- No hace nada si el rol no existe (desarrollo con superusuario). Requiere 006_neural_aceptacion.sql.
-- Idempotente: se puede ejecutar más de una vez. 003 revoca y vuelve a conceder en cada ejecución: si se vuelve a
-- ejecutar 003, ejecuta este archivo después.

DO $grants$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'boveda_app') THEN
        GRANT USAGE ON SCHEMA boveda TO boveda_app;
        GRANT SELECT, INSERT ON TABLE boveda.aceptaciones_modulo TO boveda_app;
    END IF;
END
$grants$;
