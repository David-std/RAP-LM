# Analytical target, raster representation and CNN–LSTM evaluation protocol

**Status:** binding research safeguards + gated mathematical design proposals; no final target/hyperparameters approved.  
**Authority:** integrated project plan v1.5, §3.2–3.4 and §3.11 (Figure 5E, Table 14A); prior P1/P2/P3 source, representation and feature evidence.  
**Purpose:** prevent training a plausible neural network that estimates the wrong phenomenon.

## 1. Problem, population and estimand — must be defined before training

The MVP must help specialized users compare **relative pedestrian-collision risk by supported spatial unit and period** across the 43 districts of Lima Province, with a meaningful indicator and three display levels. It is not a warning that a pedestrian will be hit tomorrow.

Define each candidate target in an immutable \`target_definition\` record containing:

| Required field | Question answered |
|---|---|
| Outcome population | All pedestrian collisions, strict \`ATROPELLO\` classes, or pedestrian-linked crashes? Include/exclude fugas and other classes explicitly |
| Consequence scope | All severities versus fatal-only subset; fatalities/injuries at person/event level and deduplication rule |
| Unit and denominator | Event count, exposure-adjusted rate, expected burden, relative index or another validated quantity; physical/statistical units |
| Observation window | Which event times/periods are included and whether 2025 is complete |
| Spatial support | Full district or approved grid mask; valid coverage and overlap rule |
| Target formula | Exact symbolic expression, input data availability and any smoothing/normalization coefficients |
| Reference / label source | Why the response variable is independently observed, not merely a formula trivially reconstructed from predictor fields |
| Output interpretation | Does a numeric value represent frequency, rate, probability, index, rank or burden? What is **not** justified |
| Comparison semantics | What can be compared across time, grids, districts and models |
| Evidence/version | Profiler report, reviewer decision, dataset snapshot hash and target definition ID |

**No arbitrary “risk score” label** is allowed. A model that simply learns a handcrafted same-input risk formula must justify what generalizable phenomenon it estimates; otherwise it adds complexity without evidential value.

## 2. Current outcome evidence and release gate

The accepted detailed ONSV data **describes fatal crashes**. Profiling has shown two distinct populations: 897 fatal crashes with at least one pedestrian and 839 with an \`ATROPELLO\`/\`ATROPELLO FUGA\` crash class (historical audit; check frozen artifacts before relying on counts). The classification difference must be adjudicated, never silently merged or renamed.

The 2025 release in that audited snapshot reaches only early April; it cannot be treated as a complete year or evidence of an annual drop. Presently usable complete calendar periods for exploratory comparison were 2021–2024, subject to source-version recheck.

This is **not** all pedestrian collisions. Person-level injuries/fatalities observed within crashes selected for fatality do not identify the full severity distribution of pedestrian collisions. Full-scope risk model training/publication is blocked pending a qualified non-fatal outcome source, spatial/temporal completeness and a defended target, or an explicitly approved scope change.

Allowed now: source quality audits, population sensitivity, tensor shape/dataset pipeline testing, retrospective **exploratory fatal-only** comparison with clearly labeled limitations. Not allowed: publish this exploratory output to a municipal specialist as general pedestrian-collision risk.

## 3. Exposure, severity and context semantics

- True pedestrian exposure requires an observed, appropriately time-and-location-aligned denominator or a defensible measurement protocol. ATU station validations, population density, transit-stop density and POIs are **proxies/context**, not direct pedestrian flow counts and cannot be silently entered as exposure offsets.
- Motor traffic: road class, transit routes and partial congestion geometries are not measured urban vehicle volumes. Separate direct measurement from proxies.
- Built environment: signalized intersections, crossing counts, zoning and road/urban context are optional qualified predictors; their spatial coverage/observation dates must be recorded before use.
- Severity: consequences are part of the **outcome definition**, not automatically contemporaneous predictors. A severity-weighted target needs a justified consequence scale, event/person linkage and complete source support. Weights cannot be chosen for aesthetic low/medium/high separation.
- Observed spatial density of features is not proof of source completeness: absence may be outside-source-coverage. Categorical missingness must be kept in masks.
- No claims of causality, absolute individual collision probability or real-time conditions without an appropriate design.

## 4. Candidate formulations — NOT selected

Let \`u\` be a nonoverlapping spatial unit, \`t\` a supported time window, \`Y[u,t]\` the unique observed collision-event outcome in the approved population, \`E[u,t]\` direct measured pedestrian exposure in compatible units, \`S[u,t]\` a separately approved severity construct, and \`X[u,t]\` features available before the target window.

Candidate A — conditional expected count:
\`\`\`text
target = Y[u,t]                    [events / unit / time bucket]
model = E[Y[u,t] | history, X]      [expected events]
\`\`\`
A frequency/count outcome is **not** an exposure-adjusted relative risk. Useful for modeling/sensitivity; cannot itself satisfy any claim that accounts for unequal exposure unless explicitly framed as a proxy-limited index.

Candidate B — exposure-adjusted event rate (GATED):
\`\`\`text
r[u,t] = Y[u,t] / E[u,t]
\`\`\`
Only admissible after \`E\` is measured with matching geography, period, coverage and positive/appropriate units. Decide aggregation and count likelihood (e.g., offset \`log(E)\`) using data. Zero exposure cells are undefined, not automatically zero risk.

Candidate C — severity-aware burden (GATED):
\`\`\`text
B[u,t] = sum_over_approved_events(approved_severity_weight(event))
\`\`\`
Requires coverage of non-fatal and fatal consequences across the chosen population, explicit scale/weights, same-period observation and independent label validity. Do not use same-period \`B\` as a predictor of \`B\`.

Candidate D — relative indicator for presentation (GATED):
\`\`\`text
I[u,t] = documented_monotone_mapping(approved_model_output,
                                     calibration/reference_distribution)
\`\`\`
Fit normalization/calibration using training/validation only, freeze before independent test, and make the units/scale explicit. Do not claim \`I=0.8\` means an 80% probability.

The selected formula may differ from these; a decision record must justify it and map it to the plan-defined risk indicator.

## 5. Spatial-temporal representation

**Reference architecture committed by Figure 5E:** regular raster/grid, CNN for spatial relationships per period, LSTM (member of RNN family) for an ordered time sequence, outputs per cell, and an explicitly justified district aggregation.

**Not yet fixed:** grid resolution, origin/orientation, clipping/support mask, temporal bucket, past lookback length, horizon alignment, number of convolution stages, LSTM hidden size/layers, loss, feature channels and optimizer. Record and benchmark these; do not silently choose.

P2 evidence currently retains \`district_month\`, \`grid_1000m_month\`, \`grid_2000m_month\` candidates, \`grid_500m_month\` as conditional sensitivity. District is a comparator or aggregation, **not** automatically an equivalent CNN raster. A selected grid should preserve continuous adjacency even where source features are missing; masked cells are handled explicitly instead of compressing the array and destroying topology.

For T periods, F feature channels, H rows and W columns:
\`\`\`text
X: [B, T, F, H, W]    // batch, ordered time, channels, grid rows, grid cols
M: [B, T, F, H, W]    // observed/coverage mask, with explicit missingness enums
CNN(X_t, M_t) -> E_t: [B, D, H, W]   // preserve location (or documented equivalent)
stack(E_1..E_T) -> [B, T, D, H, W]
per-cell sequence -> [B*H*W, T, D]
LSTM(sequence) -> latent per cell
output head -> [B, H, W, O]
\`\`\`
This is one **proposed feasible implementation**, not a claim that raw Table 14A specified tensor channel layout. Spatial pooling that destroys cell identity is disallowed unless accompanied by an independently justified reconstruction, because the MVP needs per-cell outputs. Avoid forecasting terminology unless the label horizon is explicitly defined. For held-out evaluation, features used to estimate a target at time \`t\` must be available at the actual information cutoff. Any lagged crash history uses \`< t\` and a declared lag window. If estimating the same historical interval retrospectively with contemporaneous context, define observational availability and distinguish that task from an advance forecast.

Sanity checks: expected tensor dimensions, invariant cell ordering, fixed aligned grid across periods, reproducible masked values, exact spatial joins, no future leakage, and a geometry/index round trip from tensor output back to \`unit_id\`.

## 6. Leakage-proof chronological protocol

Reference **candidate** split from P3: train 2021–2022, validation 2023, independent test 2024. This is contingent on qualified source coverage and enough meaningful observations after masks and lag windows. Exclude incomplete 2025 from any misleading full-year comparison. The chosen split manifest stores timestamps and hashes and is frozen before test evaluation.

- Fit imputation, scalers, category encoders, normalizers, thresholds, class/seasonality weights and any supervised feature selection on training only (or training+validation only when formally justified for the final model, while still preserving an untouched test).
- Hyperparameter/grid/window decisions are made on train/validation evidence, **not** the test score.
- If evaluating spatial holdout/generalization, record group strategy (spatial blocks, district groups), buffers and overlap. Do not use a random row split that leaks neighboring raster cells and past/future windows.
- The rolling historic baseline at t uses only previously eligible periods, aligned by the **same spatial unit, time bucket/seasonality, population and target scale**. It must not average target test-period values.
- With short sparse event time series, report uncertainty across seeds/repeats and baseline stability; do not assert that CNN–LSTM is well-powered simply because training finishes.

## 7. Benchmark design and technical acceptance

Minimum mandatory comparator: historical mean for the **same target** on the same held-out rows, as the v1.5 plan states. Additional diagnostic baselines (e.g., naive lag, Poisson/Negative Binomial, strong tabular regressor) may be used, but they do not replace or quietly weaken the required comparator.

Define metrics after selecting target:

| Target | Primary candidates | Secondary diagnostics |
|---|---|---|
| Continuous count/burden | MAE, RMSE, appropriate deviance | Error by district/month, support stratum, systematic bias |
| Event occurrence (rare binary) | PR-AUC, Brier score/calibration | Recall@k, precision/recall, false-alert burden |
| Valid exposure rate | error on rate/count with declared weighting/offset | exposure-stratified error, denominator stability |
| Relative continuous index | absolute/squared error if a defensible independent reference exists | ranking stability, rank correlation, top-k overlap |
| Low/medium/high | pre-registered confusion matrix and macro-F1/weighted metric | high-level FP/FN as defined below |

Require in every report: approved data sources, population, source hashes, feature list/masks, grid/period/window, train/val/test intervals and effective examples, seed/hardware/runtime, model hyperparameters, baseline definition, metric formula and unit, point estimates, uncertainty where estimable, subgroup/temporal robustness and failure examples.

**Selection gate:** CNN–LSTM must exceed historical mean under the pre-registered primary metric on independent test **without tuning on it**. A difference that is trivial, unstable or due to unequal support is not a validated improvement. If model does not beat baseline, report failure and trigger R-04 corrective decision/change review; never fabricate a weak baseline or present a failing model as validated.

## 8. Three levels and error definitions

The plan commits \`low\`, \`medium\`, \`high\` display levels. Their numerical threshold values are **GATED**. Choose threshold methodology on training/validation support and freeze before independent test, with one common comparable scale across model and baseline. Document whether thresholds are policy-informed or empirical quantiles; quantiles are not absolute danger probabilities.

- \`FP(high)\`: output predicts/classifies **high** while the approved reference class for the same unit-period is below high.
- \`FN(high)\`: approved reference is **high** while output classifies below high.
- Confusion matrix must use a valid same-scale reference and preserve missingness. Do not equate "no recorded event" with verified zero underlying risk.
- Reclassification or threshold tuning after test results is prohibited for the reported independent evaluation.

## 9. Reproducibility manifests

Every completed experiment writes machine-readable:
\`\`\`text
source-manifest.json           // publisher, licence, capture timestamp, checksums
quality-report.json            // exclusions, missingness, temporal and spatial coverage
representation-manifest.json   // grid origin/resolution/CRS, support mask and hashes
feature-schema.json            // source, unit, time semantics, allowed missingness for each channel
target-definition.json         // exact outcome population, formula, unit and interpretation
split-manifest.json            // target windows, cutoffs, train/validation/test ID hashes
training-config.json           // seeds, hyperparameters, environment and code SHA
metrics.json                   // baseline and model, units, support, confidence/uncertainty
predictions.parquet            // run/unit/period prediction, availability and label where authorized
decision-record.md             // why selected, rejected alternatives and scope of claims
\`\`\`

The dataset and model version used for published results must reference all these artifacts by stable URI and checksum; never publish from a notebook cell state.

## 10. Entry/exit decision gates

| Gate | Required evidence | Status at specification time |
|---|---|---|
| D1 broader outcome | Event-level official/public reproducible source including non-fatal pedestrian collisions, adequate Lima coverage and severity, OR approved scope change | **BLOCKED** |
| D2 exposure | Direct spatial-temporal pedestrian exposure OR qualified proxy strategy with validated limitations; no false denominator claim | **BLOCKED/RESEARCH** |
| D3 traffic/context | Source/coverage compatibility, source timestamp and missingness; leakage review | **OPEN** |
| D4 representation | Candidate grid/time density, urban support masks, event conservation, channel coverage and benchmark feasibility | **OPEN** |
| D5 target | Frozen population, formula, units, label generation, severity semantics and reference for comparison | **BLOCKED** |
| D6 evaluation | Split manifest, historical mean baseline, primary metric and acceptance criterion registered before independent test | **OPEN** |
| D7 publication | Passed D1–D6 for stated claim, validated model improvement and artifacts, district aggregation and specialist interpretation | **BLOCKED** |

Do not collapse a closed engineering milestone into a claim of scientific validity. Exploratory fatal-only benchmarking may continue in isolation without satisfying the general-risk release gate. In particular, **there is no current evidence that a generic pedestrian collision risk model is trained or publishable**.

## 11. Traceability

- OE1/§3.2.2: occurrence, severity, exposure and spatiotemporal context source profiling.
- OE2 and Figure 5E: grid preprocessing, CNN per period and LSTM across ordered periods.
- OE3: published per-unit and per-period relative indicator, with provenance and comparisons.
- OE4 and §3.3: independent benchmark versus historical mean and specialist usability evidence.
- WBS 3.1.1/3.1.2, 3.2.1–3.2.3, 3.4.4, 4.4; RM-01–RM-05, RD-01–RD-06, RG-01.

See [feature-target-contract.md](../data/feature-target-contract.md), [source-qualification.md](../data/source-qualification.md), [representation-experiments.md](../data/representation-experiments.md), [persistence-and-publication.md](../contracts/persistence-and-publication.md).
