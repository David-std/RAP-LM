# Performance experiment: validation-only screening (v5)

Status: fixed before execution, isolated from the published v4 run.
Base: def0df5. Dataset: fused-v1.4.0, unchanged. No production export, deployment,
tag, database or scope change. Target: latent intensity of pedestrian collisions
of all severities, not fatal collisions alone. CENACOM is the all-severity
reference; ONSV is a severity-truncated observation with its existing source factor.

## Evaluation

Two development folds, existing chronological partitions:
- ONSV: train CENACOM 2011-2017 and ONSV 2021-2022, validate ONSV 2023.
- CENACOM: train 2011-2015, validate 2016.

No 2024 or 2017 test outcomes in this screening (2017 remains a legitimate
training year in the main fold). These validation years were used previously;
this is exploratory development, not independent confirmation. Population
normalisation uses only training years. Static present-day urban covariates
remain retrospective proxies, not verified historical snapshots.
Keep the existing observation coverage/located-share convention for comparable
retrospective scores; it does not establish fully prospective forecast accuracy.

## Fixed arms

All use ConvLSTM, hidden=32, Adam lr=.003, weight decay=.0001, seed=20261122,
max 200 epochs, patience 35 (E0 uses the existing NLL early stopping).
E0: train-only population normalisation, original inputs and NLL.
E1: E0 plus effective shared feature-channel dropout .1, validation MAE checkpoint
selection and ReduceLROnPlateau on validation MAE (factor .5, patience 12).
E2: E1 plus causal previous-year cell and district-density inputs per day/band,
separate by source, with existing observed flags.
E3: E2 plus district-total smooth L1 loss (beta .5), weight 2, alongside the
original per-event Poisson objective. The district term is calculated only
on training-covered family-years. Expected district totals are coherent
aggregations of the latent cell intensity, scaled to each observation family.
E4: E3 plus a multiplicative historical offset. Only earlier CENACOM data
(all severities) define this offset; geolocated counts are retained and
district-only counts are distributed by cell/district overlap area as a
model prior, NEVER as observed cell labels. Average coverage-adjusted
prior years, positive floor .002. At no history, .02 per valid cell/band.
ONSv observations remain source-specific supervision. No fatal-only offset.

Primary score district x subperiod MAE, plus cell MAE, deviance, annual
top-10%-cell capture. Compare every arm with the historical average and
the published v4 validation scores. Screening uses one seed, not a claim
of ensemble superiority. Advance only arms improving E0 across both folds
without materially worsening capture (2 percentage points maximum).
No test-score selection or publication. Next step: repeat finalist with
five seeds and a locked protocol; use rolling development folds if needed.
Negative binomial: deferred until training-only dispersion diagnostics,
because fractional allocated cells are not integer observations.

## External data gate

ONSV open data https://www.onsv.gob.pe/datosabiertos provides preliminary
2021-2025 fatal records; existing source manifest already identifies the file.
Fusion report excluded 55 2025 events because coverage was not closed.
Qualify new snapshot and exact observation interval separately; do not treat
missing months as zero. External validation is fatal-only, not evidence of
all-severity risk accuracy. No changes to the target. Do not inspect 2025
outcomes for candidate selection. Require source hash, date coverage,
geocoding and duplication checks, and a frozen candidate first.

References:
- Shi et al. (2015), Convolutional LSTM Network, https://arxiv.org/abs/1506.04214
- PyTorch Adam, https://docs.pytorch.org/docs/stable/generated/torch.optim.Adam.html
- PyTorch ReduceLROnPlateau, https://docs.pytorch.org/docs/stable/generated/torch.optim.lr_scheduler.ReduceLROnPlateau.html
- Road crash excess zeros/dispersion: https://www.sciencedirect.com/science/article/pii/S0001457524002860
- Existing docs/ml/benchmark-protocol-v2.md and v4 run manifests.

## Follow-up: isolate effects (fixed after first screen, before new runs)

The ten first-stage fits did not pass the two-fold E0 gate. E1/E2 selected epoch 1 in the ONSV fold and stopped prematurely; E3/E4 did not improve both MAE and spatial capture. This follow-up is development-only and does not inspect either test fold.

Use the identical E0 seeds, splits, train-only normalisation, NLL, early stopping and training budget. R0 = historical residual offset only; R1 = day/band lag channels only; R2 = both. No new dropout or MAE scheduler. Compare against E0 and the historical average, with the original two-fold gate unchanged. Do not select by test results or deploy automatically. The first-stage results remain preserved.
