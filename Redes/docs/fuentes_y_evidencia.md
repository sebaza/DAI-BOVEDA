# DAI Neural — Fuentes y evidencia

**Versión:** 0.2 · 11-11-2026 (incorpora ronda 3, `R01`–`R30`, y las respuestas DAI del 11-11-2026). Una sección por tabla fuente de la especificación. Esquema `banner` salvo que se indique.
**Referencias:** `Q##` = `resultados_q1_q16.txt`, `V##` = `resultados_v1_v14.txt`, `C##` = `resultados_c01_c10.txt`, `R##` = `resultados_r3.txt` (ronda 3, solo lectura en el Warehouse, 11-11-2026; `R51`–`R70` = `resultados_r5.txt`, etapa A, 13-11-2026, consultas en `sql/discovery/ronda5_etapa_a.sql`), `resp#Pxx` = `respuestas_dai_2026-11-11.md`, `INV` = `inventario_q1.txt`. Formato `archivo#ID`. Cifras tal como las entregó la DAI; "derivado" = cálculo simple declarado.

## Ventanas de cobertura conocidas

| Fuente | Ventana observada | Evidencia |
|---|---|---|
| `ban_estados_academicos` | períodos 200810–202620 | `Q14`, `R01`, `R26` |
| `ban_historia_notas` | períodos 198020–202620 | `Q14`, `R26` |
| `banner_admision` | procesos 200010–202610 (más 202601) | `Q10`, `V03` |
| `banner_titulados` | `year_titulacion` 2009–2026 | `Q12` |
| `banner_estudiantes_postgrado` | al menos 2017–2026 (consulta truncada) | `V14` (`LIMIT 90`), `Q13` (`LIMIT 100`) |
| `ban_encuesta` | 201510–202610 según tipo | `Q16` |
| `ban_malla_programa` | 152 programas, 284 programa-catálogo | `R21` |
| `ban_inscripciones` | períodos **202510–202610** | `R26`, `R27` |
| `ban_oferta_academica` | períodos **201610–202650** | `R26`, `R13` |

---

## banner.ban_estados_academicos

- **Ronda 3 (R01–R30)**
  - `R01`: diccionario completo, 33 códigos + NULL (incluye reversas `1`, `2`, `5`); `R03`: uso de 52 `cod_admision` + NULL.
  - `R04`/`R05`: 686.350 pasos; `periodo` desciende en 17.705; `fecha` desciende en 56.905; con orden (`periodo`, `sorlcur`) persisten 44.990 de 461.753. `R06`: `sorlcur` sin NULL ni decimales, 1–633, 48.804 personas con saltos, 151 parten en 1.
  - `R07`/`R08`: 57.561 episodios (clave propuesta), 1.660 no contiguos, 6.530 con más de un catálogo. `R09`–`R11`: `D` no cambia de programa; los cambios de programa entran vía CC o admisión nueva. `R12`: 110.733 de 159.885 fechas NULL con fechas a ambos lados.
  - `R14`: `cod_programa` 90/90 en `programa_d.cod_banner`. `R26`: sufijos 10/20 (+01: 64, 21: 3). `R28`, `R30`: conciliación con titulados y notas.
  - DAI (11-11): orden (`periodo`, `sorlcur`) (`resp#P01`); NULL = fecha no guardada o cambio interno (`resp#P02`); futuras = marcador (`resp#P03`); episodio (`resp#P06`).

