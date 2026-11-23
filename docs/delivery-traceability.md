# Delivery traceability and verification status

**Baseline:** integrated project plan v1.6 (§3.11 Figures 5A to 5E, §4.2.1 WBS dictionary, §8.1 Tables 34 to 36).
**Reading rule:** *Implemented* means the code exists and its automated tests pass; *Measured* means the metric
was computed against the running stack and its JSON is in `evidence/`; *Accepted* is a team decision recorded
outside the repository (Sprint Review, change control). Measured values are in
[CONTROL_DESARROLLO.md](CONTROL_DESARROLLO.md).

## WBS packages

| WBS | Deliverable | Repository evidence | Status |
|---|---|---|---|
| 3.1.1 | Source profiling | `docs/data/source-qualification.md`, `data/catalog/provenance.json`, `pipelines/profiling` | Implemented |
| 3.1.2 | Benchmarking of modelling alternatives | `ml/fused/train.py`, `ml/fused/search.py`, `docs/ml/benchmark-protocol*.md`, `docs/benchmarking/BENCHMARKING.md` | Implemented, measured |
| 3.1.3 | Logical and physical architecture, API contract | `compose.yaml`, `docs/api/contract.md`, design history in `docs/architecture/` | Implemented |
| 3.1.4 | Spatial and temporal data model | `database/migrations` (0001 to 0003) | Implemented |
| 3.1.5 | Navigable prototype | Claude Design prototype (PR-01, PR-02), ported to `apps/web` | Implemented |
| 3.2.1 | Versioned analytical dataset | `pipelines/fusion`, dataset manifests with SHA-256, `evidence/reproducibility/dataset.json` | Implemented, reproduced |
| 3.2.2 | CNN component | `ml/fused/model.py`, tests `test_model_output_shape`, `test_cnn_uses_spatial_neighbourhood` | Implemented |
| 3.2.3 | RNN component | `ml/fused/model.py`, test `test_recurrence_never_reads_the_future` | Implemented |
| 3.3.1 | Read API | `apps/api`, contract tests against PostGIS | Implemented |
| 3.3.2 | Spatial database | PostGIS, GiST indexes, separated roles | Implemented |
| 3.3.3 | Web interface | `apps/web` (map, corridors, comparators, analysis, model, methodology) | Implemented |
| 3.4.1 to 3.4.3 | Integration and critical flows | Playwright journeys `apps/web/e2e` | Implemented, measured (M-07) |
| 3.4.4 | Model outputs stored and served unchanged | `pipelines/publication` reconciliation, M-08 | Implemented, measured |
| 4.3 | Verification | `docs/pruebas/plan_de_pruebas.md`, pytest, Vitest, Playwright, `tools/metrics` | Measured |
| 4.4 | Technical evaluation against the historical average | `evidence/benchmarking`, M-05 and high-level errors | Measured |
| 4.5 | Validation with at least five specialists | Instruments in `docs/validacion`, consolidation `tools/validation` | Instruments ready; sessions run by the team |
| 5.1 to 5.3 | Manual, closure, clean installation | `docs/manual_usuario.md`, `README.md` | Implemented |

## Quality metrics (Table 35)

| Metric | Measured by | Evidence |
|---|---|---|
| M-01 Spatial correspondence | `tools/metrics/measure.py` | `evidence/metrics/M-01.json` |
| M-02 Result completeness | same | `evidence/metrics/M-02.json` |
| M-03 Source and version traceability | same | `evidence/metrics/M-03.json` |
| M-04 Pipeline reproducibility | rerun of the published configuration | `evidence/metrics/M-04.json` |
| M-05 Improvement over the historical average | frozen test evaluation | `evidence/metrics/M-05.json`, `evidence/benchmarking/` |
| M-06 Mandatory RF accepted | test plan per requirement | `docs/pruebas/plan_de_pruebas.md`; acceptance by the Product Owner |
| M-07 Critical end-to-end scenarios | Playwright | `evidence/e2e/results.json` |
| M-08 Query, filter and comparison correctness | API vs exported results | `evidence/metrics/M-08.json` |
| M-09 API p95 latency | sequential load | `evidence/metrics/M-09.json` |
| M-10 to M-12 Specialist success, time, interpretation | specialist sessions | `docs/validacion`, `tools/validation/consolidate.py` |
| M-13 to M-15 SPI, CPI, change discipline | Microsoft Project and change log | outside the repository; change requests in `DECISIONES_TECNICAS.md` |
