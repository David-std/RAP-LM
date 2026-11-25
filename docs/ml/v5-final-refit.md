# v5: final refit on every observed year (prepared, not published)

Run `fused-cnnlstm-2026.11-v5`, config `ml/configs/v5-final.json`, code `f548f45`
(clean tree), dataset fused-v1.4.0. Same architecture as v4 (ConvLSTM, hidden 32,
lr .003, ensemble of 5 seeds), selected in the v10 development folds (C0). Trained on
CENACOM 2011-2017 and ONSV 2021-2024 for a fixed 150 epochs (the training length fixed
in amendment A1); no year is held out. Published production model remains v4.

## Evidence that belongs to v5 and evidence that does not

v5 has seen every year up to 2024, so its 2011-2024 estimates are in-sample
reconstructions, not predictions. Out-of-sample evidence for this procedure comes from
models trained the same way without the evaluated year:

- docs/ml/performance-v10.md and evidence/benchmarking/performance-v10 (folds D2b,
  D3b, and the single scoring T1f, T2f; 2017 and 2024 were consulted before);
- evidence/benchmarking/performance-v14 (one to three years ahead, chained).

## Coherence checks (v5 against v4)

| Check | v4 | v5 |
|---|---:|---:|
| Grad-CAM units explained | 43 districts, 400 cells | 43 districts, 400 cells |
| Grad-CAM cells whose most influential cell is the cell itself | 93.8 % | 95.0 % |
| 2024 cell levels: low / medium / high | 67.7 / 18.4 / 13.9 % | 64.4 / 19.1 / 16.5 % |
| 2024 cell index, correlation v4-v5 (23,192 cell-subperiods) | | 0.968, mean abs. diff. 5.2 |
| District forecast index, correlation v4-v5, 2025 / 2026 / 2027 | | 0.936 / 0.934 / 0.932 |
| Mean ensemble range of the district index, 2025 / 2026 / 2027 | 9.5 / 10.0 / 10.6 | 8.8 / 10.1 / 11.5 |
| Expected collisions in the 43 districts (sum of subperiods), 2025 / 2026 / 2027 | 209 / 205 / 199 | 264 / 267 / 266 |
| ONSV recording factor relative to CENACOM | 0.827 | 0.856 |

The forecast chain reproduces the in-sample years exactly (gap 0.0). The Grad-CAM run
was interrupted once at 340 cells (memory) and rerun to completion. The higher expected
level and the flat 2025-2027 trend come from training with ONSV 2023-2024 (232 and 233
fatal pedestrian crashes, the highest of the series); v4 extrapolated a decline from
2021-2022. Thresholds keep levels-v1; the reference distribution now includes every
training year, so the high level covers 16.5 % of the 2024 cell-subperiods instead of
13.9 %. Street corridors are not recomputed (they depend only on the dataset, except
their mean risk index).

Before publication: corridors with v5 results, publisher and analyst layers, model-card
reports (prioritisation and noise ceiling replaced by the v10/V14 evidence), metrics,
E2E walkthroughs.

## Proposed change request D-17 (draft, pending PM approval)

M-05 keeps its original measurement as history. Proposed replacement, all-severity
evaluation first and every result reported, including unfavourable ones:

| Dimension | Measure | Comparison |
|---|---|---|
| Prioritisation | Cell-year average precision and AUC | Relative to the historical average |
| Territorial usefulness | Capture in the top 5 %, 10 % and 20 % of cells; precise-location stratum | Relative to the historical average and to random |
| Added value of the network | Relative improvement of the above over the historical average | Must be positive in the all-severity test |
| Quantitative accuracy | District x subperiod MAE and Poisson deviance (historical average with zero predictions reported separately) | Relative to the historical average |
| Temporal generalisation | The same measures at one, two and three years ahead (V14) | Relative to the historical average of the years up to the origin |
