# DAI Neural — Auditoría de calidad de datos (Fase 1, entregable 04)

**Versión:** 0.2 · 11-11-2026 (actualiza solo el tratamiento de AQ09–AQ12, AQ19, AQ25, AQ40, AQ41 tras la segunda ronda de la DAI). Hallazgos medidos en el Warehouse en solo lectura (agregados, sin datos personales). Cada fila: cifra, evidencia, impacto y tratamiento propuesto (regla `RA##` de `03_reglas_academicas.md`). `r3#Rxx` = `evidencia/resultados_r3.txt`; `c01_c10`, `q1_q16`, `v1_v14` = `resultados_*.txt`. Porcentajes marcados "(derivado)" son cálculos simples sobre cifras de la evidencia.
**Alcance:** las vistas vigentes. No se auditaron aún: formato decimal de `nota`, coherencia nota↔inscripción por clave, emparejamiento historia↔malla, ciclos en prerrequisitos.

## 1. Ventanas de cobertura

| Fuente | Ventana | Evidencia | Impacto / tratamiento |
|---|---|---|---|
| `ban_estados_academicos` | 200810–202620 | `r3#R01`, `#R26` | Sin trayectorias de estado anteriores a 2008 (resp P24). Cohortes antiguas con notas pero sin estados. |
| `ban_historia_notas` | 198020–202620; volumen bajo hasta ~1999 (≤ 35.458 filas/año) y desde 2000 ≥ 49.805 | `r3#R13`, `#R26` | Las notas empezaron a guardarse después (resp P25). |
| `ban_inscripciones` | 202510–202610 | `r3#R26`, `#R27` | Renuncias y ramos en curso solo desde 202510 (RA18, RA19). |
| `ban_oferta_academica` | 201610–202650 | `r3#R26` | Sin docentes antes de 2016 (RA25). |
| `banner_admision` | procesos 200010–202610 (+ 202601) | `q1_q16#Q10`, `v1_v14#V03` | Ver §6. |
| `banner_titulados` | `year_titulacion` 2009–2026 (19.712 registros) | `q1_q16#Q12` | Estados `U` desde antes de 2009 sin registro posible. |
| `ban_encuesta` | 201510–202610 según tipo | `q1_q16#Q16` | Uso diferido. |
| Personas | Notas 66.125 RUT; estados 49.582; en ambas 47.574; solo notas 18.551 (28,1 %, derivado); solo estados 2.008 (4,0 %, derivado) | `r3#R30` | Solo notas: estudiantes históricos (resp P25); solo estados: sin explicar (P42). |

## 2. Estados (`ban_estados_academicos`, 735.932 filas, 49.582 personas)