- **Verificado**
  - 735.932 filas en la carga vigente (`Q14`, `V02`); 49.582 RUT según metadato `ruts` de la carga (`Q14`).
  - `V02`: 5.211 `cod_estado` vacíos, 159.885 `fecha_estado` NULL, 21 fechas futuras, 0 períodos vacíos.
  - `C01`: 735.932 pares (rut, sorlcur), 0 repetidos, máx. 1 fila por par. Derivado: `rut` y `sorlcur` sin NULL.
  - `C02`: 576.047 estados con fecha y orden (derivado: 735.932 − 159.885); 57.606 (≈10 %) con descenso de fecha al subir `sorlcur`.
  - `C08`: NULL en `fecha_estado` concentrados en J 78.193 de 178.304 (≈44 %), M 35.052 de 352.611, E 18.645 de 38.704, Z 8.706 de 19.489, D 4.293 de 23.455, N 5.618 de 5.622, O 2.442 de 2.449. Los 5.211 `cod_estado` NULL carecen también de fecha. G, U y K casi siempre con fecha (5, 6 y 0 NULL). Fechas futuras solo en B (21; `Q02`: máx. 2026-12-31).
  - `Q02`: 33 códigos de estado con `nombre_estado` más 5.211 sin código. Fechas mínimas llegan a 1981 (`Q04`: período 202210 con `fecha_min` 1981-07-30), por lo que fecha y período no coinciden.
  - `Q03`: causal informada solo para `E` (Eliminado), p. ej. `0Z` 6.116, `0D` 4.136; 5.703 `E` sin causal.
  - `C03`/`C03-V2`: `cod_admision` aparece combinado con estados de todo tipo (M, J, E, G, D, U…; `C03` solo lista filas con `cod_estado='D'` o `cod_admision` no NULL); ej. `M`+`LS` 291.055 filas / 41.393 personas / 68 programas; `D`+`LS` 19.162 / 19.022 / 63; `D`+`CC` 2.344 / 2.327 / 60. `LS` = IRP-Lista de selección, `CC` = Cambio de Carrera.
  - `C10`: 8.295 pasos con cambio de programa de 686.350 observables (derivado: filas − RUT).
  - Tipos (`Q01`): `sorlcur` y `plan_estudios` `numeric`; `cod_programa`, `catalogo`, `periodo`, `periodo_admision` `text`; `fecha_estado` `timestamp`.
- **Cobertura:** 200810–202620 (`Q14`). Por período, ej. 202620: 15.794 filas / 12.582 personas; 202610: 35.567 / 14.067 (`Q04`, solo 40 períodos).
- **Sin verificar (v0.2):** causa de los descensos de fecha (la DAI indica que el período pesa más que `sorlcur`, `resp#P01`; la fecha sigue sin ser cronológica, `R05`); regla para los estados de reversa `1`, `2`, `5` (P35); clasificación de negocio (terminal, retiro) de los 33 códigos; confirmación de la clave de episodio (P38) y del orden canónico (P43); constancia de `cod_admision` dentro de un episodio.

## banner.ban_historia_notas

- **Ronda 3 (R01–R30)**
  - `R13`: cobertura de oferta por año sobre filas evaluadas (2016 90,4 % … 2026 77,9 %); sin oferta antes de 2016. `R17`: 14 valores de `comentario` (≥ 100 filas). `R18`: `oportunidad` 0–10. `R20`: patrón de código `AAAA99999` (2.670.717 filas).
  - `R14`: `cod_carrera` 85/85 en `programa_d`. `R29`: la carga del 28-10-2026 (2.670.731 filas, 66.125 RUT) es la vigente; las dos del 04-11-2026 (64.006 RUT) no.
  - DAI (11-11): historia es la fuente por ahora (`resp#P11`); sin excepciones a nota ≥ 4,0 (`resp#P27`); aprobado = reconocido (`resp#P28`).

- **Verificado**
  - 2.670.731 filas, 66.125 RUT (`Q14`, `V05`); nota vacía 0, NRC vacío 0, oportunidad vacía 0 (`V05`).
  - 129.258 notas no numéricas y todas son `DPA` (`V05`, `V06`); 196.982 con nota 4,0 (`V05`).
  - `V08`: 0 claves repetidas por (periodo, rut, cod_carrera, catalogo, materia, curso, oportunidad, nrc); máx. 1 fila por clave.
  - `V09`: 145.051 pares (periodo, nrc) con notas; 46.325 con oferta; 98.726 sin oferta; 1.004.545 filas de notas con oferta y 1.666.186 sin oferta (≈37,6 % con oferta); 5.791 secciones multidocente.
  - `Q05`: en los 40 períodos más recientes (202620–201915) 0 notas sin valor y 0 NRC vacío. Aparecen períodos `15`, `25`, `11`, `21` y `01` (ej. 202615: 543 filas; 202525: 889).
  - Tipos (`Q01`): `nota`, `oportunidad`, `nrc` `text`; `creditos`, `plan_estudio` `numeric`.
- **Cobertura:** 198020–202620 (`Q14`). `Q05` muestra solo los 40 períodos más recientes.
- **Sin verificar (v0.2):** significado de los códigos de `comentario` (P36) y de `oportunidad` = 0 (P40); coherencia del NRC en filas DPA; cruce nota 4,0 × `oportunidad`; formato decimal de `nota`; créditos reconocidos y equivalencias.

## banner.ban_inscripciones

