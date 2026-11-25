# Validation-only performance screening: results

18 fits; all retained. No test evaluation or production export.

| Arm | ONSV 2023 MAE | Improvement | CENACOM 2016 MAE | Improvement |
|---|---:|---:|---:|---:|
| E0 | 0.57036 | +5.44% | 1.78457 | +4.23% |
| E1 | 1.12856 | -87.10% | 1.81138 | +2.79% |
| E2 | 1.12602 | -86.67% | 1.78274 | +4.33% |
| E3 | 0.58201 | +3.51% | 1.80391 | +3.19% |
| E4 | 0.57337 | +4.94% | 1.78418 | +4.25% |
| R0 | 0.59920 | +0.66% | 2.00445 | -7.57% |
| R1 | 0.58005 | +3.84% | 1.86570 | -0.13% |
| R2 | 0.60607 | -0.48% | 1.95433 | -4.88% |
| N0 | 0.57383 | +4.87% | 1.81419 | +2.64% |

## Decision

No candidate passes the preregistered two-fold E0 gate. Keep v4 published. E0 is a one-seed control, not a replacement for the five-member v4 ensemble. E1/E2 checkpointed at epoch 1 on ONSV: the compound early-stopping/scheduler change is not viable under this budget. Residual-only and band-history-only arms fail to improve both folds. N0 yields alpha near zero and does not beat E0.

ONSV 2025 cannot be treated as a closed Lima year; the downloaded workbook matches the previous snapshot. The raw 2025 nationwide observed range is January 1 to December 30, but Lima province only January 4 to April 2. These are observed dates, not certified coverage endpoints. No all-severity validation claim can be made from ONSV.

Tests: 36 passed in the targeted model/experimental suite, including five new tests; Ruff passed. All experiments use the existing retrospective observation operator. Future evaluation requires a locked model, independently qualified source coverage and a prospectively available covariate/coverage policy.
