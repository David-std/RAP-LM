# Control del desarrollo técnico

Registro operativo del desarrollo del MVP (sección 12 del handoff). Distingue lo **comprobado** (ejecutado o
leído) de lo pendiente. Las cifras provienen de los archivos en `evidence/` y de los artefactos de corrida;
ninguna se escribe a mano sin su fuente. Las decisiones y solicitudes de cambio están en
`DECISIONES_TECNICAS.md`.

## 1. Fase 0: diagnóstico al inicio (2026-11-22)

**Repositorio:** `David-std/RAP-LM`. Estado de las ramas: `main` en `40217fd`, `develop` en `0998d45` y el
PR #10 (draft) en `0558060`, sobre la rama `analysis/feature-target-contract`. El trabajo parte de la punta del
PR #10 en la rama `feature/mvp-integration`.

**Suite existente:** 63 pruebas aprobadas y `ruff` sin observaciones antes de cualquier cambio.

| EDT | HU/HT | Artefacto existente al inicio | Estado comprobado | Faltante |
|---|---|---|---|---|
| 3.1.1 | HT-01 | `docs/data/source-qualification.md`, `pipelines/profiling`, captura de 61 fuentes y armonización v0.2.0 (fuera de Git) | Parcial: perfilamiento real, sin objetivo general aprobado | Cobertura común para todas las severidades |
| 3.1.2 | HT-02 | `docs/ml/analytical-protocol.md`, experimentos de representación | Diseñado | Benchmark ejecutado |
| 3.1.3 | HT-03 | C4 y contratos en el PR #10 | Diseñado | Contrato implementado y probado |
| 3.1.4 | HT-04 | Esquema propuesto en `docs/contracts/persistence-and-publication.md` | Diseñado | Migraciones, roles e índices |
| 3.1.5 | PR-01, PR-02 | Prototipo de Claude Design (artefacto y capturas) con datos simulados | Hecho como prototipo | Integración con la API |
| 3.2.1 | HT-05, HT-06 | Armonización v0.2.0: 14.362 eventos de cohortes separadas; gates G1, G3 a G6 bloqueados | Parcial | Dataset fusionado de todas las severidades en malla |
| 3.2.2 / 3.2.3 | HT-07, HT-08 | Solo el protocolo | No implementado | CNN y LSTM |
| 3.3.1 | HT-09 | FastAPI con `RiskProvider` SHA-256 sintético por petición | Contrario a la arquitectura por lotes | API de solo lectura sobre resultados publicados |
| 3.3.2 | HT-10 | — | No implementado | PostGIS |
| 3.3.3 | EP-01 a EP-05 | React con mapa de puntos sintético | Parcial | Interfaz completa del diseño |
| 3.4.x | HT-11, HT-12 | — | No implementado | Publicación, integración y E2E |
| 4.3 / 4.4 / 4.5 | — | Métricas trazadas sin medición | No medido | Medición y evaluación |

**Hallazgo de alcance:** en la primera revisión el profesor observó que el riesgo no puede limitarse a
atropellos fatales. Se atendió con la decisión **D-01**: fusión de fuentes con objetivo de todas las
severidades.

## 2. Bitácora por paquete

Cada entrada sigue la plantilla del handoff. El responsable humano y la revisión del PR los completa el
equipo: una IA no aprueba PR.

### 3.2.1 Dataset fusionado (HT-05, HT-06; RD-02 a RD-06, RG-01)
- **Cambio:** malla de 1 km en EPSG:32718 (2.899 celdas, 43 distritos), georreferenciación por reglas contra
  10.486 calles de OSM, fusión CENACOM más ONSV y contexto por celda. Commit `454b3ad`.
