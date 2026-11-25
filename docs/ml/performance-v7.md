# V7: year-specific CENACOM recording factor (fixed before execution)

Development branch only. Published v4, dataset fused-v1.4.0, target and M-05 unchanged.

## Finding that motivates it

The raw CENACOM 2017 edition (595-Modulo1233) records, for Lima province, about
710 accidents per month in 2016 and about 1,230 per month in January-June 2017
(all accident classes, same edition, same census instrument). The coverage
window (January-June 2017, cover 0.5) is correct. The jump is a recording-volume
change: pedestrian events follow it (1,629 in half of 2017 versus 1,875 in all of
2016). In the backtest fold both the v4 ensemble (928 expected) and the historical
average (966) underpredict 2017 by a factor of about 1.75, so the -3.28% result
mainly measures that break; with each method rescaled to the observed total the
gap is 1.78 versus 1.74 MAE. Nothing observed up to 2016 anticipates the break.

In the main fold CENACOM 2017 is a training year and shares one recording factor
with 2011-2016, so the latent intensity must absorb the break.

## Arms

Same v4 selected configuration (ConvLSTM, hidden 32, dropout .1, lr .003, weight
decay .0001, 300 epochs, patience 40, validation NLL checkpoint), dataset, splits
and five ensemble seeds 1-5. Ensemble = mean of member expectations.

- P0: control, original model (must reproduce v4 validation scores).
- P1: P0 plus one learned log recording factor per CENACOM training year
  (2011 fixed at 0), L2 penalty .01 on the factors. A year outside training
  uses the factor of the last CENACOM training year.
- P2: P0 plus a single learned log factor for CENACOM 2017 only.

## Rule

Select on validation only (ONSV 2023 district x subperiod MAE of the ensemble).
An arm advances if it beats P0 on that MAE without losing more than 2 points of
top-10% capture. The test years (ONSV 2024, CENACOM 2017) are then evaluated
once for P0 and the advancing arm and every result is reported. For the backtest
fold P2 is identical to P0 (2017 is not a training year there), and P1 uses the
2016 factor for 2017, so no backtest gain is expected from the factor itself.
