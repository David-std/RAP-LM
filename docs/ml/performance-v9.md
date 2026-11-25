# V9: long-memory history input (fixed before training)

Development branch only. Dataset, splits, target and evaluation unchanged.

## Motivation

On the all-severity test (CENACOM 2017) the published network ranks cells no better
than the historical average (AUC 0.978 vs 0.976, capture in 20% of cells 94.4% vs
94.8%). The historical average uses every earlier covered year; the network only
reads the previous year. The spatial pattern is very persistent (district totals
2016 vs 2017 correlate at 0.97), so long memory matters most there.

## Change

Add, per source, two causal input channels for year t: log1p of the mean
coverage-adjusted cell rate and of the mean district density over all covered years
before t. Same ConvLSTM configuration as v4 (hidden 32, lr .003), validation NLL
checkpoint, seeds 1-10, both folds (ml/experiments/long_memory.py).

## Selection and test

Candidates: v9 ensembles of seeds 1-5 and 1-10, each alone and combined with the
historical average (weight chosen on validation average precision). The v8 pool is
the reference. Choose on validation average precision of the cell-year ranking; the
district MAE is reported alongside. Test years scored once for the chosen candidate.
