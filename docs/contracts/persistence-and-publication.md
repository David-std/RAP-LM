# Spatial persistence, artifact lineage and publication contract

**Status:** proposed physical schema and controls implementing committed Figures 5B/5D/5E. No migration or database has been deployed by this specification.  
**Plan trace:** Table 14A (spatial database, model/evaluation and batch pipeline), RT-03, WBS 3.1.4/3.3.2/3.4.4.

## 1. Ownership and access

- PostgreSQL/PostGIS is the authoritative store for **published** unit geometry, period catalog, run metadata, risk results and provenance references.
- The batch publisher is the only writer of analytical results. A restricted publication role may INSERT into staging and activate a validated run; an API role may SELECT from published views, never mutate. Schema migrations use a separate migration role, not API or training credentials.
- Artifact storage holds immutable raw snapshots, transformed dataset versions, tensor/split manifests, model weights/checkpoints, environment manifests and metrics. Git version-controls source code and small text manifests; large weights/datasets belong in a versioned persisted volume or suitable object storage with SHA-256 and retention policy.
- Never embed database credentials, Git tokens, cloud credentials or protected raw data in Docker images, scripts, logs or Git.

## 2. Proposed relational entities and keys

| Entity | Minimum fields | Rules/indexes |
|---|---|---|
| \`source_snapshot\` | \`source_snapshot_id\`, publisher, URL, licence, captured_at, coverage_start/end, SHA-256, parser_version, source_classification | Unique source/version/hash; full licence and access conditions |
| \`dataset_version\` | \`dataset_version_id\`, manifest_uri/hash, source_snapshot_ids, data dictionary version, quality report URI, created_at | Immutable lineage and no implicit overwrites |
| \`spatial_representation\` | \`representation_id\`, type, grid_origin, resolution_m, analysis_crs, clip_geometry_hash, support_mask_version, district_relation_rule | Stable across all cells/results in a run; do not assume grid resolution yet |
| \`spatial_unit\` | composite (\`representation_id\`, \`unit_id\`), geometry, display label, \`unit_type\`, structural support status | Valid polygon/multipolygon; GiST on geometry; known boundary; no ambiguity with district |
| \`district\` | \`district_id\` (official territorial key), name, polygon, boundary_version | Exactly the 43 accepted province-of-Lima districts; Callao excluded |
| \`unit_district_relation\` | \`representation_id\`, \`unit_id\`, \`district_id\`, intersection area/weight, relation_method | Necessary for border-intersecting grid cells; no arbitrary centroid assignment unless approved and assessed |
| \`analysis_period\` | \`period_id\`, start/end, granularity, timezone_definition, is_complete | Non-overlapping periods for one representation; [start,end) |
| \`target_definition\` | \`target_definition_id\`, outcome population, formula, scale, units, exposure/severity method, thresholds reference, approval status | Immutable semantics; fatal-only distinct from all-collision |
| \`model_run\` | \`run_id\`, dataset/representation/target IDs, model_version, code SHA, config/artifact checksum, split ID, benchmark URI, timestamps, status, declared population | Lifecycle draft→evaluated→approved→published or rejected; no ambiguous mutable model ID |
| \`risk_result\` | \`run_id\`, \`representation_id\`, \`unit_id\`, \`period_id\`, indicator numeric/null, level/null, availability, provenance_id, uncertainty fields (nullable) | Unique (\`run_id\`,\`unit_id\`,\`period_id\`); indexes (run,period), (run,unit); reject NaN/inf |
| \`district_result\` | \`run_id\`, district_id, period_id, value/level/availability, aggregation_method_id, inputs_checksum | Unique (run,district,period); derived from same run only; must reconcile |
| \`publication_pointer\` | single active key, \`run_id\`, activated_at, activated_by, approval_evidence | Atomically points to one completely reconciled approved run |

These are **design entities**, not a claim that migrations already exist. Implement as SQLAlchemy models and versioned Alembic migrations. Partitioning is optional and must follow measured volumes, not cargo-cult performance design.

## 3. Spatial semantics

1. Source CRS is explicit and validated; transform to a documented projected analysis CRS appropriate for Lima **only after confirming** unit accuracy and official coordinate metadata. Store/or serialize public geometry consistently in EPSG:4326/GeoJSON; document the difference between storage CRS and analysis CRS.
2. Verify topology (\`ST_IsValid\` or equivalent), geometries within the accepted 43-district boundary, and grid coverage/masking counts. Quarantine invalid records and report changes/losses.
3. For boundary-crossing cells, record intersection proportions. Assignment policy must state whether cells are clipped, allocated using intersections, or assigned by an official rule. Never silently duplicate a crash across two districts.
4. A geometry-only zoning/support mask is neither pedestrian exposure nor proof that no event could occur outside it. Report events excluded by mask and conduct sensitivity checks.
5. A missing source observation does not become zero. Track \`observed\`, \`observed_zero\`, \`missing\`, \`outside_source_coverage\`, \`temporal_coverage_unavailable\`, \`insufficient_support\`.
6. Index spatial geometry with GiST; use bounded geometry queries and \`ST_Intersects\`/equivalent through GeoAlchemy2. Benchmark query latency rather than asserting any performance SLA not set by the plan.

## 4. District aggregation: semantic gate

The plan expects both cell and district views. The aggregation rule is a **function of target semantics**, not a default \`AVG(cell.risk_level)\`.

Examples of admissible *conditional* choices:
- Count of disjoint events: sum exactly once when cells partition the domain and no events are duplicated; reconcile with raw unique event IDs.
- Exposure-normalized rate: aggregate compatible counts and exposure denominators first, then divide; never mean the rates without justified exposure weights.
- Relative score/index: specify mathematically valid weighting/normalization and verify district values against approved reference; if no defensible rule exists, mark district indicator **not publishable**, not a fake average.
- Low/medium/high: derive from the aggregated continuous indicator using the same pre-registered scale and threshold mapping; never average category labels.

If a grid cell crosses a district boundary, any apportioned contribution requires measured/justified allocation weights; a binary centroid policy cannot be chosen merely for ease of coding. Results must state district aggregation method and whether an observation is unavailable.

## 5. Artifact manifest (minimum invariant)

\`\`\`json
{
  "schema_version": "1",
  "run_id": "example-unpublished-run",
  "source_snapshot_ids": ["source-snapshot-id"],
  "dataset_version_id": "dataset-version-id",
  "representation_id": "representation-id",
  "target_definition_id": "approved-target-id",
  "split_manifest_hash": "sha256:...",
  "feature_schema_hash": "sha256:...",
  "model_family": "cnn_lstm",
  "code_commit_sha": "git-sha",
  "config_hash": "sha256:...",
  "weights_uri": "versioned-store-uri",
  "weights_sha256": "sha256:...",
  "metrics_uri": "versioned-store-uri",
  "metrics_sha256": "sha256:...",
  "environment_manifest_uri": "versioned-store-uri",
  "publication_eligible": false
}
\`\`\`

Values are placeholders illustrating **fields**, not real metrics/approved outputs. Record Python/PyTorch/CUDA/CPU versions, dependency lock hashes, random seed, preprocessing transforms, tensor shape, CRS, period mapping, masks and hardware/time/energy or memory as available.

## 6. Publication transaction — required state machine

\`\`\`text
CREATED -> PROFILED -> TRAINED -> EVALUATED -> APPROVED
                                                  |
                                                  v
                                             STAGED_IN_DB
                                                  |
                                      reconciliation passes?
                                          /             \
                                        no               yes
                                        |                 |
                                     REJECTED        PUBLISHED
                                                          |
                                               active pointer swap
\`\`\`

The pipeline should support cancellation/retry idempotently by immutable \`run_id\`; approval requires evidence, not automatic success on trainer exit.

**Staging validations before publication:**
- expected row count by unit×period, no duplicate PKs, approved grid/district mapping, valid geometry and known periods;
- no unqualified target/source scope, no forbidden leakage/exposure variable, benchmark and thresholds frozen before test;
- indicator finite and within its documented scale, level generated by registered thresholds, null states accompanied by availability reasons;
- exact correspondence between risk results, archived prediction artifact checksum and PostGIS rows;
- exact reconciliation of district aggregates with eligible unit results under approved aggregation rule;
- audit log identifies dataset, source versions, model, code commit, reviewer, timestamps and metric report.

**Atomic activation:** insert/validate a new run in a transaction or staging schema; only after approval commit an active pointer update atomically. API reads a pinned \`run_id\` snapshot for the entire request. Rollback means pointing back to the prior published run; the previous result set is retained. If the new run fails midway, old publication remains visible unchanged. Avoid deleting active run in cleanup.

## 7. Database roles and runtime segregation

\`\`\`text
Web browser --HTTPS--> Nginx/SPA --> read-only FastAPI
                                             |
                                       SELECT only role
                                             |
                                       published SQL views
                                             |
                                       PostGIS database
                                             ^
                               INSERT/stage/activate role
                                             |
                                    offline batch worker
\`\`\`

Enforce separate DB roles even if they use the same Compose PostgreSQL instance. Limit read role to approved views/tables and explicitly exclude \`raw_*\`, \`staging_*\`, training labels and sensitive/raw persons. Publication/DDL remain independent. Use Compose networks/environment secrets and TLS at the exposed boundary; fail closed when DB or active publication is unavailable, never return a mock as fallback.

## 8. Verification and audit acceptance

- Alembic migration up/down smoke test (down only when safe), referential integrity/uniqueness constraints, invalid SRID rejection, GiST index presence.
- Live 43-district fixture and accepted source counts checked against a versioned reference; differences require evidence.
- Simulate partial publication failure: assert active pointer and old results remain unchanged.
- Test parallel read during publication: each response pinned to one coherent run.
- Compare archived CSV/Parquet result checksum/values to DB published rows and GeoJSON API values.
- Restore a documented snapshot (DB + weights + manifests) in clean Docker Compose and reproduce a query.
- Access tests: read user cannot execute INSERT/UPDATE/DELETE; batch user cannot access unrelated roles/schemas.

**Reference:** integrated plan v1.5 Figures 5B, 5D and 5E; WBS 3.1.4/3.3.2/3.4.4 and RT-03. See [implementation-blueprint.md](../architecture/implementation-blueprint.md), [read-api.md](read-api.md), [analytical-protocol.md](../ml/analytical-protocol.md).
