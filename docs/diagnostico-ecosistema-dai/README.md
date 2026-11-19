# Diagnóstico de ecosistema DAI — Bóveda DAI

Informe técnico, funcional y conceptual de la aplicación **Bóveda DAI** (y de su único módulo actual, el **Termómetro Institucional**, identificador interno `percepcion`). Es uno de los cinco diagnósticos previstos para diseñar el ecosistema digital de la Dirección de Análisis Institucional (DAI) de la Universidad Católica del Norte (UCN).

| Dato | Valor |
|---|---|
| Fecha del análisis | 2026-10-22 |
| Repositorio | `DAI-BOVEDA` |
| Rama y commit analizados | `main`, `6879a9e` ("feat: renombrar subtemas desde Curación") |
| Método | Análisis estático del repositorio y tres confirmaciones del responsable (madurez, responsables y usuarios objetivo) |
| Alcance | Código versionado, documentación de `docs/`, scripts, migraciones SQL y pruebas. No se ejecutó la aplicación ni las pruebas, ni se abrió ninguna base de datos |

## Entregables

| Archivo | Contenido | Para quién |
|---|---|---|
| [00_RESUMEN_EJECUTIVO.md](00_RESUMEN_EJECUTIVO.md) | Qué es, para quién, en qué estado está y qué se encontró, en dos páginas | Dirección y equipo DAI sin conocimiento del código |
| [01_FICHA_FUNCIONAL.md](01_FICHA_FUNCIONAL.md) | Identificación, actores, módulos, flujos (Mermaid), reglas de negocio | Analistas funcionales |
| [02_ARQUITECTURA_TECNICA.md](02_ARQUITECTURA_TECNICA.md) | Stack, componentes, modelo de datos, inventario de API, autenticación, calidad y operación | Arquitectura y desarrollo |
| [03_UX_IDENTIDAD_NAMING.md](03_UX_IDENTIDAD_NAMING.md) | Inventario UX, identidad visual con valores concretos, análisis semántico para naming, guía de capturas | Diseño, marca y naming |
| [04_INTEGRACION_ECOSISTEMA.md](04_INTEGRACION_ECOSISTEMA.md) | Capacidades expuestas y reutilizables, matriz de integración, servicios compartidos, recomendaciones incrementales | Arquitectura de integración |
| [05_HALLAZGOS_Y_PREGUNTAS.md](05_HALLAZGOS_Y_PREGUNTAS.md) | Hallazgos, riesgos, evaluación de madurez 1–5, preguntas abiertas y recomendaciones priorizadas | Responsables y comité de decisión |
| [06_FICHA_NORMALIZADA.json](06_FICHA_NORMALIZADA.json) | Ficha en JSON con el esquema común (`schema_version` 1.0) para comparar las cinco aplicaciones | Comparación automatizada |

## Cómo leer los estados de evidencia

Cada afirmación relevante lleva una etiqueta y, cuando corresponde, una referencia `ruta:línea` o `ruta` + símbolo, relativa a la raíz del repositorio.

| Etiqueta | Significado |
|---|---|
| **Confirmado** | Comprobado directamente en el código, en la configuración o en la documentación versionada |
| **Confirmado por el responsable** | Dato entregado por el responsable de la aplicación el 2026-10-22, sin respaldo en el repositorio |
| **Inferido** | Conclusión razonable a partir de evidencia parcial |
| **Propuesto** | Recomendación para una arquitectura o identidad futura. Nunca describe el estado actual |
| **No verificado** | Requiere confirmación humana o evidencia que no está en el repositorio |

Las propuestas aparecen siempre en secciones tituladas como tales («Propuesto», «Recomendaciones»), separadas de la descripción del estado actual.

## Convenciones

- Los números de línea corresponden al commit `6879a9e` y pueden desplazarse con cambios posteriores.
- Los documentos de `docs/` anteriores a este diagnóstico describen el módulo cuando vivía dentro de la Torre de Control. El propio `README.md` del repositorio los declara «historia del módulo». Aquí se citan como contexto histórico, no como descripción de la Bóveda.
- No se reproducen valores de variables de entorno, credenciales, correos de personas, identificadores de cuentas personales de redes sociales ni texto de comentarios reales. Cuando el repositorio contiene datos de ese tipo, se describen solo por categoría.

## Limitaciones del análisis

- **Sin ejecución.** La aplicación es un prototipo local cuya base contiene comentarios reales. No se levantó ni se tomaron capturas: [03_UX_IDENTIDAD_NAMING.md](03_UX_IDENTIDAD_NAMING.md) incluye una guía de capturas manuales.
- **Worker externo fuera de alcance.** El repositorio que produce los datos (`Sentiment_Analisys_University`) no está disponible aquí: la implementación del scoring se describe solo por su contrato y por la documentación.
- **Otras aplicaciones DAI.** Torre de Control, Sonda, Sonda Intelligence y Plataforma CAPD no forman parte de este repositorio. Sonda, Sonda Intelligence y CAPD no se mencionan en ningún archivo, así que toda hipótesis de integración con ellas es **Propuesta** con confianza baja.
- **Archivos `.env.example`.** Los nombres de variables se tomaron de `backend/app/config.py`, del `README.md` y de los usos de `process.env`. Uno de los análisis no pudo abrir esos archivos por permisos; otro sí leyó `backend/.env.example` y detectó que está desactualizado (ver [05](05_HALLAZGOS_Y_PREGUNTAS.md)).
- **Conteos estáticos.** Las cifras de pruebas (unas 715 funciones `def test_`) y de endpoints (53 handlers) salen de búsquedas en el código, no de una ejecución.

## Comprimir los entregables

Desde la raíz del repositorio (PowerShell):

```powershell
Compress-Archive -Path docs\diagnostico-ecosistema-dai -DestinationPath diagnostico-ecosistema-dai-boveda.zip
```

La carpeta contiene solo documentación, sin datos sensibles.
