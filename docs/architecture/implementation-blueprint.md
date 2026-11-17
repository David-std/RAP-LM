# Implementation architecture — integrated plan v1.5

**Status:** implementation specification; architectural commitments are binding, analytical parameters remain gated.  
**Authoritative project baseline:** *TP_ImpPlanProyecto_GerPry_Grupo06_202602*, v1.5, §3.11, Figures 5A–5E, Table 14A, requirements traceability, WBS dictionary.  
**Prior baseline:** Project Charter v1.2 remains historical context; it does not supersede the integrated v1.5 plan.  
**Scope:** 43 districts of Lima Province; Callao excluded. A specialist-facing analytical MVP, not emergency dispatch, live surveillance, a forecasting alert system, or a city decision engine.

## 1. Normative hierarchy and controlled decisions

1. The approved integrated plan v1.5 and its traceability matrix/WBS govern product scope and committed technical architecture.
2. This blueprint translates Figures 5A–5E into development responsibilities without silently altering the plan.
3. The data and ML evidence files determine empirical feasibility, target semantics, hyperparameters and publication eligibility.
4. An implementation convenience or existing prototype is never authority to weaken a requirement.
5. A change to general pedestrian-collision risk versus fatal-only risk, available functions, geography or acceptance criteria requires project change control; not merely a code review.

Classify every technical choice as **COMMITTED** (plan-defined), **PROPOSED IMPLEMENTATION** (replaceable internal engineering choice) or **GATED** (requires profiled evidence/review). The decision log is in [decision-register.md](decision-register.md).

## 2. C4 Level 1 — system context (Figure 5A)

- **Specialist user:** uses a browser to identify and compare relative risk by spatial unit/period and read provenance; cannot trigger training or publication.
- **Project analyst/operator:** runs offline source acquisition, profiling, model evaluation and controlled publication. This is an operational role, not a public web authoring role.
- **Official/public data portals:** external origins of source records; the pipeline records URL, publisher, access time, licence, date coverage and checksum; portals are not runtime dependencies of map consultations.
- **External map-tile provider:** supplies visual basemap only, not authoritative analytical geometry or risk data.
- **Raster Analytics Web:** analytical product boundary. No person/vehicle recognition, no real-time sensors, no automated intervention.

## 3. C4 Level 2 — containers (Figure 5B)

| Logical container | Technology commitment | Sole responsibility | Forbidden coupling |
|---|---|---|---|
| Web SPA | React, TypeScript, Leaflet, delivered by Nginx | Specialist workflows, filters, map/legend, comparison, detail, provenance | No risk computation, SQL, Python or model loading |
| Read-only API | FastAPI, Pydantic, SQLAlchemy, GeoAlchemy2 | Validate read queries; apply application rules; access approved published results | No training, inference, data ingestion or public write route |
| Spatial database | PostgreSQL + PostGIS | Store unit geometries, periods, published run outputs and provenance relations | No business logic implemented as arbitrary frontend SQL |
| Analytical batch pipeline | Python, Pandas/GeoPandas, PyTorch, scikit-learn | Acquire, qualify, transform, build tensors, train/evaluate, publish approved run | No end-user request handler or unapproved publication |
| Artifact repository (logical) | Git + versioned artifact storage | Source/config manifest, dataset version, weights, metrics, environment fingerprint | Do not imply that Git or a directory must be an independently running Docker container |

**Deployment interpretation:** Docker Compose starts actual processes/services (Nginx/web, FastAPI, PostgreSQL/PostGIS and a profile or one-shot batch worker). Versioned storage is a logical container in C4; it may be backed by a persisted volume or external object store rather than a continuously running service. Use pinned images/dependencies and distinct runtime profiles. Never commit secrets, raw private data or large model weights by default.

