# Architecture decisions and traceability — integrated plan v1.5

**Status:** implementation decision record; no approval of unmeasured ML parameters.
**Hierarchy:** v1.5 integrated plan §3.11 Figures 5A–5E, Table 14A, requirement matrix, WBS > technical evidence > code convenience. Earlier Project Charter v1.2 is historical context.
**Statuses:** COMMITTED = plan-defined; PROPOSED = reversible implementation precision; GATED = empirical/reviewer evidence pending; BLOCKED = may not publish/claim; LEGACY = prototype.

| ID | Decision | Status and exit |
|---|---|---|
| ADR-01 | Modular layered monolith with separately executed batch pipeline; no microservices | COMMITTED, Fig. 5A/B |
| ADR-02 | React/TypeScript/Leaflet SPA, Nginx, React Context shared query state, typed API client | COMMITTED, Fig. 5B/C, RF-01–RF-08 |
| ADR-03 | FastAPI/Pydantic read API with routers/services/repositories, SQLAlchemy/GeoAlchemy2 and five GET resources | COMMITTED, Fig. 5D, RT-02 |
| ADR-04 | PostgreSQL/PostGIS stores geometry, periods, published risk outputs and run/provenance metadata | COMMITTED, Fig. 5B/D, RT-03 |
| ADR-05 | Regular raster, CNN spatial per period, LSTM recurrent across periods (LSTM belongs to RNN family) | COMMITTED *reference*; exact grid/window/config GATED by benchmark, Fig. 5E |
| ADR-06 | Relative risk indicator with low/medium/high display levels | COMMITTED output form; target formula/units/thresholds GATED |
| ADR-07 | 43 districts of Lima Province, exclude Callao; spatial grid/time bucket selected by profiling | COMMITTED boundary; resolution/time GATED |
| ADR-08 | Current official detailed ONSV fatal-only records are not all pedestrian collisions | BLOCKED for general-risk claims; qualify non-fatal events/severity or obtain formal scope approval |
| ADR-09 | Context/exposure proxies never relabeled measured pedestrian or traffic volume | COMMITTED data-safety invariant; exposure normalization GATED |
| ADR-10 | District aggregation derived from target semantics; never average levels or unsupported rates | GATED by aggregation/reconciliation method |
| ADR-11 | Git + versioned artifact storage with weights and checksums; logical C4 container need not be a Docker daemon | PROPOSED interpretation of Fig. 5B |
| ADR-12 | Separate read-only API, batch publication and migration DB roles, secrets out of code | PROPOSED security control; verify permissions |
| ADR-13 | Validate staged run then atomically activate published run pointer, rollback retaining old results | PROPOSED publication mechanism; failure-mode tests |
| ADR-14 | Retire request-time RiskProvider inference as production API path, retain synthetic fixtures only for tests | COMMITTED outcome of Fig. 5B/D; migration GATED by contract tests |
| ADR-15 | Chronological train/validation/test, no target-period or future leakage, historical-mean comparator on same target | COMMITTED plan success strategy; evidence required |
| ADR-16 | No new alerts, sensors, citizen reporting, automated interventions, microservices or authentication without scope review | COMMITTED exclusion/control |
| ADR-17 | GeoJSON EPSG:4326 output, verified projected CRS for spatial measurement and \`/api/v1\` route prefix | PROPOSED implementation specifics, review required |

## Seven clarification decisions

1. **CNN–LSTM/grid:** satisfies CNN–RNN. Diagrammatic selection does not prove superiority or freeze hyperparameters/grain.
2. **Variable objective:** before training freeze population, formula, label generation, units, reference, exposure, severity, thresholds and scale.
3. **Fatal-only:** valid high-severity exploratory evidence, *not* general pedestrian-collision outcome; unresolved source gate.
4. **Districts:** aggregate additive compatible components and derive the indicator; never average ordinal labels or ratios without valid weights.
5. **Artifacts:** physical weight storage, immutable hashes and manifests; Git controls code and small configs; C4 logical store is not inherently a separate service.
6. **Database security:** read-only API role, publish-only batch role, separate migration privilege; no shared production credentials.
7. **Migration:** current \`develop\` routes/provider are LEGACY; move to PostGIS approved-run queries incrementally, preserving P1/P2/P3 evidence.

## Requirement and WBS mapping

| Requirement | C4 component/acceptance | WBS |
|---|---|---|
| RF-01/RF-07 | 5C map/legend for authoritative polygon results, active period, explained scale | 3.3.3, 4.3 |
| RF-02–RF-04 | 5C detail, selection, filters and period synchronization | 3.3.3, 3.4.3 |
| RF-05/RF-06 | 5C spatial and temporal comparisons in same published run/scale | 3.3.3, 3.4.3 |
| RF-08 | 5C result provenance, variables, coverage, limitations | 3.3.3, 4.5 |
| RT-02 | 5D five GET routes, Pydantic contracts, services, controlled errors | 3.3.1, 3.4.2 |
| RT-03 | 5B/D PostGIS spatial and temporal entities/indices | 3.1.4, 3.3.2 |
| RD-01–RD-06/RG-01 | 5E acquisition, profiling, spatial/temporal features and tensors | 3.1.1, 3.2.1 |
| RM-01–RM-05 | 5E CNN/LSTM, historical mean, test metrics, publication | 3.1.2, 3.2.2/3.2.3, 3.4.4, 4.4 |
| RNF-02 | 5B versioned Docker Compose execution | 3.4, 5.3 |

Acceptance text remains in the original plan Annex B. Review risk triggers R-01 (source heterogeneity), R-04 (CNN-LSTM vs baseline), R-05 (contract mismatch), R-08 (misinterpretation), R-09 (quality) and R-10 (leakage). Each GATED/PROPOSED change must record alternatives, reviewer, date, evidence and downstream PR. No fictitious approval dates.

Next: [implementation](implementation-blueprint.md), [migration](migration-plan.md), [ML](../ml/analytical-protocol.md), [read API](../contracts/read-api.md), [PostGIS publication](../contracts/persistence-and-publication.md).
