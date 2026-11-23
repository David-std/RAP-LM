# Benchmark and evaluation protocol — fused all-severity run

**Status:** frozen before the first test evaluation (2026-11-22). Changing any item below after
seeing test results requires a change request in `docs/architecture/registro-de-decisiones.md`.
**Trace:** HT-02 (RM-01, WBS 3.1.2), HT-07/HT-08 (RM-02/RM-03, WBS 3.2.2/3.2.3), evaluation
RM-05 / M-05 (WBS 4.4). Code: `ml/fused/`, configs in `ml/configs/`.

## 1. Target

Latent intensity `λ[cell, year, subperiod]` of **all pedestrian collisions** (any severity, any
subtype: run over, hit-and-run, collision followed by run over, any crash with a pedestrian
victim). Subperiod = day type (weekday / weekend) × 6-hour band (0–6, 6–12, 12–18, 18–24).
`λ` is expressed on the scale of collisions recorded by the police census (CENACOM reporting
factor fixed to 1); it is not a probability and not a rate per pedestrian.

## 2. Observation model (data fusion)

Each source family is a partial observation of the same `λ`:

| Family | Years | Observes | Link |
|---|---|---|---|
| CENACOM (MININTER/INEI police census) | 2011–2016, Jan–Jun 2017 | all severities | `E[y] = λ × 1 × coverage × located_share` |
| ONSV georeferenced crashes | 2021–2024 | crashes with ≥1 fatal victim | `E[y] = λ × ρ_onsv × coverage × located_share` |

`coverage` = observed share of the year's days of that day type (2017 = first semester).
Located events (point, street intersection, street segment spread by length) are compared per
cell; events located only to a district are compared through the district sum of `λ`
weighted by cell area shares (Poisson thinning by the located share of each family-year).
Loss: Poisson negative log-likelihood on observed family-years only. Years 2018–2020 have no
observing source: the sequence passes through them but they contribute no loss and are not
published.

Assumption recorded as limitation: `ρ_onsv` (fatal share × relative coverage) is spatially
constant; geocodability is independent of location within a district.

## 3. Inputs and causality

Year `t` input = static context (7 proxies, standardised) + each family's observations of year
`t-1` (cell rate, district density, observed flag). The estimate for year `t` never reads data of
year `t` or later (RM-03). Static context comes from 2020–2026 snapshots (declared limitation).

## 4. Partitions (chronological, no leakage)

| Run | Train | Validation (early stopping + selection) | Test (frozen) |
|---|---|---|---|
| `run-main` (published) | CENACOM 2011–2017, ONSV 2021–2022 | ONSV 2023 | ONSV 2024 |
| `run-backtest-2017` (evidence only) | CENACOM 2011–2015 | CENACOM 2016 | CENACOM Jan–Jun 2017 |

The backtest is the only all-severity holdout available; the main test can only score the
severity-truncated ONSV observation of the same `λ`. Both are reported.

## 5. Alternatives compared (RM-01)

1. **B0 — historical average** (OE4-I1 baseline): for the same family, cell (or district) and
   subperiod, the mean of all prior covered years of that family, rescaled by coverage and located
   share. Uses no information from the evaluated year.
2. `poisson_glm` — log-linear Poisson regression on the same inputs (classic road-safety count
   model).
3. `convlstm` — ConvLSTM (Shi et al., NeurIPS 2015), the recurrent cell of Hetero-ConvLSTM for
   grid traffic-accident risk (Yuan, Zhou & Yang, KDD 2018). Literature benchmark.
4. `cnn_only` — same network without recurrence (ablation).
5. `lstm_only` — 1×1 kernels (no spatial neighbourhood) + LSTM (ablation).
6. `cnn_lstm` — reference architecture of the project plan.

All candidates share seed, data, loss and early stopping. **Selection rule:** the published
model is the CNN-RNN candidate (`cnn_lstm` or `convlstm`, the plan's committed family) with the
lowest validation Poisson NLL. The other candidates are reported as references; if one of them
beats the selected model, that result is reported, not hidden. The test partition is evaluated
once, after selection, for every candidate.

## 6. Error measure E and M-05

* **Primary E:** mean absolute error of total events per district × subperiod (43 × 8 values)
  on the test family-year. `M-05 = (E_B0 − E_model) / E_B0 × 100`. If `E_B0 = 0`, M-05 is
  reported as not computable.
* Secondary (reported, not used for M-05): cell-level MAE and mean Poisson deviance of located
  counts (predictions floored at 1e-3), and capture@10 % (share of test events inside the 10 % of
  cells ranked highest).

## 7. Indicator, index and levels (frozen before test)

* `indicator_value` = `λ / days of that day type × 365 / max(area_km2, 0.1)`: annualised expected
  recorded pedestrian collisions per km² for that subperiod.
* `risk_index` (0–100) = percentile rank of `indicator_value` in the frozen reference distribution
  of all valid cell × subperiod estimates of the training years (one distribution per
  representation: cell, district).
* Levels: low < 40, medium 40 to < 70, high ≥ 70 (`levels-v1`).
* District value = area-weighted mean of cell `λ` density (counts aggregated first, never labels).

## 8. Reproducibility (M-04, HT-02 tolerance)

Re-running a config with the same dataset manifest, code commit and seed must reproduce the
selected variant and the error measures within 1e-6 absolute (deterministic CPU algorithms).
`tests/metrics/m04_reproducibility.py` checks the published indicator values (≤ 1 % relative,
100 % unit/period/level match).
