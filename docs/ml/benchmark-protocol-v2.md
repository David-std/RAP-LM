# Benchmark protocol v2 — preregistered second iteration

**Status:** preregistered on 2026-11-22, committed **before** any v2 training or test evaluation.
**Why a v2:** the v1 all-severity backtest did not beat the historical average on the primary error E
(M-05 = −6.29 %). Changing the v1 metric, split or model after seeing that result is not allowed. v2 is
a new, declared iteration with the changes below fixed in advance; its result is reported as obtained,
together with v1, and labelled as a second look at the same test partitions (the test years were
already evaluated once by v1, which must be disclosed whenever v2 is cited).

## Unchanged from v1

Target, fusion, grid, tensors, observation model, partitions (main: train ≤ 2022, validation ONSV 2023,
test ONSV 2024; backtest: train 2011–2015, validation CENACOM 2016, test CENACOM Jan–Jun 2017), primary
error E (district × subperiod MAE), secondary measures, historical-average baseline, index and
thresholds `levels-v1`.

## Changes fixed in advance

1. **Selection criterion aligned with E.** v1 selected by validation Poisson NLL, but M-05 is defined on
   E. v2 selects by **validation E** (district × subperiod MAE on the validation family-year).
2. **Hyperparameter search on validation only.** For each CNN-RNN family (`cnn_lstm`, `convlstm`):
   hidden ∈ {16, 32}, dropout ∈ {0.1, 0.3}, learning rate ∈ {0.003, 0.01}; weight decay 1e-4,
   300 epochs max, patience 40, early stopping on validation NLL (training-loss proxy), seed 20261122.
   16 configurations per run. The test partition is not read during the search.
3. **Seed ensemble.** The selected configuration is retrained with seeds 1–5 and the five intensity
   surfaces are averaged (mean of λ). Ensembles reduce variance of a small-data network; this is
   declared here, not chosen after testing.
4. **Single test evaluation.** After selection, the ensemble and the historical average are evaluated
   once on the test partition with the v1 measures. All 16 search rows and the final result are stored.

## Decision rule for publication

The published run stays v1 unless v2 improves **validation E** over v1; publication never depends on
the test result. Whatever M-05 v2 yields on test is reported, including if it is worse than v1.

## Evidence

`ml/fused/search.py`, configs `ml/configs/v2-*.json`, outputs `artifacts/runs/*-v2/` with
`search.json` (all configurations), `metrics.json` and run manifest; summary in
`evidence/benchmarking/`.

## Amendment A1 (2026-11-22, before any v2 search finished and before any v2 test evaluation)

A partial v2 search (4 of 16 configurations, validation only) was interrupted by the host (out of
memory) and is discarded. Before restarting, two changes are fixed:

1. **Dataset `fused-v1.1.0`** (decision D-10). It adds eight OSM proxies of exposure and road environment
   named by the plan (Guo et al., 2024; Hu et al., 2024): commerce, education and health POIs, mapped
   crossings, traffic signals, footway length, arterial length (traffic-volume proxy) and collector
   length. It also adds collision subtype and severity to each event for the historical record. Target,
   fusion, grid, partitions and baseline are unchanged.
2. **High-level classification errors** (defined in plan v1.6): for each test family-year, TP, FP, FN,
   precision and recall of the "high" level for the model and the historical average, on the frozen
   common scale (`ml/fused/classification.py`). They are reported, not used for selection.

Selection (validation E), ensemble, single test evaluation and the publication rule stay as above.
v1 runs were evaluated with the same classification code for comparison; that computation uses
already frozen v1 models and does not change them.

## Amendment A2 (2026-11-23, before any v3 training and before any v3 test evaluation)

Iteration v3 changes only the data; method, search space, seeds, selection rule, ensemble, measures,
thresholds and partitions stay exactly as in v2.

1. **Dataset `fused-v1.2.0`** (decision D-12).
   - Resident population of the period's own year instead of a fixed 2020 surface: WorldPop R2025A
     2015–2025 (annual, constrained, 1 km), chained to 2011–2014 with each cell's relative change in the
     WorldPop 2000–2020 annual series. Population is exposure known at estimation time, not an outcome.
   - Vehicle type (9 classes) and transport service (4 classes) of every event, read back from the raw
     CENACOM chapter 100 microdata (edition-specific code lists) and the ONSV vehicle register. They feed
     the historical breakdown and the street corridors only, not the network input.
2. **Publication rule.** v3 replaces v2 only if it improves **validation E** over v2 (0.5736). The test
   partitions (ONSV 2024 and CENACOM January–June 2017) have now been evaluated by v1 and v2; any v3 test
   figure is a third look and is reported as such, whether better or worse.
3. **Reproducibility.** M-04 is measured again by retraining the published configuration from scratch.

Configs `ml/configs/v3-main.json` and `ml/configs/v3-backtest-2017.json` differ from the v2 configs only
in `run_id` and description.
