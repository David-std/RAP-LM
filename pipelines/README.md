# Batch pipelines

Offline stages of Figure 5E. No module here serves user requests; the API only reads what
`publication` writes to PostGIS.

```text
source snapshots -> spatial (grid) -> fusion (geocoding, events, context, corridors) -> ml/fused -> publication
```

## Current stages

| Package | Purpose | Entry point |
|---|---|---|
| `spatial` | 1 km grid in EPSG:32718 clipped to the 43 districts, cell-district area shares | used by `fusion` |
| `fusion` | Fused all-severity pedestrian collisions (CENACOM 2011-2017, ONSV 2021-2024), rule-based street geocoding with OSM, context variables (MINAM, WorldPop, OSM), subtype and severity, dataset manifest with SHA-256 | `python -m pipelines.fusion --raw <RAP-LM-DATA> --harmonized <harmonized_crash_events.csv> --out artifacts/datasets/fused-v1.1.0` |
| `fusion.corridors` | Street corridors with recorded collisions and concentration curve | `python -m pipelines.fusion.corridors --dataset ... --harmonized ... --boundary ... --results ...` |
| `publication` | Atomic publication of a run (reconciliation, active pointer) and of its analyst layers | `python -m pipelines.publication.publisher ...`, `python -m pipelines.publication.extras ...` |
| `lineage.py` | Code commit and working-tree state recorded in every manifest | imported |

## Research stages (P1 to P3)

`ingestion`, `processing`, `profiling`, `representation` and `features` produced the source qualification,
representation and feature-coverage evidence documented in `docs/data/`. They are kept with their tests and
the manual workflows in `.github/workflows/` (source, representation and feature-coverage audits).

Raw snapshots and generated artifacts stay out of Git (`artifacts/`, local data directory).
