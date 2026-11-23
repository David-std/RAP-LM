# Machine learning

## `ml/fused`: published model (WBS 3.1.2, 3.2.2, 3.2.3, 4.4)

| Module | Purpose |
|---|---|
| `tensors.py` | Tensor contract `[T, C, H, W]` per year, causal inputs (year t sees observations of t-1), targets per source, breakdown by subtype and severity |
| `model.py` | CNN-LSTM reference, ConvLSTM, Poisson GLM and ablations with a shared multi-source Poisson observation model |
| `train.py` | v1 benchmark: all candidates, selection on validation, single test evaluation, historical-average baseline |
| `search.py` | v2 protocol: validation search, 5-seed ensemble, single test evaluation |
| `classification.py` | High-level false positives and negatives on the frozen common scale |
| `indicators.py` | Expected severity and exposure-adjusted ratio |
| `export.py` | Deterministic `results.csv` (frequency, severity, exposure, breakdown) for publication |
| `explain.py` | Expected vs observed per year, occlusion attribution, district what-if, model card |

Configurations live in `ml/configs/`; protocols in `docs/ml/`. Typical run:

```bash
python -m ml.fused.search --dataset artifacts/datasets/fused-v1.1.0 --config ml/configs/v2-main.json --out artifacts/runs/<run>
python -m ml.fused.classification --dataset artifacts/datasets/fused-v1.1.0 --run artifacts/runs/<run>
python -m ml.fused.export --dataset artifacts/datasets/fused-v1.1.0 --run artifacts/runs/<run>
python -m ml.fused.explain --dataset artifacts/datasets/fused-v1.1.0 --run artifacts/runs/<run>
```

## `ml/datasets`: analytical contracts (P3)

Model-independent target and split contracts from the feature and target contract stage
(`docs/data/feature-target-contract.md`), kept with their tests.