| ID | Hallazgo | Cifra | Evidencia | Impacto | Tratamiento |
|---|---|---|---|---|---|
| AQ01 | `sorlcur` con saltos | 48.804 de 49.582 personas; 719.344 posiciones faltantes; solo 151 parten en 1; rango 1–633 | `r3#R06` | Contar con `sorlcur` da cifras falsas | RA02: no derivar conteos |
| AQ02 | `sorlcur` NULL, no entero, repetido | 0, 0, 0 repetidos | `r3#R06`, `c01_c10#C01` | Ninguno | Revalidar tras cada carga |
| AQ03 | `periodo` desciende al subir `sorlcur` | 17.705 de 686.350 pasos (2,6 %, derivado); mismo período 337.047 (49,1 %, derivado) | `r3#R04` | El orden por `sorlcur` y por período difieren en esos pasos | RA01: orden (`periodo`, `sorlcur`) |
| AQ04 | `fecha_estado` desciende | 56.905 de 686.350 pasos (8,3 %, derivado): 39.591 en el mismo período, 12.832 con descenso de período, 4.482 con período que sube. En orden (`periodo`, `sorlcur`) quedan 44.990 de 461.753 pasos con fecha (9,7 %, derivado) | `r3#R04`, `#R05` | La fecha no sirve para ordenar ni para cortes finos | Conservar como atributo; cortes por período (RA01) |
| AQ05 | `fecha_estado` NULL | 159.885 (21,7 %, derivado). Por estado: J 78.193 de 178.304; M 35.052 de 352.611; E 18.645 de 38.704; Z 8.706 de 19.489; N 5.618 de 5.622; D 4.293 de 23.455; O 2.442 de 2.449; los 5.211 sin código también sin fecha | `c01_c10#C08` | Sin cronología fina para casi 1 de 5 estados | RA03 (intervalo + marca) |
| AQ06 | Intervalo imputable | De los 159.885: 110.733 con fecha anterior y posterior; 8.967 solo anterior; 38.927 solo posterior; 1.258 ninguna; 5.068 con intervalo invertido | `r3#R12` | 49.152 sin intervalo cerrado (derivado: 8.967 + 38.927 + 1.258) y 5.068 invertidos (medido en orden `sorlcur`) | RA03; P44; re-medir en orden canónico |
| AQ07 | Fechas futuras | 21, solo en `B`; máx. 2026-12-31 | `c01_c10#C08`, `q1_q16#Q02` | Eventos falsos a futuro | RA04 (marcador); P03 |
| AQ08 | `cod_estado` NULL | 5.211 filas (0,7 %, derivado), 5.116 personas, períodos 201510–202610; sin `nombre_estado` | `r3#R01` | Estado desconocido | RA05: marca `sin_codigo` |
| AQ09 | Estados de reversa | `1`: 5, `2`: 8, `5`: 4 filas | `r3#R01` | Un evento revertido puede contarse como vigente | RA06: reversas ignoradas con `es_correccion_sistema`; no cancelan estados previos (`resp#P35`) |
| AQ10 | `cod_admision` NULL | 12 filas, 3 personas, 3 programas | `r3#R03`, `#R07` | Clave de episodio con componente NULL | RA09: `cod_admision` = `NN` con `cod_admision_imputado` (decisión del equipo, P38) |
| AQ11 | Episodios no contiguos | 1.660 de 57.561 (2,9 %, derivado) | `r3#R08` | Un episodio intercalado con otro se fragmentaría | RA09: un episodio con `tramo_n` por estado (decisión del equipo) |
| AQ12 | Episodios con más de un catálogo | 6.530 (11,3 %, derivado) | `r3#R08` | Si `catalogo` fuera parte de la clave se duplicarían episodios | RA09: `catalogo` por estado, fuera de la clave |
| AQ13 | Episodios de un solo estado | 1.483 (2,6 %, derivado) | `r3#R08` | Episodios sin trayectoria | Conservar; marcar en la ficha |
| AQ14 | Episodios CC sin estado previo | 989 | `r3#R10` | Cambio de carrera sin origen en la extracción | Marcar `origen_no_observado` |
| AQ15 | Períodos atípicos en estados | `01`: 64 filas (202601); `21`: 3 (202021) | `r3#R26` | Período sin significado definido | RA11; P45 |

## 3. Notas (`ban_historia_notas`, 2.670.731 filas, 66.125 personas)

| ID | Hallazgo | Cifra | Evidencia | Impacto | Tratamiento |
|---|---|---|---|---|---|
| AQ16 | Claves de intento repetidas | 0 | `v1_v14#V08` | Ninguno | Revalidar |
| AQ17 | Nota no numérica | 129.258 (4,8 %, derivado), todas `DPA`; 0 vacías; NRC vacío 0 | `v1_v14#V05`, `#V06` | Contaminan promedios si se parsean mal | RA12, RA13 |
| AQ18 | Notas 4,0 exactas | 196.982 (7,4 %, derivado) | `v1_v14#V05` | Aprobación en el límite; revisar frente a `oportunidad` (examen) | RA12, RA23 |
| AQ19 | `comentario` | Vacío 2.488.829; CCAT 132.721; CONVA 21.740 (15.840 DPA); CCAR 9.507; RCONV 7.982; RCRED 4.997; TRSLD 1.767; PESP 1.218; INPRO 724; CDEP 358; CSEDE 327; REXTC 181; CRVE 120; ENLC 100 | `r3#R17` | CONVA sin DPA ≈ 5.900 filas: posibles convalidaciones numéricas | RA16: `CONVA` = convalidación (`resp#P36`); el resto se preserva como `comentario_codigo`; sensibilidad en ronda 4 |
| AQ20 | `oportunidad` | 1: 2.351.185; 2: 244.421; 3: 46.450; 0: 19.531 (1.209 DPA); 4: 7.873; 5: 994; 6: 234; 7: 26; 8: 13; 9: 3; 10: 1 | `r3#R18` | Valor 0 sin significado | RA23; P40 |
| AQ21 | Códigos de asignatura fuera de patrón | Historia: patrón `AAAA99999` en 2.670.717 de 2.670.731 filas; mallas y prerrequisitos con guion; 98 códigos `AAA9-99999` en `prereq.asig` | `r3#R20` | Joins fallidos si no se normaliza | RA28 |
| AQ22 | DPA por año | Mayores: 2017: 13.274; 2014: 12.332; 2013: 9.697; recientes: 2021: 449; 2025: 35; 2026: 169 | `r3#R13` | La convalidación como DPA disminuye en los años recientes (hipótesis: cambio de práctica de registro) | No usar DPA como único criterio (P37) |

## 4. Inscripciones (`ban_inscripciones`, 213.170 filas)

