"""V9: long-memory history input (fixed before training). See docs/ml/performance-v9.md.

The published network only reads the previous year's events, while the historical
average uses every earlier covered year. This adds, per source, two causal channels
for year t: log1p of the mean coverage-adjusted cell rate and of the mean district
density over ALL covered years before t (same quantities as the existing lag-1
channels, averaged). Nothing from year t or later enters. Members are saved like v8.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from ml.fused.tensors import load_dataset
from ml.fused.train import fit, predict

FOLDS = {"onsv": "v4-main.json", "cenacom": "v4-backtest-2017.json"}
SEEDS = tuple(range(1, 11))


def add_long_memory(t):
    s_count, years = t.y_cell.shape[:2]
    area = (t.frac * t.area_km2[None]).sum(axis=(1, 2))
    extra = np.zeros((years, 2 * s_count, *t.valid.shape), np.float32)
    for s in range(s_count):
        cells, dens = [], []
        for i in range(years):
            if cells:
                extra[i, 2 * s] = np.log1p(np.mean(cells, axis=0)) * t.valid
                extra[i, 2 * s + 1] = np.log1p(np.mean(dens, axis=0)) * t.valid
            cov = t.cover[s, i].mean()
            if cov > 0:
                q = max(float(t.located[s, i]), 1e-6)
                cells.append(t.y_cell[s, i].sum(axis=0) / (cov * q))
                d = t.events_total[s, i].sum(axis=0) / cov / np.maximum(area, 1e-6)
                dens.append(np.tensordot(d, t.frac, axes=(0, 0)))
    t.X = np.concatenate([t.X, extra], axis=1)
    t.channels += [
        f"{f}_{k}"
        for f in ("cenacom", "onsv")[:s_count]
        for k in ("mean_cell_rate", "mean_district_density")
    ]
    return t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("artifacts/datasets/fused-v1.4.0"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--folds", default="cenacom,onsv")
    args = ap.parse_args()
    for fold in args.folds.split(","):
        cfg = json.loads((Path("ml/configs") / FOLDS[fold]).read_text(encoding="utf-8"))
        cfg.update(device="cuda", hidden=32, dropout=0.1, lr=0.003)
        t = add_long_memory(load_dataset(args.dataset, cfg["years"]))
        out = args.out / fold
        out.mkdir(parents=True, exist_ok=True)
        for seed in SEEDS:
            path = out / f"s{seed}.npz"
            if path.exists():
                continue
            start = time.perf_counter()
            model, info = fit(t, dict(cfg, seed=seed), "convlstm")
            p = predict(model, t)
            np.savez_compressed(
                path,
                mu_cell=p["mu_cell"].astype(np.float32),
                mu_district_total=p["mu_district_total"].astype(np.float32),
                best_epoch=info["best_epoch"],
            )
            print(fold, seed, info["best_epoch"], round(time.perf_counter() - start, 1), flush=True)
            del model
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
