"""Quality-aware loss and causal multi-year history (development only)."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np
import torch

from ml.fused.model import SpatioTemporalModel, expected_observations
from ml.fused.tensors import load_dataset
from ml.fused.train import evaluate, predict, set_determinism, to_torch, year_mask


def station_flags(dataset, t):
    """Only flag source-years entirely proxy-located; never infer from outcomes."""
    groups = {}
    for row in csv.DictReader((dataset / "events.csv").open(encoding="utf8")):
        if row["family"] == "cenacom" and int(row["year"]) in t.years:
            groups.setdefault(int(row["year"]), set()).add(row["location_basis"])
    return np.array([groups.get(y) == {"station_proxy"} for y in t.years], bool)


def history_features(t, station):
    """Past-only source-separated rates; gaps retain last available memory."""
    s_count, years, bands, h, w = t.y_cell.shape
    # Eight bands each for pooled cell and district historical rates,
    # plus observed-source recency. Proxy years excluded from spatial history.
    extra = np.zeros((years, s_count * (2 * bands + 1), h, w), np.float32)
    area = np.maximum((t.frac * t.area_km2[None]).sum((1, 2)), 1e-6)
    for s in range(s_count):
        past = []
        for i in range(years):
            if past:
                ids = np.array(past)
                cov = t.cover[s, ids]
                # Coverage and location fractions act as exposure, not zeros.
                c_exp = (cov * t.located[s, ids, None]).sum(0)
                c = t.y_cell[s, ids].sum(0) / np.maximum(c_exp, 1e-6)[:, None, None]
                dd = (
                    t.events_total[s, ids].sum(0)
                    / np.maximum(cov.sum(0), 1e-6)[:, None]
                    / area[None]
                )
                base = s * (2 * bands + 1)
                extra[i, base : base + bands] = np.log1p(c) * t.valid
                extra[i, base + bands : base + 2 * bands] = (
                    np.log1p(np.einsum("kd,dhw->khw", dd, t.frac)) * t.valid
                )
                extra[i, base + 2 * bands] = np.exp(-(t.years[i] - t.years[past[-1]]) / 3) * t.valid
            if np.all(t.cover[s, i] > 0) and not (s == 0 and station[i]):
                past.append(i)
    t.X = np.concatenate([t.X, extra], axis=1)
    t.channels.extend(
        f"trusted_history_{s}_{i}" for s in range(s_count) for i in range(2 * bands + 1)
    )
    return t


def suppress_proxy_lags(t, station):
    """Replace station spatial lag with its city-average density, not fake locations."""
    idx = t.channels.index("cenacom_prev_district_density")
    for i in range(1, len(t.years)):
        if station[i - 1]:
            # Location unknown; preserve only previous aggregate intensity.
            t.X[i, idx, t.valid] = t.X[i, idx, t.valid].mean()
    return t


def quality_loss(model, d, mask, station, weight):
    lam = model(d["X"])
    c, dist = expected_observations(
        lam, model.reporting_factors(), d["cover"], d["located"], d["frac"], d["valid"]
    )
    mc = mask[:, :, None, None, None] * d["valid"]
    md = mask[:, :, None, None]
    cell = ((c - d["y_cell"] * torch.log(c + 1e-8)) * mc).sum()
    per = dist - d["y_dist"] * torch.log(dist + 1e-8)
    # For proxy years, city-level likelihood retains counts, without assuming
    # that reporting district is actual crash district. Blend with original
    # district likelihood using a fixed confidence weight.
    proxy = station[None, :, None, None]
    source = torch.arange(dist.shape[0], device=dist.device)[:, None, None, None] == 0
    spatial_weight = 1 - (1 - weight) * (proxy & source).float()
    spatial = (per * md * spatial_weight).sum()
    city = dist.sum(-1)
    y = d["y_dist"].sum(-1)
    city_nll = city - y * torch.log(city + 1e-8)
    coarse = (city_nll * mask[:, :, None] * (1 - spatial_weight[..., 0])).sum()
    n = (d["y_cell"] * mc).sum() + (d["y_dist"] * md).sum()
    return (cell + spatial + coarse) / n.clamp_min(1)


def fit(t, cfg, station, arm):
    set_determinism(20261122, 8, "cuda")
    d = to_torch(t, "cuda")
    flags = torch.from_numpy(station).to("cuda")
    train = year_mask(t, cfg["split"]["train"]).to("cuda")
    val = year_mask(t, cfg["split"]["validation"]).to("cuda")
    weight = {"Q1": 0.25, "Q2": 0.0, "Q3": 0.25, "Q4": 1.0}[arm]
    model = SpatioTemporalModel(
        t.X.shape[1],
        t.y_cell.shape[2],
        t.y_cell.shape[0],
        hidden=32,
        dropout=0.1,
        variant="convlstm",
    ).to("cuda")
    opt = torch.optim.Adam(model.parameters(), lr=0.003, weight_decay=0.0001)
    best, state, best_epoch = float("inf"), None, 0
    hist = []
    for epoch in range(200):
        model.train()
        opt.zero_grad()
        loss = quality_loss(model, d, train, flags, weight)
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            score = float(quality_loss(model, d, val, flags, weight))
        hist.append([epoch, float(loss.detach()), score])
        if score < best - 1e-5:
            best, best_epoch = score, epoch
            state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        elif epoch - best_epoch >= 35:
            break
    if state is None:
        raise RuntimeError("No finite checkpoint")
    model.cpu().load_state_dict(state)
    return model.eval(), hist, best_epoch


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
        for arm in ("Q1", "Q2", "Q3", "Q4"):
            start = time.perf_counter()
            t = load_dataset(a.dataset, [y for y in cfg["years"] if y <= end], norm_years=train)
            flags = station_flags(a.dataset, t)
            if arm in ("Q2", "Q3", "Q4"):
                suppress_proxy_lags(t, flags)
            if arm in ("Q3", "Q4"):
                history_features(t, flags)
            model, hist, epoch = fit(t, cfg, flags, arm)
            row = evaluate(t, predict(model, t), cfg["split"]["validation"])[0]
            r = dict(
                fold=fold,
                arm=arm,
                metrics=row,
                epochs=len(hist),
                best_epoch=epoch,
                elapsed=round(time.perf_counter() - start, 2),
            )
            results.append(r)
            (a.out / "screening.json").write_text(json.dumps(results, indent=2))
            (a.out / f"{fold}-{arm}-history.json").write_text(json.dumps(hist))
            print(json.dumps(r), flush=True)
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