| ID | Hallazgo | Cifra | Evidencia | Impacto | Tratamiento |
|---|---|---|---|---|---|
| AQ23 | Cobertura temporal | 202510–202610; ≈8 % del volumen de historia (derivado) | `r3#R26`, `c01_c10#C04` | Reconciliación solo reciente | RA20 |
| AQ24 | Sin resultado (`INSCRITO`, `aprobacion` NULL) | 73.697: 202610 73.499; 202601 155; 202520 43 | `r3#R27` | 73.499 en curso (resp P10); 43 en 202520 sin explicar | RA18; auditar los 43 |
| AQ25 | Convalidación con nota numérica | CONV/INY APROBADA numérica ≥ 4: 15.367; CONV/INY REPROBADA numérica < 4: 1.713; CONV/INTERC APROBADA numérica ≥ 4: 36; solo 183 con `DPA` | `r3#R16` | "DPA = convalidación" no cubre 17.116 filas (derivado: 15.367 + 1.713 + 36) | RA13, RA15: CONV/* = convalidación; solo APROBADA cuenta como aprobada (`resp#P37`) |
| AQ26 | Convalidaciones por período | 202510: 2.163; 202520: 667; 202610: 14.469 | `r3#R27` | Salto en 202610 sin explicar | Auditoría posterior |
| AQ27 | Renuncias por período | 202510: 6.078; 202520: 3.914; 202610: 3.907 | `r3#R27` | Sin renuncias registradas antes de 202510 (resp P12) | RA19: sin tasa previa |
| AQ28 | Renuncia y reprobación | `RENUNCIADA WF` + REPROBADA: 1 fila | `c01_c10#C04` | Caso al cierre de renuncias (resp P09) | RA19 |
| AQ29 | Doble renuncia al mismo ramo | No medido | — | La DAI indica que no debe ocurrir (resp P12) | Prueba (w); consulta de ronda 4 |

## 5. Oferta, docentes y vínculo con notas

Cobertura de filas evaluadas (sin DPA) de historia con sección en oferta (`r3#R13`):

| Año | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| % vinculado | 90,4 | 69,7 | 82,3 | 95,7 | 96,9 | 96,4 | 81,9 | 71,3 | 93,6 | 95,5 | 77,9 (en curso) |

| ID | Hallazgo | Cifra | Evidencia | Impacto | Tratamiento |
|---|---|---|---|---|---|
| AQ30 | Sin oferta antes de 2016 | 1980–2015: sin vinculación (porcentaje NULL en R13) | `r3#R13` | El 37,6 % global (`v1_v14#V09`) mezclaba años sin oferta | RA25: docente NULL; reportar cobertura |
| AQ31 | Caídas de cobertura | 2017: 69,7 %; 2023: 71,3 %; 2022: 81,9 %; 2018: 82,3 % | `r3#R13` | Tasas por docente sesgadas en esos años; la DAI sugiere un período no contado (resp P14) | Informar cobertura junto a toda tasa |
| AQ32 | Secciones multidocente | 65.074 secciones; 47.252 con varias filas; 9.341 con varios docentes; máx. 451 filas; 5.791 con notas | `q1_q16#Q15`, `v1_v14#V09` | Multiplicar intentos si se hace join plano | RA24: tabla puente |

## 6. Mallas, prerrequisitos y programas

| ID | Hallazgo | Cifra | Evidencia | Impacto | Tratamiento |
|---|---|---|---|---|---|
| AQ33 | Aristas repetidas | 45.439 filas → 31.996 aristas distintas; 5.303 aristas con más de una fila; 0 autoreferencias | `v1_v14#V11` | Aristas duplicadas inflan el grafo | RA27: deduplicar |
| AQ34 | Aristas por cobertura en `malla_programa` | Asignatura en la misma malla 8.981 de 31.996; requisito: misma malla 12.255, otro catálogo 986, otro programa 17.448, ninguna malla 1.307 | `r3#R19` | `malla_programa` incompleta | RA26: oficial `ban_malla_programa` |
| AQ35 | Aristas contra `ban_malla_programa` | Asignatura 28.859 (90,2 %, derivado); requisito 12.175 (38,1 %, derivado) | `r3#R19` | Requisitos de otros programas (ciclo básico, resp P15) quedan fuera del mismo programa-catálogo | RA27: clasificar |
| AQ36 | `ban_malla_programa` | 40.077 filas, 152 programas, 284 programa-catálogo; 0 sin semestre; 0 catálogo `000000`; `malla_formacion` NULL 6.976 (17,4 %, derivado) | `r3#R21`, `#R22` | `malla_formacion` incompleto; 704 valores | P40 |
| AQ37 | `ban_malla_programa` sin `programa_d` | 3 de 152 códigos; 21 de 40.077 filas | `r3#R14` | Filas de malla sin programa | Marcar `programa_no_mapeado` |
| AQ38 | `malla_programa` con catálogo `000000` | 5 de 75 combinaciones listadas | `q1_q16#Q07` | Versión de malla ambigua (resp P16: histórico/antecesor) | RA26 |
| AQ39 | Programas no válidos | 15 de 185 con `valid_program` falso; 1 predecesor inexistente. Códigos en uso con programa no válido: estados 1 (de 90), historia 2 (de 85), admisión 3 (de 86), titulados 1 (de 65), matrícula 0 (de 82) (derivado de `codigos` − `codigos_validos`) | `r3#R14`, `#R15` | Datos de programas cerrados o reemplazados | RA10: conservar con marca |
| AQ40 | Dirección del prerrequisito | No verificada | — | Un grafo invertido produce predicciones erróneas | Resuelto: requisito → curso (`resp#P46`); RA27 |

## 7. Admisión, titulación y cargas

| ID | Hallazgo | Cifra | Evidencia | Impacto | Tratamiento |
|---|---|---|---|---|---|
| AQ41 | Combinaciones repetidas (`year_admision`, `rut`, `cod_carrera`) | 4.209 de 107.036 (3,9 %, derivado); máx. 4 filas. Varían: `cod_admision` 4.202, `matricula` 633, `preferencia` 262; `pref_demre`, sede, `cod_demre`, `ponderado`: 0; idénticas en esos campos: 3 | `v1_v14#V04`, `r3#R23` | Duplicar postulantes si el grano es 3 columnas | RA30: `postulacion_via` + `postulacion` derivada por prioridad de vía; informar si alguna vía tuvo `matricula` = Y (633 grupos varían `matricula`); decisión del equipo (P39) |
| AQ42 | Carreras por persona y período | 1: 84.740; 2: 7.483; 3: 1.586; 4: 383; 5+: 182 | `r3#R24` | Postulación múltiple (resp P21) | Grano persona-período-carrera |
| AQ43 | Matrícula N/Y por sufijo | `YYYY10`: N 93.606, Y 17.660; `YYYY20`: N 393, Y 34; `YYYY01`: N 9, Y 31 | `r3#R25` | Y casi una por persona (`v1_v14#V03`) | RA30 |
| AQ44 | `ponderado` | Informado 0 veces hasta 201520, 3 en 201610 y ≥ 4.699 de 4.778 en 201910 | `q1_q16#Q10` | Cohortes antiguas sin ponderado comparable | RA31; P47 |
| AQ45 | Titulados con más de un registro | 122 personas; 119 con más de una carrera | `r3#R28` | Contar personas ≠ contar registros | RA33 |
| AQ46 | Estado `U` sin registro de titulado | 825 de 18.959 personas con `U` (4,4 %, derivado) | `r3#R28` | Conciliación incompleta | P42 |
| AQ47 | Cargas de estados (últimos 30 días) | Vigente: 04-11-2026, 735.932 filas, 49.582 RUT. Otras: 735.879, 735.802, 735.605 filas (49.582 RUT) y una de 211.173 filas / 15.800 RUT (20-10-2026) | `r3#R29` | Hay cargas parciales (211.173) que no se deben tomar | RA32 |
| AQ48 | Cargas de notas (últimos 30 días) | Vigente: 28-10-2026, 2.670.731 filas, 66.125 RUT. No vigentes más nuevas: 04-11-2026, 2.443.729 filas / 64.006 RUT (dos cargas). Otras parciales: 2.408.736 / 63.528 y 1.615.680 / 43.949 (21-10-2026) | `r3#R29` | La carga más reciente no es la vigente: guarda del 97 % de RUT | RA32; P41 |
| AQ49 | `timestamp_carga` | Epoch ms en estados y notas | `r3#R29` | Conversión errónea si se asume segundos | RA32 |

## 8. Resumen de impacto

- **Bloqueos de v0.1 resueltos (11-11, ronda 2):** AQ25/AQ19 (RA13, RA15, RA16), AQ09 (RA06), AQ41 (RA30), AQ40 (RA27), AQ03 (orden confirmado, RA01). Siguen limitando: AQ04/AQ05/AQ06 (fechas), resto de `comentario` (sensibilidad pendiente).
- **Limitan sin bloquear:** AQ05/AQ06 (fechas), AQ30/AQ31 (docentes), AQ23/AQ27 (inscripciones y renuncias recientes), AQ36 (formación).
- **Controlados por regla:** AQ01, AQ08, AQ11, AQ12, AQ21, AQ33, AQ47–AQ49.
