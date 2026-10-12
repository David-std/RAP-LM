# Raster Analytics Web

Web application for spatiotemporal analysis of pedestrian collision risk in Metropolitan Lima.

## Overview

The system combines a geospatial web interface, an API for risk queries, and a reproducible data pipeline for profiling and preparing source datasets.

```text
Official source snapshots
    |
    v
Offline preparation -> CNN-LSTM evaluation
    |                        |
    |                   Versioned artifacts
    v
Approved batch publication
    |
    v
PostgreSQL + PostGIS
    |
    v
Read-only FastAPI
    |
    v
React + TypeScript + Leaflet
```

The planned product supports polygon-based risk exploration by period, unit details, spatial/temporal comparison, and provenance. A model is trained and evaluated offline; requests read only **approved, published** results. The current frontend/API remain a synthetic-data integration prototype while that architecture is implemented.

The latest integrated implementation specification is [Architecture](docs/architecture/architecture.md). Its analytical outcome and exposure release gates are still open; current fatal-only source records are not general pedestrian-collision risk evidence.

## Repository structure

```text
apps/api        FastAPI backend
apps/web        React + TypeScript frontend
pipelines       Data ingestion, profiling, and processing utilities
data            Source registry and data documentation
docs            Product and architecture documentation
```

## Run the API

Requirements: Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn raster_api.main:app --app-dir apps/api/src --reload
```

Current **prototype-only** endpoints (not the final v1.5 read API):

- `GET /health`
- `GET /model/metadata`
- `GET /metadata/spatial-units`
- `GET /metadata/periods`
- `GET /risk?spatial_unit=...&period=...`
- `GET /risk/map?period=...`
- `POST /risk/compare`

## Run the web application

With the API available at `http://localhost:8000`:

```bash
cd apps/web
npm install
npm run dev
```

The application is served at `http://localhost:5173` by default.

## Data

Official source workbooks are registered under `data/sources/`. To download the primary ONSV crash/person sources and build the normalized Metropolitan Lima pedestrian fatal-crash table:

```bash
python -m pipelines.ingestion.onsv sync
python -m pipelines.processing.onsv
```

Raw files and generated datasets remain outside version control.

## Quality checks

Backend and pipelines:

```bash
ruff check .
pytest
```

Frontend:

```bash
cd apps/web
npm run typecheck
npm run build
```

## Product and architecture documentation

- `docs/product-development-specification.md` defines the evidence-driven data, ML, architecture, UX, validation, and implementation gates.
- `docs/architecture/architecture.md` is the v1.5 architecture entry point and links the C4 implementation, API, PostGIS publication, ML protocol and controlled migration contracts.
