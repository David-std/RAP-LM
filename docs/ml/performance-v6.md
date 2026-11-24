# V6: hierarchical intensity and source-specific observation

Development-only follow-up to v5. Scope remains latent relative all-severity pedestrian
collision intensity, anchored by historical CENACOM observations. ONSV is a fatal-only
observation source; its multiplier cannot be interpreted as a calibrated fatality probability
because the source periods do not overlap. No model publication, no test-year evaluation,
no metric redefinition. Existing validation folds ONSV 2023 and CENACOM 2016 only.
The existing coverage and located-share convention remains retrospective.

Goal: investigate a substantial, not marginal, improvement. Aspirational screening
threshold >=10% district MAE improvement against historical average in BOTH folds,
and improvement over v5 E0 in both without loss of >2 percentage points in top-10% capture.
This is a research gate, not a change to M-05. No claim of independent validation.
If a candidate passes, repeat with five seeds and earlier chronological development folds
before any frozen final evaluation. The same years are repeatedly inspected; report all arms.

Fixed arms, same GPU, seed 20261122, train-only population normalisation, 200 epochs,
patience 35, Adam .003, 32 channels:
H0: matching ConvLSTM control with per-source scalar observation factors.
H1: H0 + ridge-regularised learned district-by-band log-intensity effect, projected
by cell/district overlap; not a geocoded observation. This models persistent district
heterogeneity not captured by urban proxies, but may also reflect reporting biases.
H2: H0 + source-1 bounded band-specific observation multiplier.
H3: H1 + H2.
H4: H3 + equal weighting of per-event source NLLs (only covered source-years).
Regularisation .03 on mean squared district and band effects. All arms select
checkpoint on validation likelihood. Compare same original district and cell MAE,
Poisson deviance and annual top-10%-cell capture. Do not compare likelihoods across
different objectives as the main metric. Run all ten fits; preserve negative results.

## Quality-aware follow-up Q (fixed before execution)

The data audit identifies exactly 8,005 CENACOM records in 2011-2014 whose only
district reference is the station. 2015-2017 instead use occurrence districts.
Removing these records would lose all-severity temporal information. Model them
with a mixture of district likelihood and city-total likelihood, retaining their
counts without asserting street/cell positions. Station flags are metadata, not
derived from validation labels. The CENACOM 2016 and ONSV 2023 validation labels
use actual occurrence district. Q1 uses district weight .25, city weight .75;
Q2 uses city-only proxy loss and removes spatial station-lag variation (retain
a city-average feature); Q3 uses Q1 weighting plus proxy-lag suppression and
causal multi-year history pooled by source, band, and exposure, excluding
station years from spatial history; Q4 uses original district likelihood but
the Q3 feature representation to isolate input changes. No future-year outcomes,
no test evaluation; same seed, E0 architecture, NLL checkpoint rule, budget and
research gate. Historical averages and metrics remain unchanged. Note that
earlier true location history is short; new features may therefore not help.
