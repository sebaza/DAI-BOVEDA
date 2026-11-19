# Vista «Lo que pasó» (DAI Neural) — diseño

**Fecha:** 18-11-2026 · **Estado:** aprobado por el usuario (boceto v2, `.superpowers/brainstorm/…/vista-historica-v2.html`).

## Intención
Vicerrectores y autoridades necesitan leer los resultados de los modelos como **cantidades de estudiantes**, no como métricas: dónde se pierden, cuántos pasan el año, cuántos son eliminados y qué se habría ganado usando el modelo. Es la parte A del enfoque elegido (C): primero lo histórico, que demuestra cuánto acierta el modelo; después (parte B, fuera de este diseño) la proyección sobre los estudiantes actuales.

## Objetivos / no objetivos / antiobjetivos
- **Objetivos:** una pestaña nueva, primera y por defecto, con cuatro bloques gráficos, cada uno con un número clave, una frase y «Cómo usarlo»; filtro Toda la UCN / facultad.
- **No objetivos:** proyección actual (parte B), cambios de modelos, reentrenamiento.
- **Antiobjetivos:** cualquier cifra por persona o lista de estudiantes; celdas de menos de 10 personas; métricas técnicas (AP, AUC) en esta vista.

## Bloques
1. **¿En qué semestre se pierden más estudiantes?** Barras apiladas por semestre de permanencia (1.º–12.º): % de la cohorte que deja la UCN y % eliminado. Número clave: % de las bajas que ocurre en el primer año. Fuente: cohortes históricas con seguimiento (snapshot de T3 / eventos de estado), descriptivo.
2. **¿Cuántos pasaron al año siguiente?** Anillo (% que siguió), «ocurrió X de N / el modelo esperaba Y / diferencia», y puntos por facultad (ocurrió ● frente a esperado ○). Fuente: T1 en prueba con el modelo conservado (`k = 1`), esperado = suma de probabilidades.
3. **¿Cuántos fueron eliminados cada año?** Línea por año: ocurrido (todos los años con dato) y esperado por el modelo (solo años de prueba de T5), con la marca del reglamento 2025 (202520). Barras por causal agrupadas con P117: 3.ª oportunidad (50-B, 52-B, 46-B), 2.ª oportunidad (50-C, 52-A, 46-A), no inscribe (50-D, 52-D, 46-D), avance o permanencia (50-A, 52-C), egresado sin titularse (77/84, 51) y otras.
4. **Si se hubiera usado el modelo.** Curva de alcance (% de estudiantes apoyados frente a % de bajas alcanzadas, con la diagonal «al azar») y «de cada 10 que no continuaron, el apoyo habría llegado a N» con el 10 % de mayor riesgo, frente a 1 al azar. Fuente: T1 en prueba.

## Restricciones
- Solo agregados; nada con n < 10 (se oculta la celda o el grupo).
- Punto en el tiempo y particiones de prueba ya definidas; sin reentrenar.
- Texto en español neutro para no técnicos; tema oscuro; sin desborde horizontal a 375 px.
- Migraciones nuevas solo con el runner (`pipelines.migrate`), nunca editar una aplicada; toda migración nueva se agrega a `EXTRA_DDL` de `backend/tests/test_neural_api.py`.

## Enfoques considerados
- A. Página con preguntas (elegida, versión gráfica v2): se lee de una pasada.
- B. Tablero con selector: menos espacio, pero oculta respuestas tras clics.

## Decisiones del constructor (mías)
- Cálculo en Redes (`evaluation/vista_historica.py` → `artefactos/vista_historica.json`) → exportador → tabla `neural_mart` (migración 029, una fila por bloque y filtro con su contenido) → endpoint de solo lectura `GET /neural/historico` → pestaña «Lo que pasó» en `NeuralPanel`.
- Gráficos con la misma biblioteca y patrón que el resto del módulo (`lib/neuralGraficos*.ts`) y las primitivas de `NeuralUI.tsx`.
