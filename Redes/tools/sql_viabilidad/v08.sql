-- R1 | patron de codigos en ban_malla_programa
SELECT regexp_replace(regexp_replace(malla_materiacurso,'[A-Za-z]','A','g'),'[0-9]','9','g') patron, count(*) n FROM banner.ban_malla_programa GROUP BY 1 ORDER BY 2 DESC LIMIT 6
-- R2 | patron codigos prereq
SELECT regexp_replace(regexp_replace(codigo_asignatura,'[A-Za-z]','A','g'),'[0-9]','9','g') patron, count(*) n FROM banner.malla_programa_prereq GROUP BY 1 ORDER BY 2 DESC LIMIT 6
-- R3 | catalogo y programa formatos
SELECT (SELECT min(malla_ctlg) FROM banner.ban_malla_programa) c1, (SELECT min(catalogo) FROM banner.malla_programa_prereq) c2, (SELECT min(cod_banner) FROM common.programa_d) p1, (SELECT min(malla_program_code) FROM banner.ban_malla_programa) p2
-- R4 | prerequisitos: cobertura con codigo normalizado (sin guion) y catalogo texto
WITH m AS (SELECT DISTINCT malla_program_code cod, malla_ctlg::text ctlg, replace(malla_materiacurso,'-','') mc, malla_semestre sem FROM banner.ban_malla_programa), p AS (SELECT DISTINCT pd.cod_banner::text cod, r.catalogo::text ctlg, replace(r.codigo_asignatura,'-','') mc FROM banner.malla_programa_prereq r JOIN common.programa_d pd ON pd.id=r.cod_programa) SELECT count(*) cursos_malla, sum((p.mc IS NOT NULL)::int) con_prereq FROM m LEFT JOIN p ON p.cod=m.cod AND p.ctlg=m.ctlg AND p.mc=m.mc
-- R5 | prereq: programas y catalogos en prereq vs en malla
SELECT count(distinct pd.cod_banner) prog_prereq, count(distinct (pd.cod_banner, r.catalogo)) prog_cat_prereq FROM banner.malla_programa_prereq r JOIN common.programa_d pd ON pd.id=r.cod_programa
