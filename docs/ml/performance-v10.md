# V10-V12: corrected evaluation, multi-horizon memory and two-head CNN-RNN (fixed before training)

Development branch only. Dataset fused-v1.4.0, target (latent intensity of pedestrian
collisions of all severities) and published v4 unchanged.

## Why

An external review of v7-v9 found: (1) the "noise ceiling" assumed the v4 intensity
was true, so it is not a bound; (2) cell capture is measured on the mass that could be
placed on the grid, half of it spread along streets; (3) average precision broke ties
by cell order; (4) the v9 winner was 35 % network, 65 % historical average; (5) the
2017 and 2024 test years have been consulted many times. All-severity evaluation is
the primary one.

## Corrected evaluation (V10)

- Average precision with tied scores grouped (step-wise definition, as scikit-learn);
  capture in the top 5/10/20 % with ties shared proportionally; AUC by ranks.
- Strata. District-year: all records of the source (43 districts; Spearman, capture
  of the top 20 % districts, MAE, Poisson deviance). Cell-year, all located mass
  (intersection, street allocation, ONSV point). Cell-year, precise only
  (CENACOM intersections; ONSV points). Positive cell: at least 0.5 located events.
- Inputs normalised with training years only.
- Development folds never evaluate the year used for early stopping:
  D1 train CENACOM 2011-2013, stop 2014, evaluate 2015;
  D2 train 2011-2014, stop 2015, evaluate 2016;
  D3 train CENACOM 2011-2017 and ONSV 2021, stop 2022, evaluate ONSV 2023.
  CENACOM has located events only from 2015, so D1/D2 cell strata are the 2015
  and 2016 records.
- References: historical average (plan baseline) and an exponentially decayed
  historical average (half-life 2 years), reported as a stronger reference.

## Candidates (ConvLSTM, hidden 32, lr .003, seeds 1-5, validation NLL early stopping)

- C0: v4 inputs (control).
- C1: C0 + mean of all earlier covered years (v9 memory).
- C2: C0 + multi-horizon memory per source: mean of the last 3 covered years, mean of
  all earlier covered years, exponentially decayed mean (half-life 2 years), each for
  cell rate and district density, plus the number of covered years. Years without
  coverage are masked, never counted as zero.
- C3: two-head CNN-RNN with C0 inputs. A shared ConvLSTM feeds a district magnitude
  head N(d,t,k) (district-pooled features, two dense layers) and a spatial head that
  gives the share of each cell within its district p(i|d,t,k) (softmax over the cells
  of the district weighted by area share). Cell intensity is the sum over districts of
  N times p, so cell estimates add up to the district magnitude. Same Poisson
  likelihood and observation operator as v4.
- C4: two-head CNN-RNN with C2 inputs.

## Selection

Score of a candidate = mean over D1 and D2 of the relative improvement over the
historical average in (a) cell-year average precision, all located mass, and
(b) district MAE, averaged. Constraint: D3 cell-year average precision not lower than
C0's by more than 0.02. The best candidate is reported with its neural-only result.
Only then: transfer learning (V13), multi-year forecast evaluation (V14), and a single
scoring of 2017 and 2024 for the final candidate, labelled as previously consulted years.

## Amendment A1 (after the first development run, before any new training)

D1/D2 cannot judge cell-level ranking: CENACOM has located events only from 2015, so
the D2 network trains on 2011-2014 with no cell supervision (2015 only stops training)
while the historical average uses 2015, and in D1 neither has located history. In D3
ONSV enters training with one year, so its recording factor is poorly identified.
District-level results of D1-D3 stay valid and are reported.

Added folds with a fixed training length (150 epochs, the median best epoch of the v4
members) instead of early stopping, so the evaluated year stays unused:
D2b train CENACOM 2011-2015, evaluate 2016; D3b train CENACOM 2011-2017 and ONSV
2021-2022, evaluate ONSV 2023. Same candidates and seeds. Selection: mean over D2b
(all severities, weight 2) and D3b (weight 1) of the relative gains over the historical
average in cell AP (all located) and district MAE; precise-location AP reported.

## Final scoring (selected candidate C0, once)

T1f train CENACOM 2011-2016, evaluate 2017; T2f train CENACOM and ONSV 2021-2023,
evaluate ONSV 2024. Fixed 150 epochs, seeds 1-5. Both years were consulted in earlier
iterations; they are reported as such, not as untouched tests.

## Findings before A2 (no training involved)

- Poisson deviance, ONSV 2024: 82.5 % of the historical average's deviance comes from
  the 132 of 344 district-subperiods where it predicts exactly zero (27 of them have
  events). Excluding them: historical 1.285, C0 1.118 (-13 %); with the historical
  average floored at its smallest positive value: 1.118 vs C0 0.935 (-16 %). The raw
  -79 % reduction is not reported as a model gain. CENACOM 2017 without those units:
  historical 2.523, C0 2.730 (C0 worse).
- CENACOM 2017. Same months (January-June) of the fused Lima events: 2015 964,
  2016 963, 2017 1,629 records. Median survey expansion factor per record: 2015 2.53,
  2016 4.95, 2017 2.60; weighted annual totals oscillate between about 5,500 and
  11,700 across 2011-2017. The 2017 increase coincides with a change in the census
  sampling fraction, but neither the weighted nor the unweighted counts form a
  comparable series, so no cause is asserted. Level-free ranking measures are not
  affected; the 2017 district MAE measures an unidentifiable change of level.

## Amendment A2: ablation and multi-year horizons (V14)

Ablation on D2b and D3b, five seeds, fixed 150 epochs: A_cnn (convolution per year,
no recurrence), A_rnn (per-cell LSTM, no spatial convolution), A_noctx (C0 with every
context variable at its standardised mean), A_nohist (C0 without previous-year history).

V14: C0 trained through a last observed year (fixed 150 epochs, covariates frozen at
that year), then chained: every later year receives its history inputs from the
ensemble's estimate of the previous year, never from observations. Origins:
CENACOM 2015 -> 2016, 2017; CENACOM 2014 -> 2015, 2016, 2017; ONSV 2023 -> 2024;
ONSV 2022 -> 2023, 2024; ONSV 2021 -> 2022, 2023, 2024. Reference: historical average
of the years up to the origin only. Same district and cell measures by horizon.
