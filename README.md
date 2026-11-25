# RAP-LM

Web application based on CNN-RNN neural networks for the spatiotemporal analysis of **pedestrian
collision risk** (all severities) in the 43 districts of the province of Lima (Callao excluded).
Academic project SI727, UPC, Group 06.

Specialists can query, filter, compare and export a relative risk index per 1 km cell, district and street
corridor, per period (year × day type × 6-hour band), with three components (frequency, expected severity and
exposure-adjusted ratio), its level (low, medium, high), the historical record by subtype and severity, an
explanation of how the network reached it and its provenance, plus annual forecasts for 2025–2027. The recurrent part of the network is an LSTM, the RNN
type with long-term memory; the published model is a ConvLSTM (LSTM with convolutional gates). It is an
analytical reference: no real-time prediction and no intervention recommendations.

![Mapa de riesgo de RAP-LM](evidence/screenshots/01-mapa.png)

## What it offers

- **Risk map** of the 43 districts by 1 km cell, district or continuous heat surface, with filters by level,
  district, year, day type and 6-hour band.
- **Zone panel**: risk index with its value, expected severity, ratio to the urban context, year-by-year network
  estimate, historical record (subtype, severity, vehicle, transport service, recorded factors) and environment
  profile against the rest of Lima.
- **Forecast** for 2025–2027, recursively projected from 2024, with ensemble disagreement and a separate one-year out-of-sample check.
- **Critical streets** ranked by a smoothed collision rate, with vehicles and recorded factors per street.
- **Explainability**: Grad-CAM map, variable-group attribution and context what-if.
- **Model view** documented as a technical report: architecture, training, out-of-sample evaluation, multi-year
  horizons, ablation and references, with the repository file behind every table.

| Zone detail | Forecast | Critical streets |
|---|---|---|
| ![Detalle de zona](evidence/screenshots/02-detalle-zona.png) | ![Pronóstico](evidence/screenshots/04-pronostico.png) | ![Vías críticas](evidence/screenshots/05-vias-criticas.png) |

## Architecture at a glance

```text
Public sources (CENACOM 2011-2017, ONSV 2021-2024, INEI, WorldPop, MINAM, OSM)
   │  pipelines/fusion      grid 1 km (EPSG:32718), rule-based street geocoding, context
   ▼
fused dataset  ── ml/fused ──►  CNN-RNN variants (ConvLSTM, CNN-LSTM) vs Poisson GLM, ablations, historical average
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
H=$D/harmonized/RAP-LM-HARMONIZED/data/harmonized_crash_events.csv
# 1. Fused dataset v1.4 (grid, street geocoding, annual population, context, vehicle, service and recorded
#    factors; events known only by the police station district stay at district level). Manifest with SHA-256.
python -m pipelines.fusion --raw $D/raw/RAP-LM-DATA --harmonized $H --out artifacts/datasets/fused-v1.4.0
python -m pipelines.fusion --raw $D/raw/RAP-LM-DATA --harmonized $H --station-proxy exclude \
  --out artifacts/datasets/fused-v1.4.0-exclude-station                              # sensitivity arm
# 2. v5 (published, D-18): v4 architecture retrained on every observed year, fixed 150 epochs, on the GPU.
#    Out-of-sample evidence: ml/experiments/v10.py and docs/ml/performance-v10.md
R=artifacts/runs/fused-cnnlstm-2026.11-v5
python -m ml.fused.search --dataset artifacts/datasets/fused-v1.4.0 --config ml/configs/v5-final.json --out $R
python -m ml.experiments.evaluation_card --out $R/evaluation.json
#    v4 benchmark arms (kept as history): all-severity backtest and station sensitivity
python -m ml.fused.search --dataset artifacts/datasets/fused-v1.4.0 --config ml/configs/v4-backtest-2017.json \
  --out artifacts/runs/fused-cnnlstm-backtest-2017-v4
python -m ml.fused.search --dataset artifacts/datasets/fused-v1.4.0-exclude-station \
  --config ml/configs/v4-sens-exclude-station.json --out artifacts/runs/fused-cnnlstm-2026.11-v4-exclude-station
# 3. Export, explanations and Grad-CAM (forward passes on the GPU), forecast, street corridors
python -m ml.fused.export --dataset artifacts/datasets/fused-v1.4.0 --run $R
python -m ml.fused.explain --dataset artifacts/datasets/fused-v1.4.0 --run $R --device cuda
python -m ml.fused.saliency --dataset artifacts/datasets/fused-v1.4.0 --run $R --device cuda
python -m ml.fused.forecast --dataset artifacts/datasets/fused-v1.4.0 --run $R --steps 3
python -m ml.fused.card_refresh --run $R --evaluation $R/evaluation.json
python -m pipelines.fusion.corridors --dataset artifacts/datasets/fused-v1.4.0 --harmonized $H \
  --boundary $D/raw/RAP-LM-DATA/geography/boundaries/lima_43_districts_inei.geojson --results $R/results.csv
# 4. Publish into PostGIS with the publisher role (atomic), then the analyst layers
export RAPLM_PUBLISHER_URL=postgresql://raplm_publisher:raplm_publisher_dev@127.0.0.1:5433/raplm
python -m pipelines.publication.publisher --dataset artifacts/datasets/fused-v1.4.0 --run $R
python -m pipelines.publication.extras --dataset artifacts/datasets/fused-v1.4.0 --run $R
# 5. Reproducibility (M-04): retrain into a new folder on the same device and compare
python -m ml.fused.search --dataset artifacts/datasets/fused-v1.4.0 --config ml/configs/v5-final.json \
  --out artifacts/runs/fused-cnnlstm-2026.11-v5-repro
```

