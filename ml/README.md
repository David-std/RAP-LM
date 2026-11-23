# Machine learning

## `ml/fused`: published model (WBS 3.1.2, 3.2.2, 3.2.3, 4.4)

| Module | Purpose |
|---|---|
| `tensors.py` | Tensor contract `[T, C, H, W]` per year, causal inputs (year t sees observations of t-1), annual population, targets per source, record breakdown (subtype, severity, vehicle, service, recorded factors) |
| `model.py` | CNN-RNN variants (ConvLSTM, published; CNN-LSTM, plan reference), Poisson GLM and ablations with a shared multi-source Poisson observation model |
| `train.py` | Training loop on CPU or CUDA, v1 benchmark, historical-average baseline |
| `search.py` | Protocol v2: validation search, 5-seed ensemble, single test evaluation; context-ablation arm |
| `classification.py` | High-level false positives and negatives on the frozen common scale |
| `indicators.py` | Expected severity and exposure-adjusted ratio |
| `export.py` | Deterministic `results.csv` for publication; refuses a later dataset whose inputs differ from training |
| `explain.py` | Expected vs observed per year, occlusion attribution, district what-if, model card |
| `saliency.py` | Grad-CAM (HiResCAM variant) on the ConvLSTM hidden states per district and top cells |
| `forecast.py` | One-step-ahead forecast of the year after the last observed one, with the ensemble range |

Configurations live in `ml/configs/`; protocols in `docs/ml/`. The full v3 sequence is in the root `README.md`.
Recorded factors (speed, signage, lighting, alcohol, conduct) are never network inputs: they are noted after
the collision, so using them would leak the outcome.

## `ml/datasets`: analytical contracts (P3)

Model-independent target and split contracts from the feature and target contract stage
(`docs/data/feature-target-contract.md`), kept with their tests.