- **Resultado comprobado** (`fusion_report.json`): 14.158 eventos fusionados.

  | Fuente | Ubicación | Eventos |
  |---|---|---|
  | CENACOM | cruce de calles | 1.024 |
  | CENACOM | tramo de vía | 7.187 |
  | CENACOM | solo distrito | 5.105 |
  | ONSV | punto | 817 |
  | ONSV | solo distrito | 25 |

  Exclusiones con motivo:
  - 78 eventos de San Isidro (cohorte no comparable);
  - 55 de ONSV 2025 (año abierto);
  - 56 sin hora;
  - 15 con fecha inválida.
- **Reproducibilidad (RD-06):** reconstruido desde el commit `cf9cfb5`, los seis artefactos son idénticos en
  SHA-256 a la primera construcción (`evidence/reproducibility/dataset.json`).
- **Criterios aún no satisfechos:** la precisión de la georreferenciación no está validada contra una muestra
  revisada por personas; queda registrada como limitación L03.

### 3.1.4 / 3.3.2 Base de datos (HT-04, HT-10; RT-03)
- Migración Alembic probada arriba, abajo y arriba otra vez, con 21 tablas, índices GiST y un trigger de
  publicación. Los roles quedan separados. Commit `b7be10d`.
- Pruebas: `test_api_role_cannot_write` y `test_only_published_runs_can_be_active`.

### 3.3.1 API (HT-09; RT-02)
- Implementa los cinco recursos más `/series` (D-06). 26 pruebas de contrato contra PostGIS. Commit
  `3818b14`.
- Defecto encontrado por las pruebas: los periodos salían con el fin de semana antes que el día laborable
  (`ORDER BY day_type DESC`). Se corrigió y se volvió a ejecutar.

### 3.3.3 Interfaz (EP-01 a EP-05)
- Port del diseño a React y TypeScript, más la vista Análisis pedida por el Product Owner. 7 pruebas Vitest y
  8 escenarios E2E con Playwright. Commits `d01d720` y `af4cf8d`.

### Despliegue (RNF-02, 5.3)
- `docker compose up -d --build` levanta db, migrate, api y web. Verificado *fail-closed*: sin corrida
  publicada, `/api/v1/periods` responde `503 NO_PUBLISHED_RUN` y la web no muestra datos simulados.

### 3.2.2 / 3.2.3 / 4.4 Modelo y evaluación (HT-02, HT-07, HT-08; RM-01 a RM-05)

Las corridas se entrenaron desde el commit `cf9cfb5` (ver la incidencia I-10). Reporte completo en
`evidence/benchmarking/REPORT.md`.

**Corrida publicada** `fused-cnnlstm-2026.11-r1`: prueba ONSV 2024, con 233 eventos.

- Seleccionado por pérdida de validación: **ConvLSTM**.
- E del modelo: 0,583 frente a 0,607 del promedio histórico, es decir **M-05 = +3,85 %** (cumple la meta > 0 %).
- El GLM de Poisson logra el menor E (+7,35 %); se reporta.
- Devianza por celda: 0,066 frente a 0,116 de la base.
- Captura del 10 % de celdas: 60,3 % frente a 62,1 % de la base.

**Backtest de todas las severidades** `fused-cnnlstm-backtest-2017`: prueba CENACOM de enero a junio de 2017,
con 1.629 eventos.

- Seleccionado: CNN-LSTM.
- **M-05 = −6,29 %** (no cumple). Ningún modelo supera al promedio histórico en E.
- La devianza por celda es menor que la de la base (0,089 frente a 0,098).

**Interpretación:** sobre la población de todas las severidades, la red no supera al promedio histórico en la
medida principal. Las causas por analizar (hipótesis, no verificadas) son:

- secuencia corta;
- semestre de prueba;
- contexto estático;
- selección por NLL en lugar de por E.

Cualquier ajuste será una corrida nueva preregistrada; el protocolo no se cambia tras ver la prueba.

### 4.3 Verificación (RV-01, RV-02) y métricas medidas

Las métricas se midieron contra la API publicada (`evidence/metrics/*.json`, `tools/metrics/measure.py`).

