# Plan de pruebas trazado a los requisitos (RV-01, paquete EDT 4.3)

**Regla:** cada caso se definió antes de ejecutarse y su resultado se toma de la evidencia generada por las
herramientas, no de esta tabla. Los resultados de cada ejecución están en `evidence/` (reportes de pytest,
Vitest, Playwright y métricas) y se resumen en `docs/pruebas/informe-de-pruebas.md`.

| Tipo | Herramienta | Archivo |
|---|---|---|
| Unitarias del pipeline y del modelo | pytest | `apps/api/tests/test_fusion_and_model.py`, pruebas previas de `pipelines/` |
| Contrato de API contra PostGIS | pytest | `apps/api/tests/test_api_contract.py` |
| Unitarias de la interfaz | Vitest | `apps/web/src/__tests__/` |
| Extremo a extremo (sistema) | Playwright | `apps/web/e2e/critical.spec.ts` |
| Métricas M-01 a M-05, M-08 y M-09 | script | `tools/metrics/measure.py` |
| Validación con usuarios (M-10 a M-12) | protocolo y script | `docs/validacion/`, `tools/validation/consolidate.py` |

## Casos por requisito

| Req. | Caso | Precondición y datos | Resultado esperado | Prueba automatizada o evidencia | Crítico |
|---|---|---|---|---|---|
| RF-01 | Mapa del periodo activo | Corrida publicada | Todas las unidades del ámbito con nivel y leyenda coherente | `E2E-01`; `test_risk_every_result_has_full_context`; M-02 | Sí |
| RF-02 | Detalle de una unidad | Unidad seleccionada | Nivel, periodo, ID, fuentes y variables; periodo y filtros sin cambios | `E2E-03`; `test_provenance_from_a_result` | Sí |
| RF-03 | Cambio de periodo | Dos periodos publicados | Mapa, detalle y comparaciones usan el nuevo periodo | `E2E-02`; `test_periods_listed_chronologically_with_bounds`; `test_unknown_period_never_substituted` | Sí |
| RF-04 | Filtros | Filtros de nivel y distrito | Solo el subconjunto que cumple; al limpiar se restablece el conjunto | `E2E-04`; `test_level_and_district_filters`; `test_removing_filters_restores_full_set`; M-08 | Sí |
| RF-05 | Comparar zonas | 2 a 4 unidades, un periodo | Mismo periodo, corrida y escala; se rechaza mezclar vistas | `E2E-05`; `test_spatial_comparison_same_period`; `test_comparison_across_representations_is_rejected` | Sí |
| RF-06 | Comparar periodos | Una unidad y dos periodos | Misma unidad y geometría; diferencia comparable | `E2E-06`; `test_temporal_comparison_keeps_unit_fixed` | Sí |
| RF-07 | Contexto mínimo | Cualquier resultado | Periodo, unidad, nivel y leyenda siempre presentes; sin resultado explícito | `test_missing_result_is_explicit_not_zero`; Vitest `levels`; M-02 | Sí |
| RF-08 | Procedencia | Un resultado | Fuente, cobertura, variables y limitaciones | `E2E-07`; `test_provenance_from_a_result`; M-03 | Sí |
| RD-01 | Ficha de fuentes | Catálogo | Variables, cobertura, licencia, decisión de inclusión o exclusión | `data/catalog/provenance.json`; `docs/data/source-qualification.md` | No |
| RD-02 | Cobertura común | Fuentes fusionadas | Combinaciones no comparables excluidas con su motivo | `fusion_report.json` (`excluded_by_reason`); `test_coverage_offsets_follow_observation_windows` | No |
| RD-03 | Representación espacial | Eventos con coordenadas o referencias | Cada evento en una celda o distrito del ámbito; nada fuera | `test_grid_cells_belong_to_scope...`; `test_intersection_yields_point_inside_district`; M-01 | Sí |
| RD-04 | Intervalos temporales | Fechas y horas | Año, tipo de día y franja trazables a la fecha original | `test_day_type_and_band`; `events.csv` | No |
| RD-05 | Variables por grupo | Dataset | Grupos conceptuales y dimensiones no incorporadas registradas | `test_provenance_from_a_result` (exposición no incorporada); catálogo | No |
| RD-06 | Reproducibilidad del dataset | Commit y fuentes | Mismas salidas (hash) al reejecutar | `evidence/reproducibility/dataset.json` | No |
| RM-01 | Benchmark | Misma partición y métrica | Comparación de alternativas y selección justificada | `metrics.json` (`candidates`); `docs/ml/benchmark-protocol.md` | Sí |
| RM-02 | Componente CNN | Tensor conocido | Salida `[T,K,H,W]`; usa el vecindario espacial | `test_model_output_shape`; `test_cnn_uses_spatial_neighbourhood` | Sí |
| RM-03 | Componente RNN | Secuencia conocida | Orden temporal sin fuga del futuro | `test_recurrence_never_reads_the_future` | Sí |
| RM-04 | Flujo integrado | Lote preparado | Un resultado por unidad y periodo consultable sin diferencias | Conciliación del publicador; M-08 (API frente a `results.csv`) | Sí |
| RM-05 | Evaluación final | Prueba independiente | Mismas métricas para la base y el modelo; M-05 calculada | `metrics.json` (`test`); M-05 | Sí |
| RT-01 | Arquitectura | Requisitos | Cada requisito con su componente | `docs/architecture/`; tabla de mapa del repositorio | No |
| RT-02 | Servicios | Consultas válidas e inválidas | Respuestas con contexto; errores con código del contrato | `test_invalid_queries_return_contract_error`; `test_ambiguous_comparisons_rejected` | Sí |
| RT-03 | Base de datos | Datos controlados | Integridad, geometría y consultas espaciales y temporales | Migración arriba y abajo; `test_api_role_cannot_write`; `test_only_published_runs_can_be_active` | Sí |
| RV-01 | Plan de pruebas | Este documento | Cada requisito con un caso verificable | Este documento | No |
| RV-02 | Flujos críticos E2E | Pila desplegada | Todos los E2E aprobados y sin bloqueantes | `evidence/e2e/results.json`; M-07 | Sí |
| RV-03 | Validación con especialistas | 5 o más usuarios | Registro de cumplimiento, tiempo y errores | `docs/validacion/` (instrumentos); **lo ejecuta el equipo** | Sí |
| RNF-01 | Comprensión | Sesiones | Preguntas de interpretación y utilidad registradas | M-12 (instrumentos listos) | No |
| RNF-02 | Reproducibilidad | Commit y configuración | Mismos artefactos y métricas | M-04; `evidence/reproducibility/` | No |
| RG-01 | 43 distritos | Consulta del Callao | Rechazada; ninguna unidad fuera del ámbito | `test_invalid_queries_return_contract_error` (070101); `test_units_are_geojson_inside_scope` | Sí |
| RG-02 | Sin tiempo real | Rutas y servicios | Solo GET y datos por lotes | `test_no_write_routes`; revisión de `compose.yaml` | Sí |
| RG-03 | Sin recomendaciones | Textos de la interfaz | Ningún mensaje prescribe intervenciones | Revisión: `grep` de "recomend" e "interven" en `apps/web/src` (solo aparece en avisos que lo niegan) | Sí |

