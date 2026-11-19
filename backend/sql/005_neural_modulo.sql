-- Registra el módulo DAI Neural en la Bóveda (lista de módulos que el lobby y las listas de acceso conocen).
--
-- NO da acceso a nadie: sin filas en boveda.accesos_modulo el módulo falla cerrado. El acceso se otorga con
-- `python scripts/boveda_accesos.py dar-acceso neural <correo> lector`.
-- Idempotente: se puede ejecutar más de una vez. Requiere haber aplicado 001_boveda_access.sql.

INSERT INTO boveda.modulos (id, nombre, descripcion, activo)
VALUES (
    'neural',
    'DAI Neural',
    'Trayectorias estudiantiles (ficha, línea de tiempo, malla, cohortes)',
    true
)
ON CONFLICT (id) DO NOTHING;
