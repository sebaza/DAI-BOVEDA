# DAI Neural — Estado del levantamiento v0.2 (10-11-2026)

## Reglas aportadas por la DAI
- **CONFIRMADO:** `sorlcur` ordena los estados **por RUT** y **no se reinicia** cuando cambia de carrera; no equivale a un identificador de episodio. Auditar valores repetidos o nulos como calidad de datos.
- Cambios de ciclo se identifican con información de `cod_admision`; conservar también el evento `D` sin equipararlo automáticamente a cambio de carrera.
- Prácticas/proyectos y CAPSTONE están en historia de notas, sus códigos pueden variar; clasificación versionada.

## Resultados V01–V14
- `common.programa_d(id, cod_banner, programa_predecesor)` permite proponer unión entre IDs internos y códigos Banner, pendiente comprobar cardinalidad.
- V02: 735.932 estados, 5.211 códigos vacíos, 159.885 fechas nulas, 21 fechas futuras.
- V04: 107.036 combinaciones persona-período-carrera en admisión; 4.209 combinaciones duplicadas, máximo 4 registros.
- V05/V06: 2.670.731 notas; 129.258 `DPA` = **convalidaciones** de ramos aprobados antes en otra carrera o institución (confirmado por DAI); 196.982 con nota 4,0, que **sí aprueba**. DPA cumple un requisito curricular, sin nota numérica ni intento evaluado local; excluirlo de promedios y tasas por profesor.
- V07: renuncias en inscripciones visibles solo 2025–2026 en consulta; cobertura previa no demostrada.
- V08: 0 claves repetidas sobre 2.670.731 combinaciones de intento evaluadas.
- V09: 1.004.545 filas de nota con oferta de 2.670.731; 5.791 secciones con múltiples docentes, cobertura 37,6%.
- V11: 31.996 aristas curriculares distintas, 5.303 aristas repetidas, 45.439 filas originales, 0 autoreferencias.
- V12: se identificaron prácticas, proyectos, tesis y `CAPSTONE PROJECT` entre asignaturas, pero también falsos positivos por palabras genéricas.
- V13: fuentes con cargas vigentes designadas y cargas no vigentes más nuevas; no tomar timestamp máximo automáticamente.
- V14: matrícula postgrado `MATRICULADO` puede coexistir con estados `W` y otros; tratar matrícula y estado por separado.

## Requisitos antes de entrenar
1. Auditar duplicados/empates/NULL de `sorlcur`, cuya secuencia global por RUT ya está confirmada.
2. Validar regla de cambio de ciclo/carrera mediante `cod_admision` y código de programa.
3. Verificar casos especiales y crédito reconocido de convalidaciones; `DPA` y aprobación de nota 4,0 ya están confirmados.
4. Confirmar representatividad de N/Y en admisión.
5. Corregir/documentar cobertura histórica e intervalos de disponibilidad de cada fuente.
6. Validar malla, códigos de programa y prerrequisitos antes de GNN.
7. Hacer primero ficha histórica y comparador; después modelos predictivos con validación temporal y supervisión.

## Tests y denominadores obligatorios
- Nota numérica >= 4,0 aprueba; 3,9 reprueba.
- DPA reconoce asignatura con nota_numérica NULL y sin intento evaluado; no incluir en tasa de aprobación docente ni promedio.
- El avance curricular puede computar DPA con equivalencia validada; evitar doble conteo de créditos.
- Secuencia de estados por `rut, sorlcur` incluso tras un cambio de carrera.
