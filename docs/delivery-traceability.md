# Delivery traceability and verification status

**Baseline:** integrated project plan v1.6, dated 2026-11-09; §3.11 Figures 5A–5E, §4.2.1 Table 16 (WBS dictionary), §8.1 Tables 34–36 (quality), §§9–10 (communications/stakeholders).
**Repository review:** 2026-11-16. Inspected main, develop and draft PR #10 (analysis/feature-target-contract, target develop). This record is an implementation/evidence audit, not a claim of formal project acceptance.
**Reading rule:** Planning documented ≠ implementation present ≠ tested/accepted. A passing CI workflow means the checks it runs passed, not that every WBS criterion or product-quality metric was met.

## Product baseline and current implementation

- **Defined architecture:** modular monolith; offline PyTorch CNN–LSTM as a *reference* on a regular raster and temporal sequence; publication of evaluated runs to PostgreSQL/PostGIS; read-only FastAPI services; React/TypeScript/Leaflet client. The 43 districts of the province of Lima are the geographic boundary, excluding Callao. This remains unchanged between the v1.5 architecture and v1.6 report.
- **In develop today:** a functioning initial React/FastAPI prototype and reproducible ONSV fatal-event ingestion/profiling and spatial-representation experiments. The API invokes RiskProvider.predict() on web requests; its score is a deterministic SHA-256-derived **synthetic value** for the selected unit/period, not a trained risk model. The web uses old endpoints and initial selection/comparison flows.
- **In draft PR #10 only:** detailed C4 responsibility boundaries, a proposed five-resource read API, PostGIS publication schema, source/feature/target safeguards, ML benchmarking protocol and a staged migration design. These documents do not deploy PostGIS, implement the model or close data gates.
- **Not evidenced in this repository:** production-ready all-severity pedestrian-collision dataset, independently defended target formula, trained CNN–LSTM, baseline test comparison, Docker Compose/PostGIS deployment, approved run publication, five final GET resources, full critical end-to-end tests or five-specialist validation.

## WBS package status

Status vocabulary: **DESIGNED** = a reviewable design exists but no acceptance sign-off; **PARTIAL** = some executable work/evidence exists, the WBS acceptance criterion is not yet proven; **NOT IMPLEMENTED** = implementation not found in reviewed branches; **NOT VERIFIED** = possible administrative evidence not available in the code repository. A package is **ACCEPTED** only with its Table 16 evidence and acceptance criterion, not by elapsed sprint dates.

