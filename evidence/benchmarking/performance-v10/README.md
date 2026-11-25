# V10-V12 development results

Protocol: docs/ml/performance-v10.md (with amendment A1). Five seeds per candidate, GPU.
Corrected metrics (tied scores grouped). Years 2017 and 2024 not used.

## Valid folds for cell ranking (A1: fixed 150 epochs, evaluated year unused)

| D2b, CENACOM 2016 (all severities) | Historical | C0 | C1 | C2 | C3 | C4 |
|---|---:|---:|---:|---:|---:|---:|
| District x subperiod MAE | 1.863 | 1.714 | 1.745 | 1.748 | 1.880 | 1.854 |
| District Spearman | 0.952 | 0.968 | 0.969 | 0.961 | 0.938 | 0.943 |
| Cell AUC, all located | 0.951 | 0.981 | 0.981 | 0.981 | 0.980 | 0.981 |
| Cell AP, all located | 0.855 | 0.903 | 0.905 | 0.902 | 0.898 | 0.900 |
| Capture 20 %, all located | 0.926 | 0.950 | 0.950 | 0.946 | 0.948 | 0.945 |
| Cell AP, intersections only | 0.350 | 0.360 | 0.363 | 0.371 | 0.364 | 0.365 |

| D3b, ONSV 2023 (fatal) | Historical | C0 | C1 | C2 | C3 | C4 |
|---|---:|---:|---:|---:|---:|---:|
| District x subperiod MAE | 0.603 | 0.572 | 0.579 | 0.573 | 0.606 | 0.583 |
| Cell AUC | 0.732 | 0.934 | 0.936 | 0.935 | 0.937 | 0.936 |
| Cell AP | 0.254 | 0.431 | 0.420 | 0.428 | 0.432 | 0.433 |

Selection score (D2b weight 2, D3b weight 1; mean of relative gains in cell AP and
district MAE): C0 17.0, C2 16.1, C1 15.6, C4 14.2, C3 13.0. C0, the published
architecture, is selected. Neither the multi-horizon memory nor the two-head
architecture improves on it once the network is trained through the last located year.

## First run (D1-D3, early stopping on the year before evaluation)

Valid at district level only (see A1). District MAE: 2015 historical 2.153, C0 1.899,
C4 1.924, C2 1.975; 2016 historical 1.863, C2 1.841, C3 1.852, C4 1.855, C0 2.024.

## Final scoring of C0 (neural network alone, once; years consulted before)

| Measure | CENACOM 2017 historical | CENACOM 2017 C0 | ONSV 2024 historical | ONSV 2024 C0 |
|---|---:|---:|---:|---:|
| District x subperiod MAE | 2.380 | 2.459 (-3.3 %) | 0.607 | 0.569 (+6.2 %) |
| Cell AUC, all located | 0.976 | 0.981 | 0.785 | 0.926 |
| Cell AP, all located | 0.887 | 0.898 | 0.294 | 0.355 |
| Capture 10 %, all located | 0.783 | 0.787 | 0.618 | 0.683 |
| Capture 20 %, all located | 0.948 | 0.950 | 0.714 | 0.897 |
| Cell AP, precise only | 0.406 | 0.419 | 0.294 | 0.355 |
| Capture 10 %, precise only | 0.810 | 0.852 | 0.618 | 0.683 |

Without combining with the historical average, the network ranks cells better than the
historical average in both test years and every ranking measure. The 2017 district MAE
remains below the reference because of the recording increase of the 2017 edition.
