# V8: larger and mixed ensembles (fixed before scoring)

Development branch only. Dataset fused-v1.4.0, splits, target and M-05 unchanged.

## Motivation

v7 showed that in ONSV 2024 the published v4 is close to the Poisson noise floor of
the district x subperiod MAE (achieved +6.3 %, approximate maximum +6.7 %). The
remaining room is variance reduction: more members and model averaging across the
two CNN-RNN variants, plus the convex combination with the historical average.

## Member pool (ml/experiments/ensembles.py)

Per fold, the two best validation configurations of each variant in the fold's
own v4 search (ConvLSTM duplicates that differ only in dropout are skipped),
seeds 1-10 each, same training rule as v4 (validation NLL checkpoint).

## Candidate ensembles (mean of member expectations)

- A: configuration 0 (the published one), seeds 1-5. Must reproduce v4 validation.
- B: configuration 0, seeds 1-10.
- C: best configuration of each variant, seeds 1-10 each (20 members).
- D: all four configurations, seeds 1-10 (40 members).
Each also with a convex weight on the historical average, w in 0..1 by .05,
chosen on the validation year.

## Selection and test

Select the candidate (with or without combination) with the lowest validation
district x subperiod MAE; ties go to the smaller ensemble. Report validation cell-year
AUC, average precision and capture as secondary measures. Score the test year once
for A and for the selected candidate, and report every candidate's validation scores.