Earlier iterations (v1 on dataset v1.0, v2 on v1.1, v3 on v1.2 and v1.3, v4 on v1.4) keep their configs in `ml/configs/`
and their evidence in `evidence/benchmarking/`.

The same steps run inside the batch container: `docker compose --profile batch run --rm pipeline ...`.

### Training on the GPU

The code trains on CPU (8 threads, about 33 minutes per iteration) or, when the run config sets
`"device": "cuda"`, on an NVIDIA GPU (about 5 minutes). A repeated GPU run reproduced weights and estimates byte
for byte, so the published model trains on the GPU and M-04 is measured by retraining there. Prediction and export
run on CPU; explanations and Grad-CAM accept `--device cuda`. Install the CUDA
environment from `requirements-gpu.txt` (outside the repository) and run the same commands with its interpreter.
Each run manifest records the device type (`cpu` or `cuda`), the PyTorch version and the training time.

## Cloud demonstration (Render)

`render.yaml` describes the demo deployment: managed PostgreSQL with PostGIS, the read-only API container
and the SPA as a static site. Web and API redeploy on every push to `main`; data changes only through a
publication.

1. Render > New > Blueprint, select this repository: it creates `raplm-db`, `raplm-api` and `raplm-web`.
2. Load the database from a machine with the artifacts, using the external URL of `raplm-db`:

   ```bash
   RAPLM_REMOTE_OWNER_URL="<external URL of raplm-db>" python -m tools.deploy.remote_setup \
     --dataset artifacts/datasets/fused-v1.4.0 --run artifacts/runs/fused-cnnlstm-2026.11-v5
   ```

   It creates the reader and publisher roles, applies the migrations and publishes the run.
3. Set `DATABASE_URL` of `raplm-api` to the read-only URL the script prints, and redeploy the API.

On the free plan the API sleeps after 15 minutes without traffic (first request takes about a minute) and
the database expires after 30 days; open the site a few minutes before a session.

## Tests and quality metrics

```bash
docker compose up -d db
RAPLM_TEST_ADMIN_URL=postgresql://raplm_owner:raplm_owner_dev@127.0.0.1:5433/raplm pytest   # unit + PostGIS contract
ruff check .
cd apps/web && npm test && npm run typecheck && npm run build
python -m tools.metrics.measure --api http://127.0.0.1:8088 --dataset artifacts/datasets/fused-v1.4.0 \
  --run artifacts/runs/fused-cnnlstm-2026.11-v5 --rerun artifacts/runs/fused-cnnlstm-2026.11-v5-repro \
  --harmonized $H --out evidence/metrics                                                    # M-01..M-05, M-08, M-09
cd apps/web && npx playwright test                                                          # M-07, 12 journeys
python -m tools.reports.test_report && python -m tools.reports.benchmark                    # docs/pruebas, docs/benchmarking
```

## Repository map

| Path | Content |
|---|---|
| `pipelines/spatial`, `pipelines/fusion` | Grid, OSM street index, geocoding rules, event fusion, context (HT-05, HT-06) |
| `ml/fused` | Tensors, CNN-RNN variants (ConvLSTM, CNN-LSTM) and benchmark models, training, export, explanations, Grad-CAM, forecast (HT-02, HT-07, HT-08) |
| `pipelines/publication` | Atomic publisher with reconciliation (HT-11) |
| `database` | Alembic migrations and DB roles (HT-04, HT-10) |
| `apps/api` | Read-only FastAPI v1 (HT-09) and tests |
| `apps/web` | React + TypeScript + Leaflet SPA (EP-01..EP-05) |
| `tools/metrics`, `tools/validation`, `tools/reports` | Metric measurement, specialist-validation consolidation, benchmark, test and CPU/GPU reports |
| `tools/deploy`, `render.yaml` | Cloud demonstration: managed database loading and Render blueprint (D-13) |
| `requirements-gpu.txt` | Optional CUDA training environment |
| `data/catalog` | Provenance catalog (sources, variables, limitations) |
| `docs/` | Architecture document and C4 diagrams, decision and incident registers, API contract, ML protocol, test plan and report, user manual, validation |
| `evidence/` | Measured metric and benchmark reports |

Documentation index: [docs/README.md](docs/README.md).

## Branches and pull requests

Git Flow: `main` holds released versions, `develop` integrates finished work. Each unit of work lives in its own
branch created from `develop` and returns to it through a reviewed pull request:

| Prefix | Use | Example |
|---|---|---|
| `feature/` | New functionality or analysis | `feature/forecast-view` |
| `fix/` | Defect found in `develop` | `fix/period-order` |
| `docs/` | Documentation only | `docs/architecture-c4` |
| `refactor/` | Internal change without new behaviour | `refactor/api-repository` |
| `release/` | Stabilisation before merging into `main`; named by version only, tagged on `main` | `release/v1.0.0` (tag `v1.0.0`) |
| `hotfix/` | Urgent fix on `main` | `hotfix/ci-import-order` |

Names are lowercase kebab-case. Commits follow Conventional Commits and cite the requirement codes they address
(for example `feat(web): HU-10 continuous heat view`). Merged branches are kept as project traceability, together
with `develop` and `main`.

