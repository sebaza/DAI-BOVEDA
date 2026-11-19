# Plan de mejora de los modelos: semana del 16-11-2026

**Objetivo:** subir el desempeño de T1 a T6 con tres palancas:
1. las fuentes que usaba el modelo anterior y DAI Neural aún no tiene (beneficios y notas parciales);
2. un modelo unificado de trayectoria;
3. las decisiones ya aprobadas o propuestas (decaimiento temporal en T2, Capstone).

**Regla común:** todo cambio se elige en **validación**, se confirma en prueba con diferencia pareada e IC 95 %, y debe pasar las pruebas de fuga de información (perturbar los datos posteriores al corte no cambia las variables).

## 1. Fuentes nuevas (revisadas el 13-11-2026, solo agregados)

| Fuente | Cobertura | Columnas útiles | Qué aporta |
|---|---|---|---|
| `banner.banner_beneficios` | Anual, 2017-2026; 7.700-9.600 personas por año | `periodo` (año), `cod_carrera`, `financiamiento` (Ayuda Gubernamental / Fondos centrales / Fondos externos), `cobertura`, `codigo`, `beneficio`, `benef_sem1`, `benef_sem2`, `total` | Situación financiera. **Pérdida de un beneficio:** lo tiene un año y no el siguiente (DAI, 13-11-2026). |
| `banner.ban_parciales_notas` | **Solo 202510 y 202610**; ≈ 11.000 personas y ≈ 2.300 secciones por período | `periodo`, `nrc`, `materia`, `curso`, componentes y subcomponentes con su peso y nota, `fecha_sub` (≈ 30 % con fecha) | Rendimiento **durante** el semestre: permite un corte a mitad de semestre. |
| `banner.analitics_results` (modelo anterior) | 13.145 estudiantes; puntaje congelado desde 09-2024 | `score` | Línea de comparación. |

**Privacidad en la extracción:**
- `rut` y `rut_estud` → `persona_key` (HMAC).
- `rut_prof` → `docente_key`.
- **No se extraen** `nombre_estud`, `nombre_prof` ni `nombre_banner`.
- Del modelo anterior solo se extraen `score` y `creation_date`.

**Punto en el tiempo de los beneficios:** el beneficio del año *t* puede asignarse o retirarse durante ese año. Para no adelantar información:
- en un corte del primer semestre del año *t* se usan los beneficios de *t* − 1 y `benef_sem1` de *t*;
- en un corte del segundo semestre se usan también los de *t*.

Se documenta como supuesto y se pregunta a la DAI en qué fecha queda registrada la asignación.

## 2. Plan por día

| Día | Trabajo | Entregable |
|---|---|---|
| **Lunes** | Extraer beneficios, notas parciales y el puntaje anterior (seudonimizados), con migración y pruebas. **Comparación cara a cara:** puntaje congelado del modelo anterior frente a T1/T5 sobre los mismos estudiantes, con resultado observado en 2025-2026. | `neural_stg/core` con las tres fuentes; informe de la comparación. |
| **Martes** | Variables nuevas en los snapshots: beneficios (tiene CAE/FSCU, gratuidad, becas, monto, cobertura, **pérdida año a año**) y riesgo reglamentario (ramos con 2.ª oportunidad reprobada). Adoptar el decaimiento temporal en T2 (P55) y regenerar las predicciones *out-of-fold* de T2 por estudiante-semestre. | Snapshots v2 con pruebas de fuga. |
| **Miércoles** | **Modelo unificado de trayectoria** sobre T3: el siguiente semestre termina en sigue / egresa / eliminado / cambia / renuncia o abandona, con T2 apilado como insumo. Se obtienen T1, T4 y T5 de un mismo modelo. | Benchmark unificado frente a T1/T4/T5 por separado. |
| **Jueves** | Corte a mitad de semestre con notas parciales (T2 y T5; entrenar con 202510 y evaluar con 202610). T6 con beneficios y el Capstone. | Resultados por tarea. |
| **Viernes** | Comparación final antes/después por tarea, por programa y por facultad. Actualizar la vista «Resultados por tarea» y documentar las decisiones. | Informes 08-12 actualizados y vista en la Bóveda. |

