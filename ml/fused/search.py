"""Benchmark v2: validation search + seed ensemble (preregistered protocol v2).

Usage::

    python -m ml.fused.search --dataset artifacts/datasets/fused-v1.0.0 \
        --config ml/configs/v2-main.json --out artifacts/runs/fused-cnnlstm-2026.11-v2

Protocol: docs/ml/benchmark-protocol-v2.md. Selection uses the **validation**
primary error E only; the test partition is evaluated once, after selection.
Outputs are compatible with ``ml.fused.export`` (estimates.npz, run_manifest.json).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import itertools
import json
import platform
import time
from pathlib import Path

import numpy as np
import torch

from ml.fused.tensors import load_dataset
from ml.fused.train import evaluate, fit, indicator, predict
from pipelines.fusion.events import SOURCE_FAMILIES
from pipelines.lineage import git_sha, tree_is_clean


def validation_e(rows: list[dict]) -> float:
    """Mean primary error E over the validation family-years."""
    return float(np.mean([r["model"]["district_mae"] for r in rows]))


def mean_prediction(preds: list[dict]) -> dict[str, np.ndarray]:
    """Ensemble = element-wise mean of each member's expected observations and intensity."""
    return {k: np.mean([p[k] for p in preds], axis=0) for k in preds[0]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    # Lineage is captured before any work so later commits cannot change it.
    code_sha, code_clean = git_sha(), tree_is_clean()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    t = load_dataset(args.dataset, cfg["years"])
    if cfg.get("ablation") == "no_context":
        # Benchmark arm (amendment A2): every urban-context channel (exposure,
        # environment, traffic proxies) is held at its standardised mean, so the
        # network only sees the collision history. Same search, seeds and rule.
        t.X[:, : len(t.context_order)] = 0.0
    split, grid = cfg["split"], cfg["search"]

    # 1. Search on validation only.
    search = []
    for variant, hidden, dropout, lr in itertools.product(
        grid["variants"], grid["hidden"], grid["dropout"], grid["lr"]
    ):
        run_cfg = cfg | {"hidden": hidden, "dropout": dropout, "lr": lr, "seed": cfg["seed"]}
        model, info = fit(t, run_cfg, variant)
        val_rows = evaluate(t, predict(model, t), split["validation"])
        row = {
            "variant": variant,
            "hidden": hidden,
            "dropout": dropout,
            "lr": lr,
            "validation_E": round(validation_e(val_rows), 6),
            "validation_nll": info["best_validation_nll"],
            "best_epoch": info["best_epoch"],
        }
        search.append(row)
        print("search", json.dumps(row), flush=True)
    best = min(search, key=lambda r: (r["validation_E"], r["validation_nll"]))
    print("selected", json.dumps(best), flush=True)

    # 2. Seed ensemble of the selected configuration.
    members, preds, histories = [], [], []
    for seed in grid["ensemble_seeds"]:
        run_cfg = cfg | {k: best[k] for k in ("hidden", "dropout", "lr")} | {"seed": seed}
        model, info = fit(t, run_cfg, best["variant"])
        members.append(model.state_dict())
        preds.append(predict(model, t))
        histories.append(
            {"seed": seed, "history": info["history"], "best_epoch": info["best_epoch"]}
        )
        print("member", seed, info["best_epoch"], info["best_validation_nll"], flush=True)
    pred = mean_prediction(preds)
    val_rows = evaluate(t, pred, split["validation"])

    # 3. Single test evaluation.
    test_rows = evaluate(t, pred, split["test"])

    lam = pred["lambda"]
    value = indicator(t, lam, cfg["area_floor_km2"])
    train_years = sorted({y for ys in split["train"].values() for y in ys})
    reference = np.sort(value[[t.years.index(y) for y in train_years]][:, :, t.valid].ravel())
    buffer = io.BytesIO()
    torch.save({"variant": best["variant"], "members": members}, buffer)
    (out / "model.pt").write_bytes(buffer.getvalue())
    np.savez_compressed(
        out / "estimates.npz",
        years=np.array(t.years),
        lam=lam.astype(np.float64),
        indicator=value,
        reference=reference,
        rho=pred["rho"],
    )
    metrics = {
        "protocol": "docs/ml/benchmark-protocol-v2.md",
        "selected_variant": best["variant"],
        "selected_config": best,
        "selection_rule": "lowest validation E (district x subperiod MAE); seed ensemble of 5",
        "search": search,
        "ensemble_members": histories,
        "validation": val_rows,
        "test": test_rows,
        "reporting_factor": dict(zip(SOURCE_FAMILIES, pred["rho"].round(6).tolist(), strict=True)),
        "candidates": {},
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    manifest = {
        "run_id": cfg["run_id"],
        "config": cfg | {k: best[k] for k in ("hidden", "dropout", "lr")},
        "dataset_manifest_sha256": hashlib.sha256(
            (args.dataset / "dataset_manifest.json").read_bytes()
        ).hexdigest(),
        "model_family": f"pytorch:{best['variant']}:ensemble{len(members)}",
        "code_commit_sha": code_sha,
        "code_tree_clean": code_clean,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "threads": cfg["threads"],
        "device": cfg.get("device", "cpu"),
        "weights_sha256": hashlib.sha256((out / "model.pt").read_bytes()).hexdigest(),
        "estimates_sha256": hashlib.sha256((out / "estimates.npz").read_bytes()).hexdigest(),
        "tensor_shapes": {"X": list(t.X.shape), "y_cell": list(t.y_cell.shape)},
        "channels": t.channels,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"selected": best, "test": test_rows}, indent=2))


if __name__ == "__main__":
    main()