- **Ronda 3 (R01–R30)**
  - `R26`/`R27`: períodos 202510–202610; 202610: 91.880 filas, 73.499 sin resultado; renuncias 6.078 / 3.914 / 3.907 y convalidaciones 2.163 / 667 / 14.469 (202510 / 202520 / 202610).
  - `R16`: en `CONV/*`, nota numérica ≥ 4 en 15.367 + 36 filas, numérica < 4 en 1.713 y `DPA` en 183.
  - DAI (11-11): NULL = en curso (`resp#P10`); renuncias no se registraban antes (`resp#P12`); DPA = convalidada (`resp#P08`).

- **Verificado**
  - `C04` (= `Q06`): 213.170 filas (derivado: suma de grupos). `INSCRITO`/APROBADA 88.453; `INSCRITO`/NULL 73.697; `INSCRITO`/REPROBADA 19.822; CONV/INY APROBADA 15.550; RENUNCIADA MANUAL 10.104; RENUNCIADA WF 2.964; CONV/INY REPROBADA 1.713; RENUNCIADA WEB 830; CONV/INTERC APROBADA 36; RENUNCIADA WF REPROBADA 1.
  - `C04`, `nota_4`: 5.764 en INSCRITO/APROBADA; 1.120 en CONV/INY APROBADA; 1 en CONV/INTERC APROBADA.
  - `C09`: solo 183 filas con `nota='DPA'`, todas CONV/INY APROBADA (contra 129.258 en historia).
  - `V07`: renuncias solo en 2025 (MANUAL 6.582, WF 2.965, WEB 445) y 2026 (MANUAL 3.522, WEB 385); ninguna con nota salvo 1 fila WF 2025 en la columna `con_nota`.
  - Tipos (`Q01`): `oportunidad` `numeric` (en historia es `text`); `nota` `text`.
