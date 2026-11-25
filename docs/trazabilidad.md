# Delivery traceability and verification status

**Baseline:** integrated project plan v1.6 (§3.11 Figures 5A to 5E, §4.2.1 WBS dictionary, §8.1 Tables 34 to 36).
**Reading rule:** *Implemented* means the code exists and its automated tests pass; *Measured* means the metric
was computed against the running stack and its JSON is in `evidence/`; *Accepted* is a team decision recorded
outside the repository (Sprint Review, change control). Measured values are in
[pruebas/informe-de-pruebas.md](pruebas/informe-de-pruebas.md).

## WBS packages

| WBS | Deliverable | Repository evidence | Status |
|---|---|---|---|
| 3.1.1 | Source profiling | `docs/data/source-qualification.md`, `data/catalog/provenance.json`, `pipelines/profiling` | Implemented |
| 3.1.2 | Benchmarking of modelling alternatives | `ml/fused/train.py`, `ml/fused/search.py`, `docs/ml/benchmark-protocol*.md`, `docs/benchmarking/informe-de-benchmarking.md` | Implemented, measured |
| 3.1.3 | Logical and physical architecture, API contract | `compose.yaml`, `docs/api/contract.md`, design history in `docs/architecture/` | Implemented |
| 3.1.4 | Spatial and temporal data model | `database/migrations` (0001 to 0003) | Implemented |
| 3.1.5 | Navigable prototype | Navigable design prototype (PR-01, PR-02), implemented in `apps/web` | Implemented |
| 3.2.1 | Versioned analytical dataset | `pipelines/fusion`, dataset manifests with SHA-256, `evidence/reproducibility/dataset.json` | Implemented, reproduced |
| 3.2.2 | CNN component | `ml/fused/model.py`, tests `test_model_output_shape`, `test_cnn_uses_spatial_neighbourhood` | Implemented |
| 3.2.3 | RNN component | `ml/fused/model.py`, test `test_recurrence_never_reads_the_future` | Implemented |
| 3.2.4 | Explicabilidad del modelo | `ml/fused/explain.py` (atribución, qué pasaría si), `ml/fused/saliency.py` (Grad-CAM, variante HiResCAM), test `test_gradcam_is_non_negative_and_localised`; vistas Modelo y capa Grad-CAM | Implemented |
| 3.2.5 | Pronóstico anual encadenado (D-11, D-16) | `ml/fused/forecast.py`, migración 0005, `GET /api/v1/forecast`, vista Pronóstico; tests `test_forecast_next_year`, `test_forecast_chained_horizons`, E2E-12/13 | Implemented |
| 3.2.6 | Registro enriquecido y entorno (D-12) | `pipelines/fusion/vehicles.py` (vehículo, servicio y factores por edición), `pipelines/publication/context_profile.py`, migraciones 0006 y 0007; tests `test_cenacom_vehicle_codes_follow_each_edition`, `test_cenacom_factor_codes_follow_each_edition`, `test_context_profile_percentiles` | Implemented |
| 3.2.8 | Política espacial de eventos por comisaría (D-14) | `pipelines/fusion/events.py`, dataset v1.4, brazo de sensibilidad `v4-sens-exclude-station`; test `test_station_proxy_events_never_reach_a_cell` | Implemented, measured |
| 3.2.7 | Entrenamiento en GPU (recurso del plan) | `ml/fused/train.py` (dispositivo), `requirements-gpu.txt`, `tools/reports/device_comparison.py`, `evidence/benchmarking/device_comparison.json` | Implemented, measured |
| 3.3.1 | Read API | `apps/api`, contract tests against PostGIS | Implemented |
| 3.3.2 | Spatial database | PostGIS, GiST indexes, separated roles | Implemented |
| 3.3.3 | Web interface | `apps/web` (map, corridors, comparators, analysis, model, methodology) | Implemented |
| 3.4.1 to 3.4.3 | Integration and critical flows | Playwright journeys `apps/web/e2e` | Implemented, measured (M-07) |
| 3.4.4 | Model outputs stored and served unchanged | `pipelines/publication` reconciliation, M-08 | Implemented, measured |
| 4.3 | Verification | `docs/pruebas/plan-de-pruebas.md`, pytest, Vitest, Playwright, `tools/metrics` | Measured |
| 4.4 | Technical evaluation against the historical average | `evidence/benchmarking`, `docs/ml/performance-v10.md` (out-of-sample evaluation, ablation), `evidence/benchmarking/performance-v13` (transfer pilot), `performance-v14` (horizons), M-05 per D-17 | Measured |
| 3.2.9 | Final refit of the selected architecture (D-18) | `ml/configs/v5-final.json`, `fixed_config`/`fixed_epochs` in `ml/fused/search.py` and `train.py`, run `fused-cnnlstm-2026.11-v5`, M-04 | Implemented, measured |
| 4.5 | Validation with at least five specialists | Instruments in `docs/validacion`, consolidation `tools/validation` | Instruments ready; sessions run by the team |
| 5.1 to 5.3 | Manual, closure, clean installation | `docs/manual-de-usuario.md`, `README.md` | Implemented |
| 5.3 | Despliegue de demostración (D-13) | `render.yaml`, `tools/deploy/remote_setup.py` (probado sobre una base vacía), test `test_config.py` | Implemented, pending cloud account |

## Quality metrics (Table 35)

| Metric | Measured by | Evidence |
|---|---|---|
| M-01 Spatial correspondence | `tools/metrics/measure.py` | `evidence/metrics/M-01.json` |
| M-02 Result completeness | same | `evidence/metrics/M-02.json` |
| M-03 Source and version traceability | same | `evidence/metrics/M-03.json` |
| M-04 Pipeline reproducibility | rerun of the published configuration | `evidence/metrics/M-04.json` |
| M-05 Prioritisation over the historical average (D-17; original MAE measurement kept as history) | cell-year average precision, all-severity test, models trained without the scored year | `evidence/metrics/M-05.json`, `evidence/benchmarking/fused-cnnlstm-2026.11-v5.evaluation.json`, `docs/architecture/registro-de-decisiones.md` |
| M-06 Mandatory RF accepted | test plan per requirement | `docs/pruebas/plan-de-pruebas.md`; acceptance by the Product Owner |
| M-07 Critical end-to-end scenarios | Playwright | `evidence/e2e/results.json` |
| M-08 Query, filter and comparison correctness | API vs exported results | `evidence/metrics/M-08.json` |
| M-09 API p95 latency | sequential load | `evidence/metrics/M-09.json` |
| M-10 to M-12 Specialist success, time, interpretation | specialist sessions | `docs/validacion`, `tools/validation/consolidate.py` |
| M-13 to M-15 SPI, CPI, change discipline | Microsoft Project and change log | outside the repository; change requests in `architecture/registro-de-decisiones.md` |
