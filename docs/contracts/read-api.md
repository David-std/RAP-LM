# Read API contract — published analytical results

**Status:** proposed HTTP DTO precision for committed Figure 5D resources. Not an implemented API and not evidence that a risk model is ready.  
**Source:** integrated plan v1.5 §3.11 Figure 5D; Figure 5C and RF-01–RF-08, RT-02. API exposes no public writes.

## 1. General conventions

- Base path: \`/api/v1\` is an internal versioning proposal. Exact endpoint names from Figure 5D remain \`/periodos\`, \`/unidades\`, \`/riesgo\`, \`/comparaciones\`, \`/procedencia\`; therefore final paths are \`/api/v1/periodos\`, etc. A prefixed root must be confirmed during API implementation.
- GET only; idempotent and read-only. \`/health\` may exist as an operational probe.
- All query filters explicitly typed and allowlisted; never concatenate raw SQL filters.
- UTF-8 JSON unless \`application/geo+json\` is negotiated for units; GeoJSON coordinates WGS84 longitude/latitude (RFC 7946).
- ISO 8601 for dates and timestamps; period boundary convention half-open \`[start, end)\`; time-zone/source conventions recorded in \`/procedencia\`.
- Public identifier is stable opaque \`unit_id\` (not a bare longitude/latitude, array index or display district label); period identifier is stable \`period_id\`; every modeled response includes \`run_id\`.
- Default queries select the currently approved active publication. Internally resolve active run **once per request** to avoid mixing versions. If historic run selection is exposed later, that is a separately reviewed feature.
- A response is analytical evidence only when \`publication_status=published\` AND source/target scope is suitable. Prototype fixtures must be flagged \`synthetic=true\` and cannot populate production publication tables.
- A risk value is never implicitly a probability or percentage. A rate is never implied by a normalized score. Include unit, scale, population, period and interpretation.

## 2. Canonical DTO types (language-independent conceptual schema)

\`\`\`ts
type ID = string; // opaque, stable; max length and permitted charset enforced server-side

type RiskLevel = "low" | "medium" | "high" | null;

type Availability =
  | "observed" | "observed_zero" | "missing"
  | "outside_source_coverage" | "temporal_coverage_unavailable"
  | "insufficient_support" | "not_published";

type RunScope = "general_pedestrian_collision" | "fatal_pedestrian_collision";

interface PublishedRun {
  run_id: ID;
  dataset_version: ID;
  model_version: ID;
  target_definition_id: ID;
  representation_id: ID;
  published_at: string; // ISO 8601
  population_scope: RunScope;
  publication_status: "published";
  methodology_version: ID;
}

interface Period {
  period_id: ID;
  start: string; // inclusive
  end: string;   // exclusive
  label: string;
  availability: Availability;
}

interface RiskValue {
  unit_id: ID;
  period_id: ID;
  run_id: ID;
  indicator_value: number | null; // finite when present
  value_unit: string; // e.g. "relative_index"; must match approved methodology
  risk_level: RiskLevel;
  availability: Availability;
  source_coverage_status: string;
  uncertainty: null | {
    type: string;
    lower: number | null;
    upper: number | null;
    interpretation: string;
  };
  provenance_id: ID;
}
\`\`\`

The TS snippet defines a design contract, not a promise that a specific risk formula, uncertainty estimator or categorical threshold has been validated. \`indicator_value=null\` and \`risk_level=null\` when unavailable; zero must mean an observed numerical zero and must not encode missingness. If no uncertainty was evaluated, use null rather than invented confidence intervals.

Server response metadata envelope for JSON collections:
\`\`\`json
{
  "meta": {
    "contract_version": "1",
    "run_id": "published-run-id",
    "target_definition_id": "approved-target-id",
    "population_scope": "fatal_pedestrian_collision",
    "scope_notice": "High-severity/fatal population only",
    "generated_at": "2026-10-01T00:00:00Z"
  },
  "data": []
}
\`\`\`
All identifiers/timestamps above are **illustrative contract examples**, not actual published runs. Do not serve this example as data.

## 3. Five product resources

### GET /periodos — RF-03

Returns the periods with published, eligible results for the selected active run; sorted chronologically ascending. Empty list means no publishable results; do not synthesize missing calendar periods. Each period records interval and availability. Optional \`limit\` with bounded maximum; no filter may expose an unapproved run. Consumer: period selector and compare-period dropdowns.

### GET /unidades — RF-01/RF-02/RF-07

Returns authoritative polygons as a GeoJSON FeatureCollection; each Feature has \`properties.unit_id\`, \`unit_type\` (grid/district), \`display_name\`, \`support_status\`, optional parent district IDs. All polygon geometry comes from stored PostGIS data, not eight display points or map tile geometry.

Allowed filters (proposal): \`unit_type=grid|district\`, \`bbox=minLon,minLat,maxLon,maxLat\` validated against Lima bounds and with max-size/pagination constraints. Enforce a hard cap and document a \`next_cursor\` strategy if grid output exceeds the response budget. No geometry simplification may change identities or counted membership. Invalid geometries are rejected before publication.

### GET /riesgo — RF-01/RF-02/RF-03/RF-04/RF-07

Required \`period_id\`; optional \`unit_id\` (single detail) or supported \`unit_type\`/bounded bbox (map collection), plus allowlisted filters only if they are in the published run's representation. No user-supplied target formula. Return \`RiskValue\` objects tied to the same active run; if a requested unit-period has no eligible result, return an explicit availability status, not synthetic interpolation or zero.

A detail response must identify the exact spatial unit, period, numerical meaning, level threshold methodology, scope and \`provenance_id\`. A collection must be spatially bounded or paginated and stable-sorted; the frontend should not silently fetch an unbounded national-level geometry set.

### GET /comparaciones — RF-05/RF-06

Exactly one of two mutually exclusive modes:

- \`mode=spatial\`: \`unit_a\`, \`unit_b\`, \`period_id\`; requires distinct units within a common representation and same active run.
- \`mode=temporal\`: \`unit_id\`, \`period_a\`, \`period_b\`; requires distinct periods, same unit/representation, identical indicator scale and compatible methodology/run context.

Return both RiskValue objects and comparison metadata: \`comparable: boolean\`, \`reason\` when false, \`difference\` and \`difference_unit\` only if mathematical comparability has been approved. Avoid percentage change with zero denominator. Comparison is not causality or policy recommendation.

### GET /procedencia — RF-08

Required \`provenance_id\` or supported \`run_id\`; resolves publication lineage and describes:

- dataset source list (publisher, URL, licence, extraction time, version/hash, spatial/temporal coverage);
- accepted population and outcome class definition, severity inclusion/exclusion, fatal-only notice when relevant;
- feature IDs, units, transformations, missingness/coverage masks, exposure semantics;
- grid specification, CRS, time periods, split strategy, comparator, benchmark metrics and evidence artifact IDs;
- formula/scale for indicator, any low/medium/high thresholds and their provenance;
- known limitations, uncertainty description if available, publication timestamp.

No raw person-level incident data or private records in public provenance.

## 4. Errors and operational behavior

Use one stable Pydantic error schema:
\`\`\`json
{
  "error": {
    "code": "INVALID_PERIOD",
    "message": "The requested period is not available in the selected published run.",
    "details": {"parameter": "period_id"},
    "request_id": "trace-id"
  }
}
\`\`\`

| HTTP | Meaning | Example |
|---|---|---|
| 400/422 | Malformed or semantically incompatible parameters | Ambiguous compare mode, invalid bbox, unsupported filter |
| 404 | Identified unit/period/provenance does not exist | Unknown ID |
| 409 | Comparison unavailable due to incompatible scale/run or result temporarily unpublished | Invalid comparison of distinct methodologies |
| 503 | DB unavailable or no approved publication exists | Do not fall back to mock or recompute inference |
| 200 with explicit \`availability\` | Valid unit/period has no publishable measurement | Missing/unsupported grid cell |

Authentication is not introduced as an MVP feature in the plan. Regardless, configure TLS/HTTPS, CORS allowlist, safe error messages, structured logs without sensitive payloads, read-only DB principal, SQL parameterization and reasonable query limits. Public read endpoints must never mutate rows.

## 5. Stability, integration and tests

- Generate OpenAPI and a typed TS client from committed Pydantic schemas; if hand-authored DTOs are used initially, run contract parity tests.
- Golden contract tests: full 43-district boundary, representative grid polygons, one-period risk, spatial comparison, temporal comparison, fatal-only scope notice, provenance retrieval, invalid IDs, invalid bbox and missing results.
- Query tests assert every value returned is from the **same approved run** and that geography and period are consistent.
- UI tests confirm a period/filter change cancels stale requests and updates map, detail and comparison together.
- Test that production routes never import torch, invoke training/inference or issue INSERT/UPDATE/DELETE to PostGIS.
- Any migration from legacy \`GET /risk\`, \`POST /risk/compare\`, \`/metadata/*\`, \`/risk/map\` is controlled and does not silently reinterpret old synthetic contracts. See [migration-plan.md](../architecture/migration-plan.md).

## 6. Traceability

Figure 5C: map/legend RF-01/RF-07; detail/filters RF-02–RF-04; comparison RF-05/RF-06; provenance RF-08. Figure 5D: read API RT-02, integration WBS 3.3.1/3.4.2; PostGIS RT-03 WBS 3.1.4/3.3.2. RFC-style proposal fields above are **not** newly approved requirements; their final names and status codes must be reviewed against traceability before implementation.