| Métrica | Valor medido | Meta | Estado |
|---|---|---|---|
| M-01 correspondencia espacial | 817/817 = 100 % | ≥ 95 % | Cumple |
| M-02 completitud | 258.896/258.896 = 100 % | ≥ 95 % | Cumple |
| M-03 trazabilidad | 200/200 = 100 % | ≥ 95 % | Cumple |
| M-04 reproducibilidad del pipeline | Dataset: 6/6 artefactos idénticos. Corrida: no medida | ≥ 95 % | Parcial: falta reentrenar y comparar |
| M-05 mejora frente a la base | +3,85 % (ONSV 2024); −6,29 % (backtest de todas las severidades) | > 0 % | Cumple en la prueba principal; no cumple en el backtest |
| M-06 RF obligatorios aceptados | 8/8 con pruebas automatizadas aprobadas | 100 % | Pendiente: aceptación del Product Owner |
| M-07 escenarios críticos E2E | 8/8 aprobados, 0 bloqueantes | 100 % | Cumple (`evidence/e2e/results.json`) |
| M-08 consultas, filtros y comparaciones | 188/188 = 100 % (100 % críticos) | ≥ 95 % | Cumple |
| M-09 p95 de la API | 0,19 s (200 peticiones, 0 errores, carga secuencial) | ≤ 2 s | Cumple; no incluye el renderizado |
| M-10 a M-12 validación con usuarios | Sin medición | — | Pendiente: sesiones del equipo |
| M-13 a M-15 gestión | No se calculan en el repositorio | — | — |

**Pruebas:**

- Backend: 107 pruebas pytest (unitarias y de contrato contra PostGIS).
- Interfaz: 7 pruebas Vitest y 8 escenarios E2E de Playwright.
- Lint: `ruff` sin observaciones.
- Capturas de la aplicación con la corrida publicada en `evidence/screenshots/`.

## 3. Registro de incidencias reales

