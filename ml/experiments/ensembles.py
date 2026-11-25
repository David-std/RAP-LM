"""V8: larger and mixed ensembles, trained once; members saved for validation-only selection.

Fold configs are the published v4 ones. Member pool per fold:
- the two best validation configurations of each variant in the fold's own search
  (metrics.json), ten seeds each (seeds 1-10; seeds 1-5 of the selected configuration
  reproduce the published ensemble).
Every member's expected district totals and latent intensity are stored; selection
of the ensemble happens in ``ensemble_select.py`` on validation years only.
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

FOLDS = {
    "onsv": ("v4-main.json", "fused-cnnlstm-2026.11-v4"),
    "cenacom": ("v4-backtest-2017.json", "fused-cnnlstm-backtest-2017-v4"),
}
SEEDS = tuple(range(1, 11))


def pool(run: Path) -> list[dict]:
    search = json.loads((run / "metrics.json").read_text(encoding="utf-8"))["search"]
    out, seen = [], set()
    for variant in ("convlstm", "cnn_lstm"):
        rows = sorted(
            (r for r in search if r["variant"] == variant), key=lambda r: r["validation_E"]
        )
        for r in rows:
            # ConvLSTM ignores dropout: configurations differing only in dropout are duplicates.
            key = (variant, r["hidden"], r["lr"], None if variant == "convlstm" else r["dropout"])
            if key in seen:
                continue
            seen.add(key)
            out.append({k: r[k] for k in ("variant", "hidden", "dropout", "lr")})
            if sum(1 for c in out if c["variant"] == variant) == 2:
                break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("artifacts/datasets/fused-v1.4.0"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--folds", default="onsv,cenacom")
    args = ap.parse_args()
    for fold in args.folds.split(","):
        cfg_name, run = FOLDS[fold]
        cfg = json.loads((Path("ml/configs") / cfg_name).read_text(encoding="utf-8"))
        cfg["device"] = "cuda"
        t = load_dataset(args.dataset, cfg["years"])
        out = args.out / fold
        out.mkdir(parents=True, exist_ok=True)
        configs = pool(Path("artifacts/runs") / run)
        (out / "pool.json").write_text(json.dumps(configs, indent=2), encoding="utf-8")
        for ci, conf in enumerate(configs):
            for seed in SEEDS:
                path = out / f"c{ci}_s{seed}.npz"
                if path.exists():
                    continue
                start = time.perf_counter()
                c = dict(
                    cfg, hidden=conf["hidden"], dropout=conf["dropout"], lr=conf["lr"], seed=seed
                )
                model, info = fit(t, c, conf["variant"])
                p = predict(model, t)
                np.savez_compressed(
                    path,
                    mu_cell=p["mu_cell"].astype(np.float32),
                    mu_district_total=p["mu_district_total"].astype(np.float32),
                    best_epoch=info["best_epoch"],
                )
                print(
                    fold,
                    ci,
                    conf,
                    seed,
                    info["best_epoch"],
                    round(time.perf_counter() - start, 1),
                    flush=True,
                )
                del model
                torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
