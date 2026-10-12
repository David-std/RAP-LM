# Controlled migration from prototype to integrated-plan v1.5 architecture

**Status:** implementation sequence, not an authorization to migrate without evidence.  
**Branch:** this specification is reviewed in draft PR #10. Do not merge and then implement unreviewed incompatible contracts in one change.

## 1. Observed legacy state (checked against develop)

Current \`apps/api/src/raster_api/main.py\` constructs \`RiskProvider()\` and calls \`predict()\` inside \`GET /risk\` and \`GET /risk/map\`, while \`POST /risk/compare\` delegates to the provider. It also exposes \`/metadata/spatial-units\`, \`/metadata/periods\`, \`/model/metadata\` and \`/health\`. \`apps/web\` renders an initial map, period selector, detail and spatial comparison from this prototype API. P1/P2/P3 source/feature audits and blocked target contracts are separate evidence that **must be retained**, not deleted to simplify migration.

The new integrated plan v1.5 mandates an offline batch **publication** architecture, PostGIS-backed GET-only API with five core resources, React shared state and a CNN-LSTM grid reference design. Existing mocks remain acceptable only for test fixtures and local contract demos with clear synthetic labeling.

## 2. Non-negotiable migration invariants

- All writes stay exclusively within \`David-std/Raster-Analytics-Web\` and reviewable branches targeting \`develop\`. Never push release-bound changes directly to \`main\`.
- Do not modify the approved integrated-plan report to disguise implementation deviations. A genuine scope change enters change control.
- Preserve data source hashes, fatal-only limitation, source catalog, partial-year 2025 exclusion, target gates, masking semantics, chronological splits and all prior benchmark evidence.
- No public request path invokes torch/training/inference or calls unverified data portals.
- No incomplete publication or mock values reach a published active run.
- API and SPA are compatible at every merge milestone via contract tests, even if the first published run is not yet available. Fail with explicit \`no_approved_publication\` rather than synthesize a model.

## 3. Incremental work packets

### M0 — specification alignment (this PR, documentation-only)

Inputs: v1.5 Figures 5A–5E, Table 14A, traceability, active branch baseline.  
Outputs: decision register, implementation blueprint, read API contract, persistence/publication contract, ML protocol, migration path and gate checklist.  
Done when docs agree on status of each proposed vs committed field; no application behavior changed. PR stays draft until reviewed.

### M1 — technical skeleton for storage and environment

Create Docker Compose with version-pinned PostGIS, API and Nginx SPA, an explicit one-shot batch worker profile and persistent artifact/data volumes. Add Alembic migrations, roles and connection health checks. Provide deterministic seed fixtures that are clearly synthetic and isolated from production publication.  
Evidence: clean Compose startup, migration test, read-role cannot write, project README run instructions; CI unaffected by unavailable external portals.

### M2 — analytical schema, staging and atomic publication contract

Implement \`source_snapshot\`, \`dataset_version\`, \`spatial_representation\`, \`spatial_unit\`, \`district\`, \`unit_district_relation\`, \`analysis_period\`, \`target_definition\`, \`model_run\`, \`risk_result\`, \`district_result\`, active publication pointer.  
Add publisher CLI with manifest validation, duplicate checks, geometry/CRS/period reconciliation, idempotent staged insert and atomic activation/rollback.  
Evidence: integration tests for partial failure, duplicate rows, missingness, checksum mismatch and concurrent readers.

### M3 — read-only API replacement (may overlap M2 against fixtures)

Create routers for \`GET /periodos\`, \`GET /unidades\`, \`GET /riesgo\`, \`GET /comparaciones\`, \`GET /procedencia\`; Pydantic schemas, application services and SQLAlchemy/GeoAlchemy2 repositories. Pin active run per request and explicit no-publication responses.  
Compatibility strategy: keep legacy endpoints as clearly deprecated, fixture-only adapters **temporarily if needed** for old web tests; never expose them as production-ready risk endpoints. Replace integration tests before removing old routes.  
Evidence: OpenAPI DTO parity, HTTP error tests, no model import in API, DB read-only enforcement and geometry correctness.

### M4 — React application adaptation

Central typed client; one React Context state for period, spatial unit, compare mode/periods, filters and active run. Retain map, detail and spatial comparison; add the **already in-scope** temporal comparison and provenance view before MVP validation, not unrelated dashboard features.  
Geometry is polygon/GeoJSON rather than isolated demo points; preserve legend, attribution, null/coverage rendering, accessible controls and errors.  
Evidence: RF-01–RF-08 traced to UI automated/manual tests, no stale cross-period responses and no invented risk when DB has no approved run.

### M5 — validated data/outcome expansion and target freeze (data gate)

Continue qualified research/access to non-fatal pedestrian events and consequence severity (official PNP/MTC/ONSV or other reproducible source). Record source access rights, canonical IDs, spatial/temporal support, duplicates, geographic coverage, direct/proxy exposure and join validity.  
Only after evidence: approve target definition, feature schema, grid/time bucket and district aggregation; rerun P2 coverage if outcome population expands substantially.  
If full-scope data cannot be obtained, do not silently narrow the product; escalate risk and formal scope decision through project control.

### M6 — baseline, CNN-LSTM and independent technical evaluation

Build versioned tensor dataset, historical-average baseline **on same target**, CNN–LSTM PyTorch candidate and independent chronological evaluation. Train entirely offline. Freeze thresholds before test, compare metrics, uncertainty/runtime and report counterexamples.  
Do not publish an unqualified/fatal-only model under general-risk semantics. Technical failure against baseline triggers documented remediation/decision, not a misleading green badge.

### M7 — acceptance, integration, validation and release

Publish an **approved** run, smoke test API↔PostGIS↔React, compare published vs archived predictions, document provenance, complete functional tests and technical evaluation. Test specialist tasks (at least five specialist users per WBS 4.5), including correct interpretation of indicator, levels and limitation.  
Only then promote approved \`develop\` integration through normal release review to \`main\`.

## 4. Dependency/acceptance map

| Phase | Requires | Prevents | WBS |
|---|---|---|---|
| M1 | M0 architecture consensus | Unreproducible deployment | 3.1.3, 3.3.2 |
| M2 | M1 migrations/roles | Inconsistent published results | 3.1.4, 3.3.2, 3.4.4 |
| M3 | M2 schema or fixture-backed repositories | Request-time ML and endpoint drift | 3.3.1, 3.4.2 |
| M4 | M3 typed schema | Independent frontend mock drift | 3.3.3, 3.4.3 |
| M5 | P1/P2/P3 evidence, verified sources | Fatal-only generalized target | 3.1.1/3.1.2, 3.2.1 |
| M6 | M5 target+feature+split freeze | Scientifically invalid neural network | 3.2.2/3.2.3, 4.4 |
| M7 | M2–M6 complete | False green MVP delivery | 3.4, 4.3–4.5 |

M1–M4 infrastructure/contracts may proceed with **synthetic isolated fixtures**, but must not be represented as scientific validation. The data gate M5 governs production publication and meaningful ML. Synchronize this order with the approved schedule via change control if dependencies shift.

## 5. Concrete branch/PR slicing (proposed)

- \`infra/compose-postgis\`: executable multi-service environment, schema migration base and DB roles.
- \`data/publication-store\`: PostGIS entities, staging and atomic publisher.
- \`api/published-risk-queries\`: v1.5 GET API and application/repository layers.
- \`web/analytical-workspace\`: v1.5 typed client/shared state/temporal comparison/provenance.
- \`data/outcome-coverage\`: improved non-fatal/severity sources and definitive feasibility evidence.
- \`ml/cnn-lstm-evaluation\`: model only after target/representation/baseline gates close.

Branch names communicate work, not course milestones. The list is a proposal, not an instruction to run all branches regardless of dependencies.

## 6. Definition of Done and release guardrails

For each PR: requirement ID + Figure 5 component + WBS work package linked; written design decisions where ambiguous; unit/contract/integration tests; executable commands; evidence IDs/checksums; limitations updated; no loss of fatal-only or exposure gates; lint/typecheck/build passing; no unnecessary services or authentication.

A PR that only draws a diagram while leaving request-time inference, fabricated dataset, unreviewed target, unversioned DB output or contradictory API behavior in place **does not complete** the corresponding architectural work package.