| ID y fecha | Requisito y EDT | Síntoma y evidencia | Causa | Decisión y ejecución | Verificación | Lección |
|---|---|---|---|---|---|---|
| I-01 2026-11-22 | RD-03, 3.2.1 | La construcción falló con `ValueError: Cannot linemerge LINESTRING` | Calles OSM de un solo tramo: `linemerge` exige MultiLineString (comprobado) | Fusionar solo si es MultiLineString | La construcción se completa | Probar entradas degeneradas en geometría |
| I-02 2026-11-22 | RD-03, 3.2.1 | La georreferenciación seguía tras más de 10 minutos | Comparación difusa contra todas las calles del distrito por candidato, sin caché (comprobado con perfil: 300 eventos en 0,6 s tras optimizar) | Caché por distrito y prefiltros `real_quick_ratio` y `quick_ratio` | Lote completo en minutos | Perfilar una muestra antes de lanzar el lote |
| I-03 2026-11-22 | RT-03 | Alembic quedó bloqueado sin conectarse a `localhost:5433` | `localhost` resolvía a IPv6 y Docker publica en 127.0.0.1 (comprobado: conecta con 127.0.0.1) | URL por defecto `127.0.0.1` | Migración arriba y abajo correcta | Usar IP explícita en Windows |
| I-04 2026-11-22 | RM-01, 3.1.2 | Dos entrenamientos escribían en la misma carpeta | Un comando previo continuó tras un error (`;` en lugar de `&&`) | Se detuvo la corrida obsoleta; se relanzó desde el commit | Una sola corrida por carpeta | Encadenar con `&&` y verificar procesos |
| I-05 2026-11-22 | RM-01, 3.1.2 | El benchmark estimado superaba 2 horas | 1 hilo y 800 épocas (medido: 1,9 a 2,7 s por época) | 8 hilos fijos y registrados; 300 épocas con paciencia 40, antes de ver la prueba | Corrida completa en minutos | Medir tiempo por época antes de fijar épocas |
| I-06 2026-11-22 | RT-02, 3.3.1 | Prueba de contrato fallida en el orden de periodos | `ORDER BY day_type DESC` | Orden ascendente | 26/26 | Fijar el orden esperado en pruebas |
| I-07 2026-11-22 | RNF-02, 5.3 | La web no publicaba en `127.0.0.1:8080` | Puerto ocupado por otro servidor local (respondía un 404 de Apache ajeno) | Puerto configurable, 8088 por defecto | Web 200 y `/health` correcto | Parametrizar puertos |
| I-08 2026-11-22 | RF-06, 3.3.3 | E2E-06 falló: no aparecía la serie de años | La serie pide 11 periodos y la API limitaba a 8 (422); también afectaba la evolución temporal del mapa (comprobado) | Límite de 24 periodos y prueba de regresión | E2E 8/8 | Probar límites con el número real de periodos publicados |
| I-09 2026-11-22 | RT-03, 3.4.4 | La publicación se rechazó: `area_fraction` igual a 0 en `F41-C22` | Astilla de borde de menos de 10⁻⁶ redondeada a 0 | Omitir participaciones nulas; la transacción revirtió completa (atomicidad comprobada) | Publicación conciliada | Validar restricciones antes de cargar |
| I-10 2026-11-22 | RNF-02, RD-06 | Las corridas registraron `code_commit_sha = "unknown"` | Python en Windows no encuentra `git` (solo existe en Git Bash) | `pipelines/lineage.py` lee `.git` directamente y registra si el árbol está limpio. Atestación: `git diff cf9cfb5 HEAD` no muestra cambios en `ml/fused`, `pipelines/fusion`, `pipelines/spatial` ni `ml/configs`, así que la corrida usó el código de `cf9cfb5`. Los artefactos publicados no se modificaron | Prueba `test_git_sha_is_resolved_without_git_executable` | No depender de ejecutables externos para el linaje |
| I-11 2026-11-22 | 3.3.3 | Las capturas mostraban textos en inglés, el layout no llenaba la altura y el selector de herramientas se superponía | Textos del catálogo en inglés; fila vacía de la grilla cuando no hay aviso demo | Catálogo en español, contenedor flex y CSS | Capturas revisadas | Revisar capturas reales, no solo pruebas |
| I-12 2026-11-22 | RM-01, 3.1.2 | Corridas v2 y de explicaciones detenidas por el sistema por falta de memoria (521 MB libres de 16 GB) | Otro proceso local (Ollama de otra sesión) y Docker ocupaban la memoria (comprobado: tras cerrar Ollama, 5,3 GB libres) | Cerrar Ollama, detener API y web durante el entrenamiento y correr una sola tarea a la vez; la búsqueda v2 se reinició desde cero (enmienda A1) | Ver resultados v2 | Planificar memoria antes de lotes largos |
| I-13 2026-11-22 | RD-05, RM-05 | Revisión del plan v1.6 frente al MVP: el riesgo debía relacionar frecuencia, severidad, exposición y entorno, y la evaluación debía reportar falsos positivos y negativos del nivel alto | Solo se modelaba la frecuencia con siete proxies (comprobado en el código) | D-10: dataset v1.1 con ocho proxies de OSM, componentes de severidad y exposición, desglose por subtipo y severidad, y matriz de confusión del nivel alto | 35 pruebas de contrato; v1 evaluada con el mismo código | Contrastar cada indicador con el marco conceptual del plan, no solo con los requisitos |

## 4. Pendientes que dependen del equipo

- Aprobar o rechazar D-01 y D-06 en el control integrado de cambios y actualizar la Matriz de Trazabilidad.
- Revisar y aprobar los PR (DoD 1): una IA no aprueba en nombre del equipo.
- Ejecutar la validación con al menos cinco especialistas con los instrumentos de `docs/validacion/` (M-10
  a M-12).
- Registrar horas y avance en Microsoft Project (DoD 5).
