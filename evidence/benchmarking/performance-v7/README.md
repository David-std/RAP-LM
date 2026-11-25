# V7 results (validation only for P arms)

Protocol: docs/ml/performance-v7.md. Five-seed ensembles, ConvLSTM v4 configuration, GPU.

| Arm | ONSV 2023 MAE | Improvement vs historical | Top-10% capture |
|---|---:|---:|---:|
| P0 (control, reproduces v4 validation) | 0.57511 | +4.66% | 0.664 |
| P1 (factor per CENACOM year) | 0.57948 | +3.93% | 0.655 |
| P2 (factor for CENACOM 2017) | 0.57904 | +4.01% | 0.655 |

Historical-average capture: 0.549. Learned 2017 log factor about 0.2 (x1.22), well
below the raw x1.75 jump: the network already absorbs most of the break through its
inputs. No arm advances; test years were not scored for P arms.

## Diagnostic: CENACOM 2017 backtest

Raw edition 2017, Lima province, all accident classes: about 710 records per month in
2016 versus about 1,230 per month in January-June 2017. Pedestrian events: 1,875 (2016,
full year) and 1,629 (2017, half year). Expected 2017 counts: v4 backtest 928,
historical average 966. Both underpredict by about x1.75; the -3.28% result reflects
that recording break. Rescaling each method to the observed total gives MAE 1.78
(model) versus 1.74 (historical average).

## Post-hoc combination with the historical average

Weight on the model chosen on the validation year only, then applied once to the test year.

| Fold | Weight | Validation | Test (model only) | Test (combined) |
|---|---:|---:|---:|---:|
| ONSV (2023 / 2024) | 0.65 | +6.44% | +6.29% | +6.90% |
| CENACOM (2016 / 2017) | 0.95 | +9.28% | -3.28% | -3.06% |
