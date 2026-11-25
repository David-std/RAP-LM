"""Development-only hierarchical observation models (v6)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from ml.fused.model import ConvLSTMCell
from ml.fused.tensors import load_dataset
from ml.fused.train import evaluate, set_determinism, to_torch, year_mask


class Hierarchical(nn.Module):
    def __init__(self, t, arm):
        super().__init__()
        self.arm = arm
        self.encoder = ConvLSTMCell(t.X.shape[1], 32)
        self.head = nn.Conv2d(32, t.y_cell.shape[2], 1)
        nn.init.constant_(self.head.bias, -4.0)
        self.log_report = nn.Parameter(torch.zeros(t.y_cell.shape[0]))
        self.district = nn.Parameter(torch.zeros(t.y_cell.shape[2], t.frac.shape[0]))
        self.band_report = nn.Parameter(torch.zeros(t.y_cell.shape[2]))
        self.register_buffer("frac", torch.from_numpy(t.frac))
        self.register_buffer("valid", torch.from_numpy(t.valid.astype(np.float32)))

    def forward(self, x):
        log_lam = self.head(self.encoder(x))
        if self.arm in ("H1", "H3", "H4"):
            effect = torch.einsum("kd,dhw->khw", self.district, self.frac)
            log_lam = log_lam + effect[None]
        lam = log_lam.exp() * self.valid
        if self.arm in ("H2", "H3", "H4"):
            # Source 0 anchors all-severity intensity. Source 1 is a bounded
            # observation multiplier, not an identified fatality probability.
            q = torch.sigmoid(self.log_report[1] + self.band_report - 1.5)
            rho = torch.stack([torch.ones_like(q), q])
        else:
            q = self.log_report[1].exp().expand(lam.shape[1])
            rho = torch.stack([torch.ones_like(q), q])
        return lam, rho


def predictions(model, d):
    lam, rho = model(d["X"])
    scale = rho[:, None, :] * d["cover"]
    full = torch.einsum("tkhw,dhw->tkd", lam, d["frac"])[None] * scale[..., None]
    cell = lam[None] * (scale * d["located"][:, :, None])[..., None, None]
    district = full * (1 - d["located"][:, :, None, None])
    return lam, rho, full, cell, district


def objective(model, d, mask, training=False):
    _, _, _, cell, district = predictions(model, d)
    mc = mask[:, :, None, None, None] * d["valid"]
    md = mask[:, :, None, None]
    c = ((cell - d["y_cell"] * torch.log(cell + 1e-8)) * mc).sum((1, 2, 3, 4))
    a = ((district - d["y_dist"] * torch.log(district + 1e-8)) * md).sum((1, 2, 3))
    n = (d["y_cell"] * mc).sum((1, 2, 3, 4)) + (d["y_dist"] * md).sum((1, 2, 3))
    if model.arm == "H4":
        active = (n > 0).float()
        loss = (((c + a) / n.clamp_min(1)) * active).sum() / active.sum().clamp_min(1)
    else:
        loss = (c + a).sum() / n.sum().clamp_min(1)
    if training:
        loss = (
            loss + 0.03 * model.district.square().mean() + 0.03 * model.band_report.square().mean()
        )
    return loss


def fit(t, cfg, arm, seed):
    set_determinism(seed, 8, "cuda")
    d = to_torch(t, "cuda")
    train = year_mask(t, cfg["split"]["train"]).to("cuda")
    val = year_mask(t, cfg["split"]["validation"]).to("cuda")
    model = Hierarchical(t, arm).to("cuda")
    opt = torch.optim.Adam(model.parameters(), lr=0.003, weight_decay=0.0001)
    best, state, best_epoch = float("inf"), None, 0
    hist = []
    for epoch in range(200):
        model.train()
        opt.zero_grad()
        loss = objective(model, d, train, True)
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            score = float(objective(model, d, val))
        hist.append([epoch, float(loss.detach()), score])
        if score < best - 1e-5:
            best, best_epoch = score, epoch
            state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        elif epoch - best_epoch >= 35:
            break
    if state is None:
        raise RuntimeError("No finite checkpoint")
    model.load_state_dict(state)
    model.eval()
    with torch.no_grad():
        lam, rho, full, cell, _ = predictions(model, d)
    pred = {
        "lambda": lam.cpu().numpy(),
        "rho": rho.cpu().numpy(),
        "mu_district_total": full.cpu().numpy(),
        "mu_cell": cell.cpu().numpy(),
    }
    return pred, hist, best_epoch


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    results = []
    for fold, filename in (("onsv", "v4-main.json"), ("cenacom", "v4-backtest-2017.json")):
        cfg = json.loads((Path("ml/configs") / filename).read_text(encoding="utf8"))
        train = sorted({y for ys in cfg["split"]["train"].values() for y in ys})
        end = max(y for ys in cfg["split"]["validation"].values() for y in ys)
        t = load_dataset(a.dataset, [y for y in cfg["years"] if y <= end], norm_years=train)
        for arm in ("H0", "H1", "H2", "H3", "H4"):
            start = time.perf_counter()
            pred, hist, epoch = fit(t, cfg, arm, 20261122)
            metrics = evaluate(t, pred, cfg["split"]["validation"])[0]
            r = dict(
                fold=fold,
                arm=arm,
                metrics=metrics,
                best_epoch=epoch,
                epochs=len(hist),
                elapsed=round(time.perf_counter() - start, 2),
                rho=pred["rho"].tolist(),
            )
            results.append(r)
            (a.out / "screening.json").write_text(json.dumps(results, indent=2))
            (a.out / f"{fold}-{arm}-history.json").write_text(json.dumps(hist))
            print(json.dumps(r), flush=True)
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
