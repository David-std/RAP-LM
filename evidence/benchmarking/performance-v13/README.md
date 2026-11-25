# V13 pilot results: transfer learning from ten Peruvian cities

Protocol: docs/ml/performance-v13.md. 15,723 source events, 104 districts, 34,890 cells.
Five seeds per arm. Lima evaluation with the v10 corrected metrics.

| Arm | 2016 district MAE | 2016 cell AP | 2016 cell AUC | 2023 district MAE | 2023 cell AP | 2023 cell AUC |
|---|---:|---:|---:|---:|---:|---:|
| Historical average | 1.863 | 0.855 | 0.951 | 0.603 | 0.254 | 0.732 |
| A, Lima only, reduced inputs | 1.892 | 0.799 | 0.956 | 0.660 | 0.310 | 0.899 |
| B, pretrained on sources, reduced inputs | 2.006 | 0.819 | 0.961 | 0.652 | 0.314 | 0.905 |
| C0, Lima only, full inputs (v10) | 1.714 | 0.903 | 0.981 | 0.572 | 0.431 | 0.934 |

Decision: B improves the cell ranking of A slightly in both folds but worsens the 2016
district MAE, so it does not meet the adoption rule. Both reduced arms are well below C0:
dropping the Lima-only urban context costs far more than pretraining recovers (consistent
with the A_noctx ablation). A full version would require national urban context (OSM);
with the observed gains it is not pursued now.