## 3. Qué se prueba en cada tarea

| Tarea | Hoy (test) | Qué se agrega | Hipótesis | Criterio de éxito |
|---|---|---|---|---|
| **T1 Continuidad** | AP 0,360 · AUC 0,857 | Beneficios y su pérdida; reprobaciones esperadas (T2 apilado); modelo unificado | La pérdida de un beneficio y la falta de financiamiento anticipan la no continuidad (el factor principal más frecuente del modelo anterior era «no tiene beneficio de crédito (CAE/FSCU)»; `evidencia/modelo_anterior_analitics_2026-11-13.md`) | ΔAP > 0 con IC que excluya 0 en validación; superar al modelo anterior en la comparación cara a cara |
| **T2 Reprobación** | AP 0,534 | Decaimiento temporal (+0,009 en validación); beneficios; **corte a mitad de semestre** con notas parciales | Con la mitad de las notas del semestre el AP sube fuertemente | ΔAP en validación; en parciales, AP en 202610 frente al modelo sin parciales |
| **T3 Egreso** | C(12) 0,839-0,860 | Beneficios: la gratuidad se pierde al superar la duración formal. Capstone inscrito o aprobado (señal de egreso cercano) | El Capstone y la pérdida de gratuidad marcan la cercanía del egreso | ΔC(12) e IBS con IC |
| **T4 Cambio de programa** | AP 0,094 · AUC 0,73 | Preferencia de postulación (¿entró en su 1.ª opción?); notas en ramos propios de la carrera frente a ramos generales; modelo unificado; **recalibración** | Quien no entró en su primera opción y rinde mejor en ramos generales cambia más | Corregir la sobreestimación de ≈ 7 pts; ΔAP en validación. Se acepta que siga siendo útil sobre todo por programa |
| **T5 Eliminación** | AP 0,554 (0,646 sin los años dudosos) | Riesgo reglamentario (ramo con 2.ª oportunidad reprobada, P(reprobar 3.ª) desde T2); beneficios; notas parciales; separar las vías con el diccionario de causales | La vía reglamentaria (≈ 30 % de los E) se vuelve casi predecible; la de abandono (≈ 34 %) se parece a T1 | ΔAP en validación sin los años dudosos; AP por vía cuando haya diccionario |
| **T6 Postgrado** | AP 0,046 · AUC 0,70 | Nota de titulación 70/30 con el Capstone (P89); beneficios; foco en magíster | La distinción del título y el área anticipan el magíster UCN | Pasar el umbral de viabilidad de CatBoost (100 eventos en entrenamiento) o mejorar AP/AUC de Cox con IC |

*Nota (D112):* el AP 0,360 de T1 (prueba con las cohortes 2022-2023, solo variables académicas) no es comparable con los 0,205 y 0,248 de la cohorte 2025 (sin y con beneficios): son otras cohortes, otro número de eventos y otro conjunto de datos.

## 4. Pendientes que condicionan el plan

| Pendiente | Afecta | Quién |
|---|---|---|
| P75: caída de los estados E y de reintegro desde 2024-2 | T5, modelo unificado | DAI / Banner |
| Diccionario de causales de E (0A, 0B, 0D, 2D, 84…) | T5 por vía | DAI |
| Fecha en que se registra la asignación o la pérdida de un beneficio | Punto en el tiempo de los beneficios | DAI |
| Fuente de los diagnósticos institucionales (matemáticas, inglés) | T1, T2 de primer año | DAI (no se encontró en el almacén) |
| Solo dos semestres de notas parciales | Corte a mitad de semestre | Resultado exploratorio hasta tener más semestres |

## 5. Lo que no cambia

- Sin predicciones individuales en la Bóveda hasta la revisión institucional.
- Agregados con n ≥ 10.
- `sexo` solo para equidad.
- Ningún dato personal en los documentos.
- Sin commits hasta que la DAI lo decida.
