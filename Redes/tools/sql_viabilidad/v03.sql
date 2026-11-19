-- R1 | ses.casos columnas
SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='ses' AND table_name='casos' ORDER BY ordinal_position
-- R2 | vridt.estudiantes_f columnas
SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='vridt' AND table_name='estudiantes_f' ORDER BY ordinal_position
-- R3 | vridt.cargo_en_proyecto_f columnas
SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='vridt' AND table_name='cargo_en_proyecto_f' ORDER BY ordinal_position
-- R4 | reportes_deudas cobertura por anio
SELECT year, count(*) filas, count(distinct rut) ruts, sum((saldo_por_pagar>0)::int) con_saldo, round(avg(NULLIF(saldo_por_pagar,0))) saldo_prom FROM banner.reportes_deudas GROUP BY 1 ORDER BY 1
-- R5 | biucn columnas
SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema='biucn' AND table_name IN ('ingreso_plataforma_f','uso_plataforma_f') ORDER BY 1, ordinal_position
-- R6 | pde estudiantes_inclusion columnas
SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='pde' AND table_name IN ('estudiantes_inclusion_xls','intercambio_saliente_xls') ORDER BY 1, ordinal_position
-- R7 | reportes_deudas: tiene marca de carga o fecha?
SELECT table_schema, table_name, table_type FROM information_schema.tables WHERE table_name ILIKE '%deuda%'