| WBS | Expected deliverable and acceptance criterion (Table 16) | Evidence in repository | Status / missing evidence |
|---|---|---|---|
| 3.1.1 | Profile sources: coverage, grain, variables, access/quality and include/exclude decision; profiling report | docs/data/source-qualification.md, feature-coverage-evidence.md; pipelines/profiling/, ONSV source audits | PARTIAL: multiple sources audited; no accepted all-severity outcome coverage across 43 districts |
| 3.1.2 | Benchmark alternatives with same protocol and metrics; benchmarking report | docs/data/representation-experiments.md; docs/ml/analytical-protocol.md (draft PR) | PARTIAL: empirical representation/sparsity exploration, but not completed **model** benchmark or final configuration selection |
| 3.1.3 | Reviewable components, interfaces and deployment diagrams against technical requirements | docs/architecture/implementation-blueprint.md and contracts (draft PR) | DESIGNED: Fig. 5A–5E and interface responsibilities documented; design review/acceptance not recorded |
| 3.1.4 | Data model including entities, relations, valid geometries and metadata supporting unit/period queries | docs/contracts/persistence-and-publication.md (draft PR) | DESIGNED: physical migrations/constraints and query proof not implemented |
| 3.1.5 | Navigable prototype showing map, queries, filters and comparisons | apps/web/src/App.tsx, RiskMap.tsx | PARTIAL: early period selection, map/detail and spatial comparison exist; v1.6 temporal comparison/provenance/final risk semantics not evidenced |
| 3.2.1 | Versioned reproducible multi-source analytical dataset, variable dictionary, complete processing lineage | ml/datasets/ (draft PR), data/features/*.json, profiling and representation scripts | PARTIAL: validated contracts and subset transformations, no approved model-ready full-population dataset |
| 3.2.2 | Versioned CNN implementation, input/output contract and reproducible pilot metrics | ML protocol only | NOT IMPLEMENTED |
| 3.2.3 | Versioned ordered RNN/LSTM sequences and reproducible leakage-free pilot metrics | ML protocol only | NOT IMPLEMENTED |
| 3.3.1 | Contract-compliant documented API, positive and negative query tests | apps/api/src/raster_api/main.py, unit tests | PARTIAL: legacy provider/request-time scoring; missing v1.6 GET resources and PostGIS-backed services |
| 3.3.2 | Spatial database, common SRID, spatial indices, reconciled per-unit counts | PostGIS schema proposed in draft PR | NOT IMPLEMENTED |
| 3.3.3 | UI with map, legend, filters, same-period and across-period comparisons per RF-01–RF-06 | apps/web/ prototype | PARTIAL: map/period/spatial selection present; full geometry/provenance/temporal-comparison evidence absent |
| 3.4.1 | Integration dependencies/contracts and responsible owners documented | docs/architecture/migration-plan.md (draft PR) | DESIGNED; coordinated integration execution evidence still pending |
| 3.4.2 | Frontend actually consumes final API; loading/error paths verified | Legacy web-to-API integration | PARTIAL; no final GET contract/parity or integrated scenarios |
| 3.4.3 | Zone, period, filter and comparison end-to-end flows, no blockers | Some unit/API/UI prototype behavior | NOT VERIFIED against final contract and critical E2E plan |
| 3.4.4 | Model outputs stored in DB and served unchanged by API | Proposed pipeline and publisher contract | NOT IMPLEMENTED |
| 4.3 | Critical functional/integration/system tests executed; no blocking defects | API and source-processing unit tests; PR CI success at previous revision | PARTIAL; complete acceptance suite, scenario outcomes and defect log absent |
| 4.4 | CNN–LSTM evaluated vs **historical mean** on independent same-target holdout; metrics/time/resources | Evaluation protocol in draft PR | NOT IMPLEMENTED/MEASURED |
| 4.5 | Validated with at least five specialist users; task success, completion time and interpretation recorded | Planned in report v1.6 | NOT VERIFIED in repo |
| 5.3 | Installable clean environment and reproducible trained-model run | README explains prototype install; no full Compose/model replay | PARTIAL |

**Management deliverables:** v1.6 documents quality planning (§8), communication plan (§9) and stakeholder analysis (§10). Their existence in the DOCX is evidence of planning, **not** evidence that periodic communications, validations, approvals and change-control actions actually happened. Meeting notes, Microsoft Project baselines, specialist questionnaires and professor approvals are maintained as project-management artifacts; do not fabricate them in Git history.

## Quality verification matrix — 15 metrics from v1.6

These targets reproduce Table 35 in concise terms. **Unmeasured ≠ failed; passed unit tests ≠ accepted metric.** Store measurement date, exact run/dataset/code SHA, sample size, numerator/denominator and test artifact when evidence becomes available.

| Metric | Target and WBS/source | Test/evidence that must exist | Verification status |
|---|---|---|---|
| M-01 Spatial correspondence | >=95%; RF-01/RF-07/RD-03, 4.3 | Reference-coordinate/geometry fixtures and UI/API comparison within 43 districts | NOT MEASURED |
| M-02 Result completeness | >=95% of applicable results show unit, period, value and risk level; RF-07/RF-08 | UI result assertions against final published DTOs | NOT MEASURED |
| M-03 Source/version traceability | >=95%; RF-08, 3.3.1/4.3 | Follow result -> provenance endpoint -> source/version | NOT MEASURED |
| M-04 Pipeline reproducibility | >=95% values within <=1% relative tolerance when reference !=0; absolute equality at 0; 100% unit/period/category match; RD-06/RNF-02 | Re-run *same* data/code/config and reconcile outputs; do not use hash-based prototype as substitute | NOT MEASURED |
| M-05 Relative model error improvement | >0%: (baseline_error - model_error)/baseline_error *100; RM-01/RM-05, 4.4 | Same-target independent temporal holdout, registered primary error metric and baseline; define handling for baseline error =0 | NOT MEASURED |
| M-06 Functional requirements | 100% mandatory RF accepted; 4.3 | Requirement-by-requirement acceptance suite with recorded pass counts | NOT MEASURED |
| M-07 Critical E2E scenarios | 100% passed, zero blockers; RV-02, 3.4.3/4.3 | Tested zone/period/filter/compare/provenance paths through deployed API/database | NOT MEASURED |
| M-08 Query/filter/compare correctness | >=95% total, 100% critical; RF-03–RF-06/RT-02 | Golden input/output integration fixtures and frontend assertions | NOT MEASURED |
| M-09 API response p95 | <=2 seconds; RT-02/RT-03, 3.3.1/4.3 | Documented representative load, sample count, environment and p95 of risk/compare | NOT MEASURED |
| M-10 Specialist task success | >=80% and not below reference; RV-03, 4.5 | Specialist-by-task starts, passes, failures and dropouts | NOT MEASURED |
| M-11 Specialist task-time reduction | >0%, without M-10 regression; RV-03, 4.5 | Paired comparable task timings using ONSV reference and MVP | NOT MEASURED |
| M-12 Correct interpretation + utility | >=80% correct; >=4/5 mean utility; RNF-01/RF-07, 4.5 | Specialist questionnaire and interpretation tasks | NOT MEASURED |
| M-13 SPI | >=1.00; 4.2 | Verified Microsoft Project earned/planned value baseline | Report v1.6 states SPI=1.00 at its own cut; NOT independently repo-verified |
| M-14 CPI | >=1.00; 4.2 | Verified earned/actual cost baseline in Microsoft Project | Report v1.6 states CPI=1.00 at its own cut; NOT independently repo-verified |
| M-15 Approved-change discipline | 100% prior impact analysis/authorization, or N/A when none; 4.1 | Change log and authorization before each implemented baseline change | NOT VERIFIED |

**Data quality activities (Table 36):** separately audit source coordinates, duplicates, missingness, exclusion reasons, availability dates and snapshot hashes before modeling. These checks are procedural work and cannot be silently counted as a sixteenth published quality metric. Metrics M-01–M-12 concern product/use; M-13–M-15 concern project administration.

## Next implementation sequence (source-safe)

1. **Infrastructure first:** reproduce actual services with pinned Docker Compose profiles, PostGIS, isolated API-read and publisher-write roles, Alembic migrations and deterministic test fixtures. Tests: clean boot, rollback, permission isolation and migration stability. Addresses WBS 3.3.2, 3.1.4 and 5.3.
2. **Publish/store separately:** implement source/dataset/run/geometry/period/provenance schema and atomic activation with checksums. Prove a failed publication leaves the previous run active. Addresses WBS 3.2.1, 3.4.4 design gates, M-03/M-04.
3. **Implement read API:** five plan-defined GET resources (/periodos, /unidades, /riesgo, /comparaciones, /procedencia) with query validation, bounded GeoJSON and pinned published run; no torch or RiskProvider in runtime path. Addresses RT-02, 3.3.1 and M-08/M-09.
4. **Adapt client:** typed API and shared query state, map polygons, comparisons across both zones and time, provenance/availability and accessible legends. Addresses RF-01–RF-08, 3.3.3, M-01/M-02/M-03/M-08.
5. **In parallel, data R&D:** qualify an all-severity pedestrian-collision outcome and spatial/temporal compatibility, choose observed target and grid from evidence, freeze baseline/splits before model training. An ONSV fatal-only training exercise may be conducted for scientific exploration but must not be published as validated general collision risk.
6. **Benchmark and validation:** when input/target gates close, train CNN–LSTM offline, evaluate against the same-target historical mean, publish eligible run, execute M-01–M-12 acceptance, five-specialist validation and record model metrics.

**Stop conditions:** no fabricated data, coordinates, severity, exposure, p95 or training scores. No synthetic run promoted as real risk. Incomplete source coverage is explicit; Callao excluded. Record the reason for every open gate.

## Implementation PR requirements

Every code PR must cite: WBS package, requirement ID(s), C4 component (Figure 5A–5E), linked quality metric(s), executable test command and evidence (CI run, report path, dataset/manifest hash where applicable). Use one clear status per work package: **proposed / in progress / verified / accepted**. Merge to develop only after review. Reassess any architectural or scope change against the v1.6 project plan, not the old prototype behavior.

**Verification note:** inspected repository source and PR files; no new model training, Docker/PostGIS deployment, specialist sessions or performance benchmarks were executed during this documentation audit.
