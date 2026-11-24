# V9 results: long-memory history input

Protocol: docs/ml/performance-v9.md. 20 members (10 seeds x 2 folds), GPU. Selection on
validation average precision; test scored once.

| Test | Measure | Published v4 | Selected v9 | Historical average |
|---|---|---:|---:|---:|
| CENACOM 2017 (all severities), v9-10 + historical, weight 0.35 | AUC | 0.978 | 0.981 | 0.976 |
| | Average precision | 0.887 | 0.900 | 0.887 |
| | Capture, 10% of cells | 78.1% | 79.4% | 78.3% |
| | Capture, 20% of cells | 94.4% | 94.8% | 94.8% |
| | District MAE vs historical | -3.28% | -1.68% | - |
| ONSV 2024 (fatal), v9-10 | AUC | 0.927 | 0.927 | 0.785 |
| | Capture, 20% of cells | 92.4% | 90.6% | 68.8% |
| | District MAE vs historical | +6.29% | +6.12% | - |

The long-memory input brings the all-severity ranking to or slightly above the historical
average, but the gain is about one point and ONSV does not improve. The persistent
all-severity pattern leaves little room above the historical average.
