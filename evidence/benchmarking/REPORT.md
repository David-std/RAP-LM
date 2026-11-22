# Benchmark report (HT-02, RM-01, RM-05, M-05)

Generated from `evidence/benchmarking/*.metrics.json` (copied from the run artifacts). Protocol: `docs/ml/benchmark-protocol.md`, frozen before the test evaluation. Values are reported as obtained.

## Main run (published) — test ONSV 2024

Run `fused-cnnlstm-2026.11-r1`, code `unknown`, seed 20261122, torch 2.15.0+cpu, 8 threads. Test events: 233 (224 located to cells). Selected (CNN-RNN, lowest validation NLL): **convlstm**. Reporting factor ONSV/CENACOM: 0.687.

| Alternative | Validation NLL | Test E (district×band MAE) | M-05 vs historical average | Cell deviance | Capture@10 % |
|---|---|---|---|---|---|
| Historical average (B0) | — | 0.6066 | — | 0.1156 | 62.1 % |
| CNN-LSTM (plan reference) | 4.2461 | 0.5966 | +1.65 % | 0.0671 | 58.9 % |
| ConvLSTM (Shi 2015; Hetero-ConvLSTM) **(selected)** | 4.2443 | 0.5832 | +3.85 % | 0.0655 | 60.3 % |
| CNN only (ablation) | 4.2790 | 0.6193 | -2.09 % | 0.0655 | 61.2 % |
| LSTM only (ablation) | 4.2570 | 0.6010 | +0.92 % | 0.0651 | 62.1 % |
| Poisson GLM (classic count model) | 4.4063 | 0.5620 | +7.35 % | 0.0666 | 60.7 % |

## All-severity backtest — test CENACOM Jan–Jun 2017

Run `fused-cnnlstm-backtest-2017`, code `unknown`, seed 20261122, torch 2.15.0+cpu, 8 threads. Test events: 1629 (946 located to cells). Selected (CNN-RNN, lowest validation NLL): **cnn_lstm**. Reporting factor ONSV/CENACOM: 1.000.

| Alternative | Validation NLL | Test E (district×band MAE) | M-05 vs historical average | Cell deviance | Capture@10 % |
|---|---|---|---|---|---|
| Historical average (B0) | — | 2.3798 | — | 0.0981 | 79.9 % |
| CNN-LSTM (plan reference) **(selected)** | 1.0629 | 2.5295 | -6.29 % | 0.0892 | 79.1 % |
| ConvLSTM (Shi 2015; Hetero-ConvLSTM) | 1.0701 | 2.4489 | -2.90 % | 0.0900 | 78.8 % |
| CNN only (ablation) | 1.2124 | 3.1778 | -33.53 % | 0.1129 | 76.2 % |
| LSTM only (ablation) | 1.0591 | 2.5672 | -7.87 % | 0.0882 | 79.7 % |
| Poisson GLM (classic count model) | 1.1276 | 2.6152 | -9.89 % | 0.0933 | 76.7 % |

## Reading

* Main test (2024): the selected ConvLSTM improves the primary error E by +3.85 % over the historical average (M-05 target > 0 %: met). The classic Poisson GLM obtains the lowest E (+7.35 %); the neural models are not the best on this metric. Every learned model roughly halves the cell-level Poisson deviance of the historical average.
* All-severity backtest (2017): no model beats the historical average on E (selected CNN-LSTM −6.29 %). Cell-level deviance is still lower than B0 for the CNN-RNN candidates. M-05 on the all-severity population is therefore **not met**.
* Capture of observed events in the top 10 % of cells is 1–3 points below the historical average in both tests.
* Causes to analyse (not yet verified): short training sequence (5 CENACOM years in the backtest), half-year test window, static context, and selection by validation NLL rather than by E. Changing the metric or the split after seeing these results is not allowed by the protocol; any follow-up is a new, pre-registered run.
