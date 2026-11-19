| Métrica | Antes | Después | Cambio |
|---|---|---|---|
| oficial (train desde 2015), k = 1: AP de test, Tasa histórica (programa, k) | 0,071 [0,061; 0,086] | 0,071 [0,061; 0,086] | +0,000 |
| oficial (train desde 2015), k = 1: AP de test, CatBoost, solo ingreso | 0,104 [0,085; 0,132] | 0,104 [0,085; 0,133] | +0,001 |
| oficial (train desde 2015), k = 1: AP de test, Logística, ingreso + agregados | 0,305 [0,250; 0,360] | 0,307 [0,251; 0,360] | +0,001 |
| oficial (train desde 2015), k = 1: AP de test, CatBoost, ingreso + agregados | 0,341 [0,280; 0,394] | 0,360 [0,303; 0,416] | +0,020 |
| oficial (train desde 2015), k = 1: AP de test, GRU, ingreso + secuencia | 0,325 [0,268; 0,380] | 0,330 [0,271; 0,384] | +0,005 |
| oficial (train desde 2015), k = 1: ROC-AUC de test, CatBoost, ingreso + agregados | 0,854 [0,828; 0,875] | 0,857 [0,832; 0,879] | +0,003 |
| oficial (train desde 2015), k = 1: GRU − CatBoost, ΔAP pareado | -0,015 [-0,036; 0,007] | -0,030 [-0,052; -0,009] | -0,015 |
| oficial (train desde 2015), k = 2: AP de test, Tasa histórica (programa, k) | 0,122 [0,109; 0,136] | 0,122 [0,109; 0,136] | +0,000 |
| oficial (train desde 2015), k = 2: AP de test, CatBoost, solo ingreso | 0,165 [0,145; 0,189] | 0,163 [0,143; 0,187] | -0,002 |
| oficial (train desde 2015), k = 2: AP de test, Logística, ingreso + agregados | 0,545 [0,500; 0,592] | 0,537 [0,492; 0,585] | -0,008 |
| oficial (train desde 2015), k = 2: AP de test, CatBoost, ingreso + agregados | 0,549 [0,503; 0,594] | 0,552 [0,506; 0,596] | +0,002 |
| oficial (train desde 2015), k = 2: AP de test, GRU, ingreso + secuencia | 0,539 [0,489; 0,586] | 0,526 [0,478; 0,575] | -0,013 |
| oficial (train desde 2015), k = 2: ROC-AUC de test, CatBoost, ingreso + agregados | 0,890 [0,874; 0,905] | 0,890 [0,874; 0,906] | +0,000 |
| oficial (train desde 2015), k = 2: GRU − CatBoost, ΔAP pareado | -0,011 [-0,029; 0,009] | -0,026 [-0,042; -0,007] | -0,015 |
| sensibilidad (todas las cohortes), k = 1: AP de test, Tasa histórica (programa, k) | 0,073 [0,062; 0,089] | 0,073 [0,062; 0,089] | +0,000 |
| sensibilidad (todas las cohortes), k = 1: AP de test, CatBoost, solo ingreso | 0,100 [0,083; 0,124] | 0,103 [0,086; 0,130] | +0,003 |
| sensibilidad (todas las cohortes), k = 1: AP de test, Logística, ingreso + agregados | 0,307 [0,253; 0,363] | 0,312 [0,260; 0,367] | +0,004 |
| sensibilidad (todas las cohortes), k = 1: AP de test, CatBoost, ingreso + agregados | 0,322 [0,267; 0,379] | 0,329 [0,272; 0,384] | +0,007 |
| sensibilidad (todas las cohortes), k = 1: AP de test, GRU, ingreso + secuencia | 0,318 [0,263; 0,369] | 0,306 [0,251; 0,362] | -0,011 |
| sensibilidad (todas las cohortes), k = 1: ROC-AUC de test, CatBoost, ingreso + agregados | 0,850 [0,825; 0,873] | 0,852 [0,826; 0,874] | +0,001 |
| sensibilidad (todas las cohortes), k = 1: GRU − CatBoost, ΔAP pareado | -0,005 [-0,027; 0,016] | -0,023 [-0,050; 0,006] | -0,018 |
| sensibilidad (todas las cohortes), k = 2: AP de test, Tasa histórica (programa, k) | 0,122 [0,109; 0,136] | 0,122 [0,109; 0,136] | +0,000 |
| sensibilidad (todas las cohortes), k = 2: AP de test, CatBoost, solo ingreso | 0,166 [0,147; 0,192] | 0,167 [0,147; 0,192] | +0,001 |
| sensibilidad (todas las cohortes), k = 2: AP de test, Logística, ingreso + agregados | 0,546 [0,500; 0,592] | 0,540 [0,494; 0,588] | -0,006 |
| sensibilidad (todas las cohortes), k = 2: AP de test, CatBoost, ingreso + agregados | 0,552 [0,507; 0,596] | 0,552 [0,507; 0,598] | -0,000 |
| sensibilidad (todas las cohortes), k = 2: AP de test, GRU, ingreso + secuencia | 0,538 [0,489; 0,586] | 0,534 [0,485; 0,583] | -0,005 |
| sensibilidad (todas las cohortes), k = 2: ROC-AUC de test, CatBoost, ingreso + agregados | 0,890 [0,874; 0,905] | 0,889 [0,873; 0,906] | -0,001 |
| sensibilidad (todas las cohortes), k = 2: GRU − CatBoost, ΔAP pareado | -0,014 [-0,032; 0,005] | -0,018 [-0,038; 0,003] | -0,004 |
| Pregunta | Respuesta de la DAI | Consecuencia en este informe |
|---|---|---|
| P49 | Los segundos semestres anteriores a 2015 probablemente nunca se registraron; no pueden usarse. | La regla de cobertura (corte u horizonte en un período `20` anterior a `201520` ⇒ sin cobertura, fuera de modelos) deja de ser provisional (§1, §2). |
| P50 | La forma de registrar las salidas debió de cambiar hacia 2014; la DAI buscará registros anteriores, por ahora se usan los datos tal como están. | **Configuración oficial: entrenar con las cohortes 2015–2019** (valid 2020–2021, test 2022–2023). La corrida con todas las cohortes ≤ 2019 se conserva como sensibilidad (§9). Las filas anteriores a 2015 siguen en el snapshot con su estado, para auditoría. |
| P51 | «No continuidad» = el estudiante ya no se encuentra matriculado. | **Verificado contra la implementación, sin cambios:** `continua` = estado de matrícula, reintegro o cambio de ciclo en el período del horizonte en cualquier programa de la UCN; egreso o titulación hasta el horizonte cuenta como término de ciclo, no como no continuidad. Ninguna etiqueta cambia (§1). |
| P52 | Se pueden excluir las filas que ya tienen un estado de salida en el período del corte. | La exclusión (1.982 filas en `k = 1`, 990 en `k = 2`) queda confirmada (§2). |
