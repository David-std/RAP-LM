"""Second validation-only screen: isolate residual and band-history effects."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch

from ml.experiments.performance import Candidate, add_band_history
from ml.fused.tensors import load_dataset
from ml.fused.train import evaluate, fit, poisson_nll, predict, set_determinism, to_torch, year_mask


class ResidualNLL(Candidate):
    """Remove dropout to isolate the offset from the first screen's other changes."""

    def forward(self, x):
        return self.head(self.encoder(x)) + self.offset


def fit_residual(t, cfg):
    set_determinism(cfg["seed"], cfg["threads"], cfg["device"])
    d = to_torch(t, cfg["device"])
    train = year_mask(t, cfg["split"]["train"]).to(cfg["device"])
    val = year_mask(t, cfg["split"]["validation"]).to(cfg["device"])
    model = ResidualNLL(t, True).to(cfg["device"])
    opt = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    best, state, epoch_best = float("inf"), None, 0
    history = []
    for epoch in range(cfg["max_epochs"]):
        model.train()
        opt.zero_grad()
        loss = poisson_nll(model, d, train)
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            score = float(poisson_nll(model, d, val))
        history.append([epoch, float(loss.detach()), score])
        if score < best - 1e-5:
            best, epoch_best = score, epoch
            state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        elif epoch - epoch_best >= cfg["patience"]:
            break
    if state is None:
        raise RuntimeError("No finite checkpoint")
    model.cpu().load_state_dict(state)
    return model.eval(), history, epoch_best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for fold, fname in (("onsv", "v4-main.json"), ("cenacom", "v4-backtest-2017.json")):
        cfg = json.loads((Path("ml/configs") / fname).read_text(encoding="utf-8"))
        train_years = sorted({y for years in cfg["split"]["train"].values() for y in years})
        max_val = max(y for ys in cfg["split"]["validation"].values() for y in ys)
        cfg.update(hidden=32, lr=.003, dropout=.1, max_epochs=200, patience=35,
                   seed=20261122, device="cuda")
        years = [y for y in cfg["years"] if y <= max_val]
        for arm in ("R0", "R1", "R2"):
            start = time.perf_counter()
            t = load_dataset(args.dataset, years, norm_years=train_years)
            if arm in ("R1", "R2"):
                add_band_history(t)
            if arm in ("R0", "R2"):
                model, hist, best_epoch = fit_residual(t, cfg)
            else:
                model, info = fit(t, cfg, "convlstm")
                hist, best_epoch = info["history"], info["best_epoch"]
            row = evaluate(t, predict(model, t), cfg["split"]["validation"])[0]
            result = dict(fold=fold, arm=arm, best_epoch=best_epoch,
                          epochs=len(hist), elapsed=round(time.perf_counter()-start, 2),
                          metrics=row)
            records.append(result)
            (args.out / "screening.json").write_text(json.dumps(records, indent=2))
            (args.out / f"{fold}-{arm}-history.json").write_text(json.dumps(hist))
            print(json.dumps(result), flush=True)
            del model, t
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
