# RAP-LM

Web application based on neural networks (CNN-LSTM) for the spatiotemporal analysis of **pedestrian
collision risk** (all severities) in the 43 districts of the province of Lima (Callao excluded).
Academic project SI727, UPC, Group 06. Baseline: integrated project plan v1.6.

Specialists can query, filter, compare and export a relative risk index per 1 km cell, district and street
corridor, per period (year × day type × 6-hour band), with three components (frequency, expected severity and
exposure-adjusted ratio), its level (low, medium, high), the historical record by subtype and severity, an
explanation of how the network reached it and its provenance. It is an analytical reference: no real-time prediction and no intervention recommendations.

```text
Public sources (CENACOM 2011-2017, ONSV 2021-2024, INEI, WorldPop, MINAM, OSM)
   │  pipelines/fusion      grid 1 km (EPSG:32718), rule-based street geocoding, context
   ▼
fused dataset  ── ml/fused ──►  CNN-LSTM vs ConvLSTM, Poisson GLM, ablations, historical average
   │                               (chronological split, frozen protocol)
   ▼  pipelines/publication   one transaction, reconciliation, atomic pointer
PostgreSQL + PostGIS  ──►  read-only FastAPI /api/v1  ──►  React + TypeScript + Leaflet (Nginx)
```

## Run the application (Docker Compose)

Requirements: Docker with Compose v2.

```bash
docker compose up -d --build          # db, migrate (one-shot), api, web
open http://localhost:8088             # web; API docs at http://localhost:8000/docs
```

Without a published run the API answers `503 NO_PUBLISHED_RUN` and the web says so: no demo data is shown
in its place. To publish a run, see the next section.

## Reproduce the data, the model and the publication

The source snapshots are not in Git (size and licence review). Obtain the capture
`RAP-LM-DATA-2026-11-17-v2.zip` and the harmonized `RAP-LM-HARMONIZED-2026-11-17-v0.2.0.zip`
(SHA-256 in `docs/data/` and the handoff manifest) and extract them, e.g. under `../RAP-LM-DATA-LOCAL/raw` and
`../RAP-LM-DATA-LOCAL/harmonized`.

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows; use bin/activate elsewhere
pip install -e ".[dev,pipeline]"                    # torch CPU: --index-url https://download.pytorch.org/whl/cpu

D=../RAP-LM-DATA-LOCAL
# 1. Fused dataset (grid, geocoding, context, manifest with SHA-256)
python -m pipelines.fusion --raw $D/raw/RAP-LM-DATA \
  --harmonized $D/harmonized/RAP-LM-HARMONIZED/data/harmonized_crash_events.csv \
  --out artifacts/datasets/fused-v1.1.0
# 2. v1 benchmark of all architectures (CNN-LSTM, ConvLSTM, Poisson GLM, ablations) on dataset v1.0
python -m ml.fused.train --dataset artifacts/datasets/fused-v1.0.0   --config ml/configs/run-main.json --out artifacts/runs/fused-cnnlstm-2026.11-r1
# 3. v2 (published): validation search, 5-seed ensemble, single test evaluation, high-level errors
R=artifacts/runs/fused-cnnlstm-2026.11-v2
python -m ml.fused.search --dataset artifacts/datasets/fused-v1.1.0 --config ml/configs/v2-main.json --out $R
python -m ml.fused.classification --dataset artifacts/datasets/fused-v1.1.0 --run $R
# 4. Export results (frequency, severity, exposure, breakdown) and explanations
python -m ml.fused.export --dataset artifacts/datasets/fused-v1.1.0 --run $R
python -m ml.fused.explain --dataset artifacts/datasets/fused-v1.1.0 --run $R
python -m pipelines.fusion.corridors --dataset artifacts/datasets/fused-v1.1.0   --harmonized $D/harmonized/RAP-LM-HARMONIZED/data/harmonized_crash_events.csv   --boundary $D/raw/RAP-LM-DATA/geography/boundaries/lima_43_districts_inei.geojson --results $R/results.csv
# 5. Publish into PostGIS with the publisher role (atomic), then the analyst layers
export RAPLM_PUBLISHER_URL=postgresql://raplm_publisher:raplm_publisher_dev@127.0.0.1:5433/raplm
python -m pipelines.publication.publisher --dataset artifacts/datasets/fused-v1.1.0 --run $R
python -m pipelines.publication.extras --dataset artifacts/datasets/fused-v1.1.0 --run $R
```

The same steps run inside the batch container: `docker compose --profile batch run --rm pipeline ...`.

## Tests and quality metrics

```bash
docker compose up -d db
RAPLM_TEST_ADMIN_URL=postgresql://raplm_owner:raplm_owner_dev@127.0.0.1:5433/raplm pytest   # unit + PostGIS contract
ruff check .
cd apps/web && npm test && npm run typecheck && npm run build
python -m tools.metrics.measure --dataset artifacts/datasets/fused-v1.1.0 \
  --run artifacts/runs/fused-cnnlstm-2026.11-v2 --out evidence/metrics                    # M-01..M-05, M-08, M-09
```

## Repository map

| Path | Content |
|---|---|
| `pipelines/spatial`, `pipelines/fusion` | Grid, OSM street index, geocoding rules, event fusion, context (HT-05, HT-06) |
| `ml/fused` | Tensors, CNN-LSTM and benchmark models, training/evaluation, export (HT-02, HT-07, HT-08) |
| `pipelines/publication` | Atomic publisher with reconciliation (HT-11) |
| `database` | Alembic migrations and DB roles (HT-04, HT-10) |
| `apps/api` | Read-only FastAPI v1 (HT-09) and tests |
| `apps/web` | React + TypeScript + Leaflet SPA (EP-01..EP-05) |
| `tools/metrics`, `tools/validation`, `tools/reports` | Metric measurement, specialist-validation consolidation, benchmark report |
| `data/catalog` | Provenance catalog (sources, variables, limitations) |
| `docs/` | Architecture, API contract, ML protocol, decisions, control log, user manual, validation |
| `evidence/` | Measured metric and benchmark reports |

Documentation index: [docs/README.md](docs/README.md).
