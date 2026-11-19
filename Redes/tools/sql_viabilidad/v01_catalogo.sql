-- R1 | tablas por palabra clave en nombre
SELECT table_schema, table_name, table_type FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog','information_schema')
AND (table_name ~* '(ayudant|investig|proyect|public|anid|fondecyt|contrato|honorar|beca|solicitud|carta|renuncia|suspens|reglament|causal|prerreq|equival|conval|moros|deuda|bloqueo|practica|titul|egres|ranking|postgrad|posgrad|articul|motivo|retiro|tutor|apoyo|orient|conducta|sancion|sumario|dpa|inscrip|cambio)')
ORDER BY 1,2
-- R2 | esquemas y conteo de tablas
SELECT table_schema, count(*) n FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') GROUP BY 1 ORDER BY 1
-- R3 | columnas por palabra clave
SELECT table_schema, table_name, column_name, data_type FROM information_schema.columns
WHERE table_schema NOT IN ('pg_catalog','information_schema','bench')
AND column_name ~* '(ayudant|investig|proyect|public|anid|fondecyt|contrato|honorar|motivo|causal|reglament|moros|deuda|bloqueo|practica|ranking|egreso|renuncia|suspens|solicitud|carta|condicional|observacion|tutor|sancion|area_|nota_titul|examen|capstone)'
ORDER BY 1,2,3
