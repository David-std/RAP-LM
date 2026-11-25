"""NB2 sensitivity arm for integer district-only CENACOM observations."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from ml.fused.model import SpatioTemporalModel, expected_observations
from ml.fused.tensors import load_dataset
from ml.fused.train import evaluate, predict, set_determinism, to_torch, year_mask


def estimate_dispersion(t, cfg):
    """Pooled method-of-moments diagnostic using only covered training years."""
    indices = [i for i, y in enumerate(t.years) if y in cfg["split"]["train"].get("cenacom", [])]
    y = t.y_dist[0, indices]
    exposure = t.cover[0, indices, :, None] * (1 - t.located[0, indices, None, None])
    rate = y.sum(axis=0) / np.maximum(exposure.sum(axis=0), 1e-8)
    mu = exposure * rate
    # This is a screening estimate, not a fully identified conditional dispersion.
    return float(np.clip((((y - mu) ** 2 - y).sum()) / max(float((mu**2).sum()), 1e-8), 0, 2))


def nb_nll(y, mu, alpha):
    if alpha <= 1e-6:
        return mu - y * torch.log(mu + 1e-8)
    r = 1 / alpha
    # Omit log(y!) which is constant in model parameters.
    return (
        torch.lgamma(torch.full_like(y, r))
        - torch.lgamma(y + r)
        + r * torch.log1p(mu / r)
        + y * (torch.log(mu + r) - torch.log(mu + 1e-8))
    )


def loss(model, d, mask, alpha):
    log_lambda = model(d["X"])
    mu_c, mu_d = expected_observations(
        log_lambda, model.reporting_factors(), d["cover"], d["located"], d["frac"], d["valid"]
    )
    mc = mask[:, :, None, None, None] * d["valid"]
    md = mask[:, :, None, None]
    nll_c = ((mu_c - d["y_cell"] * torch.log(mu_c + 1e-8)) * mc).sum()
    nll_d = (nb_nll(d["y_dist"][0], mu_d[0], alpha) * md[0]).sum()
    nll_d += ((mu_d[1:] - d["y_dist"][1:] * torch.log(mu_d[1:] + 1e-8)) * md[1:]).sum()
    events = (d["y_cell"] * mc).sum() + (d["y_dist"] * md).sum()
    return (nll_c + nll_d) / events.clamp_min(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    for fold, filename in (("onsv", "v4-main.json"), ("cenacom", "v4-backtest-2017.json")):
        start = time.perf_counter()
        cfg = json.loads((Path("ml/configs") / filename).read_text(encoding="utf-8"))
        train_years = sorted({y for ys in cfg["split"]["train"].values() for y in ys})
        max_val = max(y for ys in cfg["split"]["validation"].values() for y in ys)
        years = [y for y in cfg["years"] if y <= max_val]
        t = load_dataset(args.dataset, years, norm_years=train_years)
        alpha = estimate_dispersion(t, cfg)
        assert np.all(t.y_dist[0] == np.floor(t.y_dist[0])), "NB needs integer counts"
        device = "cuda"
        set_determinism(20261122, 8, device)
        d = to_torch(t, device)
        train = year_mask(t, cfg["split"]["train"]).to(device)
        val = year_mask(t, cfg["split"]["validation"]).to(device)
        model = SpatioTemporalModel(
            t.X.shape[1],
            t.y_cell.shape[2],
            t.y_cell.shape[0],
            hidden=32,
            dropout=0.1,
            variant="convlstm",
        ).to(device)
        opt = torch.optim.Adam(model.parameters(), lr=0.003, weight_decay=0.0001)
        best, state, best_epoch = float("inf"), None, 0
        hist = []
        for epoch in range(200):
            model.train()
            opt.zero_grad()
            objective = loss(model, d, train, alpha)
            objective.backward()
            opt.step()
            model.eval()
            with torch.no_grad():
                score = float(loss(model, d, val, alpha))
            hist.append([epoch, float(objective.detach()), score])
            if score < best - 1e-5:
                best, best_epoch = score, epoch
                state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            elif epoch - best_epoch >= 35:
                break
        if state is None:
            raise RuntimeError("No finite checkpoint")
        model.cpu().load_state_dict(state)
        row = evaluate(t, predict(model.eval(), t), cfg["split"]["validation"])[0]
        result = dict(
            fold=fold,
            arm="N0",
            alpha=alpha,
            epochs=len(hist),
            best_epoch=best_epoch,
            elapsed=round(time.perf_counter() - start, 2),
            metrics=row,
        )
        results.append(result)
        (args.out / "screening.json").write_text(json.dumps(results, indent=2))
        (args.out / f"{fold}-N0-history.json").write_text(json.dumps(hist))
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
