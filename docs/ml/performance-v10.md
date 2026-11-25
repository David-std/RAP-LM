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