## Escenarios críticos de extremo a extremo (M-07)

Definidos en `apps/web/e2e/critical.spec.ts` y ejecutados sobre la aplicación desplegada con una corrida publicada:

| ID | Recorrido | Requisitos |
|---|---|---|
| E2E-01 | Mapa con todas las unidades del ámbito, leyenda y periodo activo | RF-01, RF-07 |
| E2E-02 | Cambio de periodo que actualiza mapa y barra de estado | RF-03 |
| E2E-03 | Panel de zona con riesgo, red año a año, registro histórico y procedencia | RF-02, RF-08, HU-23 |
| E2E-04 | Filtro por nivel y retiro de filtros en una acción | RF-04 |
| E2E-05 | Comparación de dos distritos en un mismo periodo | RF-05 |
| E2E-06 | Comparación de un distrito entre dos periodos | RF-06 |
| E2E-07 | Metodología con fuentes, variables y limitaciones | RF-08 |
| E2E-08 | Exportación CSV del ranking con corrida y alcance | Análisis |
| E2E-09 | Vista Modelo con arquitectura, benchmark y errores del nivel alto | RM-01, RM-05 |
| E2E-10 | Vías críticas: ranking de calles y detalle de una calle | D-09 |
| E2E-11 | Densidad registrada, vista de calor continua y capa Grad-CAM | D-09 |
| E2E-12 | Pronóstico del año siguiente con ranking, rango del ensamble y validación 2024 | D-11 |
| E2E-13 | Selección 2025–2027, comparación con año anterior y aviso de incertidumbre | D-16 |

M-07 = escenarios críticos aprobados / escenarios críticos previstos (12). Un defecto bloqueante se registra en
el [registro de incidencias](../registro-de-incidencias.md), se corrige y se vuelve a ejecutar.
