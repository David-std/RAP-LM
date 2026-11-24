"""Isolated, validation-only performance screening. See docs/ml/performance-v5.md."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from ml.fused.model import SpatioTemporalModel
from ml.fused.tensors import load_dataset
from ml.fused.train import evaluate, fit, poisson_nll, predict, set_determinism, to_torch, year_mask


ARMS = ("E0", "E1", "E2", "E3", "E4")


def add_band_history(t):
    """Use only immediately preceding covered observations; retain missingness flags."""
    s_count, years, bands, h, w = t.y_cell.shape
    extra = np.zeros((years, s_count * bands * 2, h, w), np.float32)
    area = np.maximum((t.frac * t.area_km2[None]).sum(axis=(1, 2)), 1e-6)
    for i in range(1, years):
        for s in range(s_count):
            cov = t.cover[s, i - 1]
            if not np.any(cov > 0):
                continue
            q = max(float(t.located[s, i - 1]), 1e-6)
            cell = t.y_cell[s, i - 1] / (np.maximum(cov, 1e-6)[:, None, None] * q)
            den = t.events_total[s, i - 1] / np.maximum(cov, 1e-6)[:, None] / area[None]
            spread = np.einsum("kd,dhw->khw", den, t.frac)
            offset = s * bands * 2
            extra[i, offset:offset + bands] = np.log1p(cell) * t.valid
            extra[i, offset + bands:offset + 2 * bands] = np.log1p(spread) * t.valid
    t.X = np.concatenate([t.X, extra], axis=1)
    t.channels.extend(
        f"band_history_{s}_{kind}_{k}"
        for s in range(s_count) for kind in ("cell", "district") for k in range(bands)
    )
    return t


def historical_prior(t):
    """All-severity past-only prior; district allocation is not an observed label."""
    _, years, bands, h, w = t.y_cell.shape
    prior = np.zeros((years, bands, h, w), np.float32)
    weights = t.frac * t.area_km2[None]
    weights /= np.maximum(weights.sum(axis=(1, 2), keepdims=True), 1e-6)
    rates = []
    for i in range(years):
        prior[i] = (np.mean(rates, axis=0) + .002 if rates else .02) * t.valid
        cov = t.cover[0, i]
        if np.all(cov > 0):
            unlocated = np.einsum("kd,dhw->khw", t.y_dist[0, i], weights)
            rates.append((t.y_cell[0, i] + unlocated) / cov[:, None, None])
    return prior


class Candidate(SpatioTemporalModel):
    def __init__(self, t, residual):
        super().__init__(t.X.shape[1], t.y_cell.shape[2], t.y_cell.shape[0],
                         hidden=32, dropout=0., variant="convlstm")
        offset = historical_prior(t) if residual else np.ones_like(t.y_cell[0])
        self.register_buffer("offset", torch.from_numpy(np.log(np.maximum(offset, 1e-8))))
        if residual:
            torch.nn.init.zeros_(self.head.weight)
            torch.nn.init.zeros_(self.head.bias)

    def forward(self, x):
        z = self.encoder(x)
        if self.training:
            # One channel mask shared across years and spatial positions.
            keep = (torch.rand((1, z.shape[1], 1, 1), device=z.device) >= .1)
            z = z * keep / .9
        return self.head(z) + self.offset


def district_prediction(model, d, log_lambda):
    lam = log_lambda.exp() * d["valid"]
    total = torch.einsum("tkhw,dhw->tkd", lam, d["frac"])
    scale = model.reporting_factors().exp()[:, None, None] * d["cover"]
    return total[None] * scale[..., None]


def district_mae(model, d, mask):
    pred = district_prediction(model, d, model(d["X"]))
    truth = d["events_total"]
    m = mask[:, :, None, None]
    return ((pred - truth).abs() * m).sum() / (m.sum() * truth.shape[2] * truth.shape[3]).clamp_min(1)


def train_candidate(t, cfg, arm):
    if arm == "E0":
        model, info = fit(t, cfg, "convlstm")
        return model, info["history"], info["best_epoch"]
    device = cfg["device"]
    set_determinism(cfg["seed"], cfg["threads"], device)
    d = to_torch(t, device)
    d["events_total"] = torch.from_numpy(t.events_total).to(device)
    train = year_mask(t, cfg["split"]["train"]).to(device)
    val = year_mask(t, cfg["split"]["validation"]).to(device)
    model = Candidate(t, arm == "E4").to(device)
    opt = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=.5, patience=12)
    best_score, best_state, best_epoch = float("inf"), None, 0
    history = []
    for epoch in range(cfg["max_epochs"]):
        model.train()
        opt.zero_grad()
        loss = poisson_nll(model, d, train)
        if arm in ("E3", "E4"):
            pred = district_prediction(model, d, model(d["X"]))
            err = F.smooth_l1_loss(pred, d["events_total"], beta=.5, reduction="none")
            mask = train[:, :, None, None]
            loss = loss + 2 * (err * mask).sum() / (
                mask.sum() * err.shape[2] * err.shape[3]).clamp_min(1)
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            score = float(district_mae(model, d, val))
        scheduler.step(score)
        history.append([epoch, float(loss.detach()), score, opt.param_groups[0]["lr"]])
        if score < best_score - 1e-5:
            best_score = score
            best_epoch = epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        elif epoch - best_epoch >= cfg["patience"]:
            break
    if best_state is None:
        raise RuntimeError("No finite checkpoint")
    model.cpu().load_state_dict(best_state)
    return model.eval(), history, best_epoch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for fold, filename in (("onsv", "v4-main.json"), ("cenacom", "v4-backtest-2017.json")):
        cfg = json.loads((Path("ml/configs") / filename).read_text(encoding="utf-8"))
        train_years = sorted({y for years in cfg["split"]["train"].values() for y in years})
        max_val = max(y for ys in cfg["split"]["validation"].values() for y in ys)
        cfg.update(hidden=32, lr=.003, dropout=.1, max_epochs=200, patience=35,
                   seed=20261122, device="cuda")
        years = [y for y in cfg["years"] if y <= max_val]
        for arm in ARMS:
            start = time.perf_counter()
            t = load_dataset(args.dataset, years, norm_years=train_years)
            if arm in ("E2", "E3", "E4"):
                add_band_history(t)
            model, hist, best_epoch = train_candidate(t, cfg, arm)
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