**Runtime invariant:** \`GET /riesgo\` performs database reads of an already published and approved run. It never invokes \`model.forward()\` or \`RiskProvider.predict()\`.

## 4. C4 Level 3 — web components (Figure 5C)

- **Map & legend (RF-01/RF-07, WBS 3.3.3):** draw authoritative unit geometries, categorical/continuous visual encoding, legends, selected period, selection and missing-data distinction. Do not infer risk from basemap appearance.
- **Details, period & filters (RF-02–RF-04):** select one unit and supported period, show exact indicator, level, source/run/period, available contextual variables and limitations. No client recomputation of scores.
- **Comparators (RF-05/RF-06):** compare two units for one period AND one unit across two periods. Validate scale compatibility and make noncomparability explicit.
- **Provenance (RF-08):** explain source versions, variable definitions, coverage, modeling limitations, run ID, benchmark status and classification method. Accessible from an individual result, not buried in documentation.
- **Shared query state (React Context):** owns \`activePeriodId\`, \`selectedUnitIds\`, \`filters\`, \`comparisonMode\`, \`comparisonPeriods\`, and active published run; one period change invalidates/refetches all dependent views.
- **Typed API client:** sole HTTP boundary, typed DTO validation, cancellation/obsolete-request handling, loading/empty/error states, and standard error representation. UI does not call arbitrary fetches scattered across components.

Usability constraints: stable selection and keyboard access, clear map legend not reliant on color alone, progressive loading/empty states, consistent terminology, source/fatal-scope notice where applicable, WCAG 2.2 AA review. Basemap attribution remains visible.

## 5. C4 Level 3 — API components (Figure 5D)

- **Routers** expose exactly five MVP read resources in the plan: \`GET /periodos\`, \`GET /unidades\`, \`GET /riesgo\`, \`GET /comparaciones\`, \`GET /procedencia\`. Operational \`/health\` is acceptable but is not a product resource. No public POST or mutation route.
- **Pydantic contracts** validate IDs, comparison modes, limits and filters and serialize JSON/GeoJSON with consistent errors.
- **Application services** resolve publication snapshot and authorize compatible comparisons, available periods and provenance.
- **Repository interfaces** isolate SQLAlchemy/GeoAlchemy2 queries, load geometries/results, avoid N+1, and parameterize every query. No model imports in these layers.
- **PostGIS** is the query source of truth after publication. Read-only DB credentials are distinct from the batch publication credentials.
- Details of payloads, status codes, sorting and consistency belong to [read-api.md](../contracts/read-api.md).

## 6. C4 Level 3 — ordered analytical pipeline (Figure 5E)

Each numbered stage is resumable from immutable/versioned inputs, produces a manifest, writes a checksum, logs row/geometry counts and fails on unresolved contract violations.

1. **Acquisition and registration:** official source identifiers, URL/version, time, licence, consent/access constraints, file SHA-256; download idempotently; preserve source bytes.
2. **Profiling and quality:** schema, row counts, duplicates, date/time coverage, missingness, coordinate plausibility, spatial coverage, severity and outcome semantics. Quarantine rejected rows with reasons rather than silently dropping.
3. **Spatial transformation:** verify origin CRS, reproject to one analysis CRS, clip to 43 districts, assign events/context to a regular grid and districts; measure assignment loss, invalid polygons and topology defects. A zoning mask indicates structural support, NOT pedestrian exposure.
4. **Temporal transformation:** explicit timezone/date conventions, time windows and bucket boundaries; align all sources by availability dates, not just event date; prohibit forward-looking features.
5. **Tensor construction:** preserve spatial raster adjacency and temporal sequence. Use observation/missingness masks; record order of cells, channels and periods plus normalization fitted on training only.
6. **Training CNN–LSTM:** spatial CNN applied per time slice; LSTM over ordered representations; output a result for every supported cell-period without collapsing position into one unlocatable global embedding. Record model shape and hyperparameters.
7. **Evaluation:** chronological train/validation/independent test; historical-average comparator defined on the **same target and scale**; compare metrics, error, FP/FN for levels and computational cost; no test-driven threshold tuning.
8. **Publication:** require approved benchmark + validated schemas + lineage, store run metadata and spatial outputs transactionally, and make one new run active only after reconciliation. A failed publication must not disturb currently published results.

A notebook is exploration evidence, not a substitute for reproducible modules/CLI and artifacts.

## 7. Architecture interfaces and invariants

\`\`\`text
Official snapshots -> validated normalized events -> spatial-temporal feature set
       -> dataset + split/tensor manifest -> baseline / CNN-LSTM evaluations
       -> approved, versioned run -> transactional publisher -> PostGIS
       -> read repository -> application service -> FastAPI -> typed client -> UI
\`\`\`

- Both the baseline and CNN-LSTM see identical target population, split, support mask, eligible features and test period.
- The \`RiskProvider\` protocol is a **legacy prototype seam**. It may remain for isolated test fixtures while migration occurs, but it must not remain the authoritative production request path.
- All published values must carry \`run_id\`, \`dataset_version\`, \`target_definition_id\`, \`representation_id\`, \`period_id\`, and semantic \`value_unit\`.
- A district summary is generated with a documented target-compatible aggregation rule, never an arithmetic average of ordinal labels.
- No synthetic/mock values are published as validated outcomes, even if used for API/UI contract testing.
- Only approved \`published\` runs are visible to the API, and a response must be consistent with exactly one \`run_id\` during a request.

## 8. Implementation responsibility map

| Responsibility | Proposed location | Design/EDT trace |
|---|---|---|
| Source acquisition, quality, spatial/temporal processing | \`pipelines/\` | 5E stages 1–4; RD-01–RD-06, RG-01; WBS 3.1.1/3.2.1 |
| Raster tensorization, baseline, CNN-LSTM, evaluation | \`ml/\` | 5E stages 5–7; RM-01–RM-05; WBS 3.1.2/3.2.2/3.2.3/4.4 |
| Run artifacts and batch publisher | \`ml/artifacts/\`, \`pipelines/publication/\` (proposed) | 5E stage 8; WBS 3.4.4 |
| DB schema/indices and query repositories | \`database/\`, \`apps/api/\` | 5B/5D; RT-03; WBS 3.1.4/3.3.2 |
| Read-only route/service/contracts | \`apps/api/\` | 5D; RT-02; WBS 3.3.1/3.4.2 |
| Analytical workspace | \`apps/web/\` | 5C; RF-01–RF-08; WBS 3.3.3/3.4.3/4.5 |
| Compose/environment and integration tests | \`infra/\`, \`tests/\` | 5B; RNF-02; WBS 3.4/4.3 |

Paths are proposed implementation packaging, not a requirement to create extra distributed services.

## 9. Deferred choices and approval boundaries

The v1.5 plan commits a grid-based CNN–LSTM **reference architecture** and low/medium/high presentation levels; it does **not** supply a justified grid size, temporal stride/window, target formula, direct exposure denominator, model hyperparameters or validated thresholds. Those must be resolved in an evidence-bearing benchmark decision record.

The source currently profiled in the repository is fatal-only ONSV, not complete pedestrian collisions. Full-scope publication is blocked until an adequate source and risk formulation exist or an approved scope change is recorded. Exploratory fatal-event benchmarking is allowed with explicit high-severity labels and cannot be promoted by hiding its target semantics.

See [analytical-protocol.md](../ml/analytical-protocol.md), [persistence-and-publication.md](../contracts/persistence-and-publication.md) and [migration-plan.md](migration-plan.md).