- **Cobertura:** períodos 202510–202610 (`R26`, `R27`). Volumen ≈8 % de historia (derivado: 213.170 / 2.670.731): cobertura parcial confirmada.
- **Sin verificar (v0.2):** clasificación de CONV/* con nota numérica (P37; `R16`); 43 `INSCRITO` sin resultado en 202520 (`R27`); reconciliación con historia por clave de intento; doble renuncia al mismo ramo (`resp#P12`).

## banner.ban_oferta_academica

- **Ronda 3 (R01–R30)**
  - `R26`: períodos 201610–202650 (sufijos 10, 20, 50, 60, 01). `R13`: vinculación con notas por año (sin DPA): 2016 90,4 %; 2017 69,7 %; 2018 82,3 %; 2019 95,7 %; 2020 96,9 %; 2021 96,4 %; 2022 81,9 %; 2023 71,3 %; 2024 93,6 %; 2025 95,5 %; 2026 77,9 %. El 37,6 % global estaba dominado por años sin oferta.
  - DAI (11-11): el foco son los estudiantes; menos vínculos docentes que notas es normal (`resp#P14`).

- **Verificado**
  - `Q15`: 65.074 secciones (periodo, nrc); 47.252 con varias filas; 9.341 con varios docentes; máx. 451 filas por sección.
  - `V09`: 5.791 secciones con notas y oferta con varios docentes.
  - Tipos (`Q01`): todas `text`, incluidas `fechainicio`, `fechafin`, `cupo`.
- **Cobertura:** períodos 201610–202650; vínculo con notas por año en `R13` (69,7 %–96,9 % entre 2016 y 2026). El ≈37,6 % global (`V09`) incluía años sin oferta.
- **Sin verificar (v0.2):** significado de `tipo_profesor` y regla de atribución con varios docentes (P14); semántica de las múltiples filas por sección; causa de las caídas de cobertura en 2017 y 2023.

## banner.ban_parciales_notas

- **Verificado:** estructura (`Q01`): 25 columnas; `fecha_sub` `text`, `nota_comp`/`nota_sub` `text`.
- **Cobertura y contenido:** no consultados.
- **Sin verificar:** temporalidad, cobertura y utilidad; se difiere a fase posterior (especificación).

## banner.malla_programa

- **Ronda 3 (R01–R30)**
  - `R19`: de 31.996 aristas distintas, asignatura en la misma malla 8.981; requisito en la misma malla 12.255, en otro catálogo del mismo programa 986, en otro programa 17.448, en ninguna 1.307. `R20`: patrón `AAAA-99999` en las 8.091 filas.
  - DAI (11-11): la fuente oficial es `ban_malla_programa` (`resp#P17`); catálogo `000000` = histórico o antecesor (`resp#P16`).

- **Verificado**
  - `C07`: 8.091 filas, 173 combinaciones (programa, catálogo), 0 sin `programa_d`, 0 combinaciones sin mapeo.
  - `Q07` (75 combinaciones listadas de 173): `filas` = `asignaturas_distintas` en las 75; `nivel_min` 1 en las 75; `nivel_max` 8–14; catálogo `000000` en 5 de las 75.
  - Tipos (`Q01`): `cod_programa` `bigint`; `catalogo` `text`; `creditos`, `nivel` `integer`.
- **Cobertura:** 173 combinaciones; catálogos de 198310 a 202510 en `Q07`.
- **Sin verificar (v0.2):** unicidad de código en las 98 combinaciones no listadas; vigencia por catálogo; si `creditos` es crédito local o SCT. El catálogo `000000` es histórico o antecesor (`resp#P16`).

## banner.malla_programa_prereq

- **Ronda 3 (R01–R30)**
  - `R19`: clasificación de requisitos (ver arriba); contra `ban_malla_programa` (vía `programa_d`): asignatura 28.859, requisito 12.175. `R20`: 98 códigos con patrón `AAA9-99999`.
  - DAI (11-11): muchos ramos sin prerrequisito, otros del ciclo básico (`resp#P15`). Dirección del requisito: sin confirmar (P46).

- **Verificado**
  - `V11`: 45.439 filas → 31.996 aristas distintas; 5.303 aristas con más de una fila; 0 autoreferencias (derivado: 13.443 filas excedentes).
  - `Q09`: de 45.439 relaciones, destino en malla 8.983 (≈19,8 %), destino sin malla 36.456; requisito en malla 18.912 (≈41,6 %), requisito sin malla 26.527. Cruce por (cod_programa, catalogo, código).
  - `Q08`/`V10`: por programa/catálogo los destinos ausentes son altos (ej. 47/202320: 2.097 relaciones, 2.003 destinos ausentes).
- **Cobertura:** ver `Q08` (75 combinaciones mayores).
- **Sin verificar (v0.2):** dirección del requisito (P46); ciclos; emparejamiento de códigos entre historia y mallas (cobertura).

## banner.ban_malla_programa

- **Ronda 3 (R01–R30)**
  - `R21`: 40.077 filas, 152 programas, 284 programa-catálogo, 0 con catálogo `000000`, 0 sin semestre, 704 valores de `malla_formacion`, 29.614 asignaturas distintas (programa, catálogo, asignatura). `R22`: `malla_formacion` NULL 6.976; códigos UNFE…, UNFG…, UNFP…, UNFV… (significado por confirmar). `R14`: 149 de 152 códigos en `programa_d` (40.056 de 40.077 filas). `R20`: patrón `AAAA-99999` (40.048 filas).
  - DAI (11-11): malla oficial, con semestre (`resp#P17`).

- **Verificado:** estructura (`V01`): `malla_program_code` `text`; `malla_creditaje`, `malla_semestre` `text`; fechas de actividad `timestamp`.
- **Cobertura y contenido:** no consultados.
- **Sin verificar (v0.2):** emparejamiento de (programa, catálogo) con `catalogo` de estados e historia; significado de `malla_formacion` (P40); 3 códigos de programa sin `programa_d`.

## common.programa_d

- **Ronda 3 (R01–R30)**
  - `R14`: `cod_banner` cubre el 100 % de las filas de estados, historia, admisión, matrícula y titulados. `R15`: 185 programas, 170 válidos, 15 no válidos, 15 con predecesor, 1 predecesor inexistente, 6 niveles.
  - DAI (11-11): `cod_banner` equivalente; los cambios de catálogo llegan con actualizaciones de malla (`resp#P07`).

- **Verificado**
  - `C06`: 185 filas, 185 ids, 185 `cod_banner`, 0 vacíos (id↔cod_banner biyectivo).
  - Columnas (`V01`): `id` `bigint`, `cod_banner` `text`, `programa_predecesor` `bigint`, `valid_program` `boolean`, `id_nivel`, `nombre_programa`, `area_conocimiento`, `facultad`, `sede`, `cod_demre`, entre otras.
  - `C07`: cobertura completa de `malla_programa.cod_programa` contra `programa_d.id`.
- **Sin verificar (v0.2):** semántica del linaje por `programa_predecesor` (1 predecesor inexistente); si incluye postgrado.

## banner.banner_catalogos y banner.banner_programas

- **Verificado:** estructura (`Q01`): `banner_catalogos` (`id`, `cod_carrera`, `catalogo`, `duracion` `integer`); `banner_programas` (`tipo_programa`, `codigo_sies`, `area_conocimiento`, `sede`, `facultad`).
- **Cobertura y contenido:** no consultados.
- **Sin verificar:** unidad de `duracion`; relación con `programa_d`.

## banner.banner_admision

- **Ronda 3 (R01–R30)**
  - `R25`: `YYYY10` 111.266 filas (derivado; N 93.606 / Y 17.660), `YYYY20` 427, `YYYY01` 40. `R23`: de 4.209 grupos repetidos, 4.202 varían `cod_admision`, 633 `matricula`, 262 `preferencia`; ninguno varía sede, `cod_demre`, `pref_demre` ni `ponderado`. `R24`: personas-período con 1/2/3/4/5+ carreras = 84.740/7.483/1.586/383/182. `R14`: `cod_carrera` 86/86 en `programa_d`.
  - DAI (11-11): N = no se matriculó, Y = se matriculó (`resp#P20`); postulación a varias carreras (`resp#P21`); normalización de puntajes por prueba (`resp#P22`).

- **Verificado**
  - `Q11`: `matricula` solo `N` (94.008) o `Y` (17.725): 111.733 filas, sin NULL (derivado).
  - `V04`: 107.036 combinaciones (year_admision, rut, cod_carrera); 4.209 repetidas; máx. 4 filas.
  - `V03`: por año de proceso 2000–2026 con N e Y; la proporción varía (2000: Y 196 / N 1.658; 2026: Y 2.749 / N 6.964). Las filas Y son casi una por persona (ej. 2026: 2.749 filas / 2.748 personas).
  - `Q10`: `year_admision` es período de 6 dígitos (`10`, `20` y 202601). Puntajes NEM y matemática informados en casi todas las filas de períodos con datos; `ponderado` informado 0 hasta 201520, 3 en 201610 y ≥ 4.699 de 4.778 en 201910.
  - Tipos (`Q01`): casi todo `text` (puntajes, `fecha_matricula`, `fecha_nacimiento`); `id_sede` `integer`.
- **Cobertura:** procesos 200010–202610.
- **Sin verificar (v0.2):** grano de la postulación (P39); cobertura de `ponderado_normalizado`; parsing de puntajes textuales y normalización por prueba (P47); Y frente a estados `M`.

## banner.banner_matricula

- **Ronda 3 (R01–R30)**
  - `R14`: 204.396 filas; `cod_carrera` 82/82 códigos en `programa_d`.

- **Verificado:** estructura (`Q01`): `year` `integer`, `fecha_estado` `date`, `cod_admision`, `tipo_admision`, `sede`, `facultad`.
- **Cobertura y contenido:** no consultados.
- **Sin verificar:** definición de matrícula efectiva, relación con estados `M` y con `banner_admision.matricula`.

## banner.banner_titulados

- **Ronda 3 (R01–R30)**
  - `R14`: 19.712 filas; `codigo_carrera` 65/65 en `programa_d`. `R28`: 19.589 personas; 122 con más de un registro; 119 con más de una carrera; 18.134 con estado `U`; 825 personas con `U` sin registro.
  - DAI (11-11): doble titulación o titulación en momentos distintos (`resp#P29`).

- **Verificado**
  - `Q12`: 2009–2026, 19.712 registros en total (derivado: suma de años); ej. 2025: 1.375 registros / 1.375 personas; 2026: 1.082 / 1.081 (año en curso); 2016: 971 / 968.
  - Tipos (`Q01`): `fecha_titulacion` `date`; `year_ingreso`, `semestre_ingreso`, `semestres_suspendidos` `integer`; `timestamp_carga` `bigint`.
- **Cobertura:** 2009–2026. En estados, `U` (Titulado) abarca 23.255 filas con fechas desde 1993 (`Q02`): ventanas distintas.
- **Sin verificar (v0.2):** 825 personas con `U` sin registro (P42); semántica de `semestres_suspendidos` vs `semestres_suspendidos_old`; relación con estados `Z`/`K`.

## banner.banner_estudiantes_postgrado

- **Ronda 3 (R01–R30)**
  - `R26`: los sufijos de postgrado `50`/`60` aparecen en oferta (6.357 y 4.767 filas). Sin mediciones nuevas sobre esta tabla. DAI (11-11): `cod_estado` vacío debe revisarse (`resp#P30`).

- **Verificado**
  - `Q13`/`V14`: períodos de postgrado terminan en `50`/`60`; `estado_matricula` MATRICULADO / NO MATRICULADO coexiste con `cod_estado` variados (M, J, W, P, E, B, N, F, T, 3). Ej. 2026: MATRICULADO sin `cod_estado` 183; W (Post-Graduado) 93 NO MATRICULADO y 12 MATRICULADO.
  - Tipos (`Q01`): `fecha_estado` `date`; `cod_estado`, `estado_matricula` `text`.
- **Cobertura:** al menos 2017–2026; consultas truncadas.
- **Sin verificar:** semántica de `W`; cod_estado vacío frecuente; cobertura anterior a 2017; solo postgrado UCN (no inferir otras instituciones).

## banner.ban_encuesta

- **Ronda 3 (R01–R30)**
  - Sin mediciones nuevas. DAI (11-11): existe un Excel de ENCE por cargar (`resp#P31`).

- **Verificado:** `Q16`: 18 tipos de encuesta; `ENC_GPR` 3.023.184 filas (202210–202610); `ENC_TRA5` 374.389 (201520–201910); `ENC_MNPG` 252.988 (202110–202220). `cantidad` `numeric`; datos agregados por pregunta y respuesta (`Q01`).
- **Cobertura:** 201510–202610 según tipo.
- **Sin verificar:** semántica de `respuesta`/`tipo_respuesta`; fuente ENCE; elegibilidad de cohortes.

## Tablas `*_full` y `*_cargas`

- **Ronda 3 (R01–R30)**
  - `R29` (cargas de los últimos 30 días): la vigencia es automática ("la más nueva con ruts ≥ 97 % del máximo histórico"). Estados: vigente = 04-11-2026 (735.932 filas, 49.582 RUT); una carga parcial de 211.173 filas / 15.800 RUT (20-10-2026). Notas: vigente = 28-10-2026 (2.670.731 / 66.125); no vigentes: dos del 04-11-2026 (2.443.729 / 64.006), 2.408.736 / 63.528 y 1.615.680 / 43.949 (21-10-2026). Las vistas de estados y notas filtran por `vigente`; las demás usan el máximo `timestamp_carga`.
  - `timestamp_carga` en epoch ms: verificado en estados y notas (`resp#P19`).

- **Verificado**
  - `V13`: estados, 1 carga vigente (timestamp 1793618317360, 735.932 filas) y 158 no vigentes (máximo timestamp 1793016203971; máx. filas 735.879). Notas: 1 vigente (1793027909119, 2.670.731) y 82 no vigentes con timestamp máximo 1793630068616 (**más nuevo que la vigente**).
  - `Q14`: la carga más nueva de notas tiene 2.443.729 filas / 64.006 RUT y `vigente=false`; la vigente tiene 66.125 RUT. Motivo registrado: "la más nueva con ruts >= 97% del máximo histórico".
  - Epoch ms: 1793630068616 corresponde a 2026-11-02 11:34 (-03), coincide con `fecha_carga` en `Q14` (derivado).
- **Sin verificar (v0.2):** si la carga de notas del 04-11-2026 es parcial o una corrección (P41); veracidad de `*_full` como foto histórica; conversión de `timestamp_carga` en otras fuentes.

## Datos abiertos MINEDUC/SIES (esquema `bench`)

- **Verificado:** estructura en `INV`: `bench.min_matricula_educacion_superior_f`, `bench.min_titulados_educacion_superior_f` (incluyen `mrun`), `bench.sies_carrera_matricula_f`, `bench.sies_carrera_titulados_f`.
- **Cobertura y contenido:** no consultados.
- **Sin verificar:** todo uso. No atribuir `mrun` a RUT UCN sin vínculo legal y técnico probado; no reidentificar.

## Diccionarios candidatos de admisión

- **Ronda 3 (R01–R30):** `R02` consultó `ban_tipo_admision` (52 códigos + NULL, con `tipo_qualitas`, `tipo_cna`, `ingreso_ordinario`, `ingreso_total`); `R03` mide su uso en estados. Los 52 códigos usados están en el diccionario (comparación R02 vs R03). `tipo_admision_d` no se consultó.

- `banner.ban_tipo_admision` (`cod_admision`, `admision`, `tipo_qualitas`, `tipo_cna`, `ingreso_ordinario`, `ingreso_total`) fue consultada en `R02`. `banner.tipo_admision_d` (`cod_admision`, `nombre_admision`, `mat_ordinaria`, `mat_total`) figura en `INV`; contenido sin consultar.
