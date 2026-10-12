# Architecture

This page is the canonical **entry point** to the implementation specifications, aligned with the integrated project plan **v1.5**, §3.11, Figures 5A–5E and Table 14A. The v1.5 plan supersedes earlier prototype-oriented architecture notes. Project Charter v1.2 remains background, not the current architecture authority.

## System architecture

The product is a **modular, layered analytical web application** with a separately executed, offline **batch pipeline**. It is deliberately not microservices, online learning or request-time CNN/RNN inference.

\`\`\`text
Official/public source portals          Project operator
                |                               |
                v                               v
        Batch analytical pipeline (Python, GeoPandas, PyTorch)
        acquire -> profile -> spatial/temporal features
        -> raster tensors -> CNN + LSTM -> benchmark -> approve
                |                               |
                v                               v
     Versioned artifacts                 Batch publisher
        (Git/manifests,                         |
       data/weights, hashes)                    v
                                        PostgreSQL + PostGIS
                                        published run + provenance
                                                |
                                                v
                                     Read-only FastAPI application
                                     Pydantic -> services -> SQL repos
                                                |
                                                v
                                     React + TypeScript + Leaflet
                                     Nginx SPA, shared query state
                                     map/detail/compare/provenance
\`\`\`

The basemap is an external visualization service and does not supply authoritative risk observations. The API never trains or runs the CNN–LSTM on a web request. It returns only approved published results, or an explicit unavailable state.

## Component contract index

| Subject | Canonical documentation |
|---|---|
| C4 system context, containers, web, API, eight pipeline stages and module ownership | [Implementation blueprint](implementation-blueprint.md) |
| Committed vs proposed vs gated choices, figure/requirement/WBS mapping | [Decision register](decision-register.md) |
| Exact five read-only product resources and JSON/GeoJSON response semantics | [Read API contract](../contracts/read-api.md) |
| PostGIS entities, area/district relation, versioning, permission roles, staged and atomic publication | [Persistence & publication](../contracts/persistence-and-publication.md) |
| Target/outcome population, exposure, severity, tensor shapes, leakage, baseline, metrics and thresholds | [Analytical ML protocol](../ml/analytical-protocol.md) |
| Incremental migration from the existing RiskProvider/mock API | [Migration plan](migration-plan.md) |
| Empirical candidate/data qualification before final target/model freeze | [Feature/target contract](../data/feature-target-contract.md), [source qualification](../data/source-qualification.md), [representation experiments](../data/representation-experiments.md) |
| Broader product requirements, controls, specialist UX, acceptance and risk | [Product development specification](../product-development-specification.md) |

## Established design versus unresolved evidence

Established by v1.5: 43 districts of Lima Province excluding Callao; React/TS/Leaflet + Nginx; read-only FastAPI/Pydantic with SQLAlchemy/GeoAlchemy2; PostGIS; offline Pandas/GeoPandas/PyTorch pipeline; CNN spatial plus LSTM temporal reference; raster-to-district presentation; model artifacts with run IDs; relative indicator with low/medium/high levels; five GET resources; RF-01–RF-08 specialist workflows.

**Not established yet:** valid general pedestrian-collision outcome coverage, direct exposure denominator, severity across fatal/non-fatal events, selected grid resolution/period/window, complete feature/target formula, calibrated level thresholds, benchmark superiority, defensible district aggregation and publishable run. Do not turn documented proposals into empirical facts.

## Existing repository transition warning

The current \`apps/api/src/raster_api/main.py\` calls \`RiskProvider.predict()\` per request and uses legacy endpoints. This is a **prototype seam**, not the architecture approved in v1.5. Preserve existing P1/P2/P3 audits while migrating to a separate batch publisher and PostGIS read-only API; do not remove gates or silently expose synthetic data. Migration slices are defined in [migration-plan.md](migration-plan.md).

Any implementation PR must cite at least one ADR, Figure 5 component, requirement ID and WBS work package, with tests and a versioned evidence link. Do not change integrated-plan scope without documented change control.
