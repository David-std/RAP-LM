"""V7: year-specific CENACOM recording factor. See docs/ml/performance-v7.md."""

from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path

import numpy as np
import torch

from ml.fused.model import SpatioTemporalModel
from ml.fused.tensors import load_dataset
from ml.fused.train import evaluate, poisson_nll, predict, set_determinism, to_torch, year_mask
from pipelines.fusion.events import SOURCE_FAMILIES, SUBPERIODS

ARMS = ("P0", "P1", "P2")
SEEDS = (1, 2, 3, 4, 5)
PENALTY = 0.01


def year_factor_mask(t, cfg, arm):
    """Which CENACOM years get a free log factor (2011 = reference stays 0)."""
    train = cfg["split"]["train"].get("cenacom", [])
    mask = np.zeros(len(t.years), np.float32)
    if arm == "P1":
        for y in train[1:]:
            mask[t.years.index(y)] = 1
    elif arm == "P2" and 2017 in train:
        mask[t.years.index(2017)] = 1
    return mask


def fit_arm(t, cfg, arm, seed):
    device = cfg["device"]
    set_determinism(seed, cfg["threads"], device)
    d = to_torch(t, device)
    base_cover = d["cover"].clone()
    model = SpatioTemporalModel(
        in_channels=t.X.shape[1],
        subperiods=len(SUBPERIODS),
        families=len(SOURCE_FAMILIES),
        hidden=cfg["hidden"],
        dropout=cfg["dropout"],
        variant="convlstm",
    ).to(device)
    mask = torch.from_numpy(year_factor_mask(t, cfg, arm)).to(device)
    log_year = torch.nn.Parameter(torch.zeros(len(t.years), device=device))
    params = list(model.parameters()) + ([log_year] if mask.sum() > 0 else [])
    opt = torch.optim.Adam(params, lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    train_mask = year_mask(t, cfg["split"]["train"]).to(device)
    val_mask = year_mask(t, cfg["split"]["validation"]).to(device)

    def with_factor():
        first = base_cover[0] * torch.exp(log_year * mask)[:, None]
        d["cover"] = torch.cat([first[None], base_cover[1:]], dim=0)

    best = (float("inf"), None, None, 0)
    for epoch in range(cfg["max_epochs"]):
        model.train()
        opt.zero_grad()
        with_factor()
        loss = poisson_nll(model, d, train_mask) + PENALTY * ((log_year * mask) ** 2).sum()
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            with_factor()
            val = poisson_nll(model, d, val_mask).item()
        if val < best[0] - 1e-5:
            state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            best = (val, state, (log_year * mask).detach().cpu().numpy(), epoch)
        elif epoch - best[3] >= cfg["patience"]:
            break
    model.load_state_dict(best[1])
    return model.cpu().eval(), best[2], best[3]


def member_prediction(t, model, factors):
    """Predict with the learned factors; years after training reuse the last one."""
    tp = copy.copy(t)
    tp.cover = t.cover.copy()
    f = factors.copy()
    last = 0.0
    for i in range(len(f)):
        if f[i] != 0:
            last = f[i]
        elif t.years[i] > 2011 and t.cover[0, i].max() > 0:
            f[i] = last
    tp.cover[0] = tp.cover[0] * np.exp(f)[:, None]
    return predict(model, tp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("artifacts/datasets/fused-v1.4.0"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--folds", default="onsv,cenacom")
    ap.add_argument("--test", action="store_true", help="also score test years (once)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    configs = {"onsv": "v4-main.json", "cenacom": "v4-backtest-2017.json"}
    records = []
    for fold in args.folds.split(","):
        cfg = json.loads((Path("ml/configs") / configs[fold]).read_text(encoding="utf-8"))
        cfg.update(hidden=32, dropout=0.1, lr=0.003, device="cuda")
        t = load_dataset(args.dataset, cfg["years"])
        for arm in args.arms.split(","):
            start = time.perf_counter()
            preds, factors = [], []
            for seed in SEEDS:
                model, f, epoch = fit_arm(t, cfg, arm, seed)
                preds.append(member_prediction(t, model, f))
                factors.append(
                    {"seed": seed, "best_epoch": epoch, "log_factors": f.round(4).tolist()}
                )
                torch.cuda.empty_cache()
            ens = {
                k: np.mean([p[k] for p in preds], axis=0) for k in ("mu_cell", "mu_district_total")
            }
            split = dict(cfg["split"]["validation"])
            if args.test:
                for fam, ys in cfg["split"]["test"].items():
                    split[fam] = split.get(fam, []) + ys
            rows = evaluate(t, ens, split)
            rec = dict(
                fold=fold,
                arm=arm,
                members=factors,
                rows=rows,
                elapsed=round(time.perf_counter() - start, 1),
            )
            records.append(rec)
            for r in rows:
                print(
                    fold,
                    arm,
                    r["family"],
                    r["year"],
                    "MAE",
                    round(r["model"]["district_mae"], 5),
                    "impr",
                    r["relative_improvement_pct"],
                    "cap",
                    round(r["model"]["capture_top10"], 4),
                    "baseCap",
                    round(r["baseline"]["capture_top10"], 4) if r["baseline"] else None,
                    flush=True,
                )
            (args.out / "results.json").write_text(json.dumps(records, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
