# V8 results

Protocol: docs/ml/performance-v8.md. 80 members (4 configurations x 10 seeds x 2 folds), GPU.
Selection on validation district x subperiod MAE; test scored once.

| Fold | Selected | Validation | Test, published v4 | Test, selected |
|---|---|---:|---:|---:|
| ONSV (2023 / 2024) | v4 ensemble (A) + historical average, weight 0.65 | +6.44% | +6.29% | +6.90% |
| CENACOM (2016 / 2017) | 40 members (D) + historical average, weight 0.75 | +9.02% | -3.28% | -2.76% |

ONSV 2024 test, selected: AUC 0.929 (v4 0.927), average precision 0.377 (0.360),
capture in 20% of cells 91.5% (92.4%). Larger ensembles did not improve ONSV validation
(A +4.66%, B +4.53%, C +3.16%, D +3.34% without combination). In the CENACOM fold,
candidate A is the ConvLSTM configuration, not the published CNN-LSTM backtest, so the
reference for the published backtest is the v4 figure (-3.28%).
