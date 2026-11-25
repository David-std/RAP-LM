# ruff: noqa: E501
"""V10-V12 harness: corrected evaluation, multi-horizon memory, two-head CNN-RNN.

See docs/ml/performance-v10.md. Usage::

    python -m ml.experiments.v10 train --folds D1,D2,D3 --cands C0,C1,C2,C3,C4
    python -m ml.experiments.v10 report --folds D1,D2,D3
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from ml.fused.model import ConvLSTMCell, SpatioTemporalModel
from ml.fused.tensors import load_dataset
from ml.fused.train import (
    historical_average,
    poisson_nll,
    predict,
    set_determinism,
    to_torch,
    year_mask,
)
from pipelines.fusion.events import SOURCE_FAMILIES, SUBPERIODS

DATASET = Path("artifacts/datasets/fused-v1.4.0")
OUT = Path("artifacts/runs/performance-v10")
CEN = list(range(2011, 2018))
FOLDS = {
    "D1": dict(
        years=list(range(2011, 2016)),
        train={"cenacom": [2011, 2012, 2013]},
        stop={"cenacom": [2014]},
        eval=("cenacom", 2015),
    ),
    "D2": dict(
        years=list(range(2011, 2017)),
        train={"cenacom": [2011, 2012, 2013, 2014]},
        stop={"cenacom": [2015]},
        eval=("cenacom", 2016),
    ),
    "D3": dict(
        years=list(range(2011, 2024)),
        train={"cenacom": CEN, "onsv": [2021]},
        stop={"onsv": [2022]},
        eval=("onsv", 2023),
    ),
    "D2b": dict(years=list(range(2011, 2017)), train={"cenacom": CEN[:5]}, stop=None, epochs=150, eval=("cenacom", 2016)),
    "D3b": dict(years=list(range(2011, 2024)), train={"cenacom": CEN, "onsv": [2021, 2022]}, stop=None, epochs=150, eval=("onsv", 2023)),
    "T1": dict(
        years=CEN, train={"cenacom": CEN[:5]}, stop={"cenacom": [2016]}, eval=("cenacom", 2017)
    ),
    "T2": dict(
        years=list(range(2011, 2025)),
        train={"cenacom": CEN, "onsv": [2021, 2022]},
        stop={"onsv": [2023]},
        eval=("onsv", 2024),
    ),
}
SEEDS = (1, 2, 3, 4, 5)
HALF_LIFE = 2.0


# ----------------------------------------------------------------------------- inputs
def add_memory(t, mode: str):
    """Causal history channels. Cell memory only uses years with located events;
    district memory uses every covered year. Uncovered years are skipped, not zero."""
    if mode == "none":
        return t
    s_count, years = t.y_cell.shape[:2]
    area = np.maximum((t.frac * t.area_km2[None]).sum(axis=(1, 2)), 1e-6)
    feats, names = [], []
    for s in range(s_count):
        cell_hist, dist_hist = [], []  # (year, map)
        chans = {}
        for i in range(years):
            y = t.years[i]
            for kind, hist in (("cell", cell_hist), ("dist", dist_hist)):
                if not hist:
                    continue
                ys = np.array([h[0] for h in hist], float)
                maps = np.stack([h[1] for h in hist])
                specs = {"all": np.ones_like(ys)}
                if mode == "multi":
                    specs["last3"] = (ys >= ys[np.argsort(ys)[-3:]].min()).astype(float)
                    specs["decay"] = 0.5 ** ((y - 1 - ys) / HALF_LIFE)
                for name, w in specs.items():
                    key = f"{SOURCE_FAMILIES[s]}_{kind}_{name}"
                    chans.setdefault(key, np.zeros((years, *t.valid.shape), np.float32))
                    chans[key][i] = np.log1p(np.tensordot(w / w.sum(), maps, axes=(0, 0))) * t.valid
            if mode == "multi":
                key = f"{SOURCE_FAMILIES[s]}_years_covered"
                chans.setdefault(key, np.zeros((years, *t.valid.shape), np.float32))
                chans[key][i] = len(dist_hist) / 7.0 * t.valid
            cov = t.cover[s, i].mean()
            if cov > 0:
                dens = t.events_total[s, i].sum(axis=0) / cov / area
                dist_hist.append((y, np.tensordot(dens, t.frac, axes=(0, 0))))
                if t.located[s, i] > 0:
                    cell_hist.append((y, t.y_cell[s, i].sum(axis=0) / (cov * t.located[s, i])))
        for k, v in chans.items():
            feats.append(v)
            names.append(k)
    if feats:
        t.X = np.concatenate([t.X, np.stack(feats, axis=1)], axis=1)
        t.channels = list(t.channels) + names
    return t


# ----------------------------------------------------------------------------- two-head model
class TwoHead(nn.Module):
    """Shared ConvLSTM; district magnitude head and within-district spatial share head."""

    def __init__(self, t, hidden: int = 32):
        super().__init__()
        K = len(SUBPERIODS)
        self.encoder = ConvLSTMCell(t.X.shape[1], hidden)
        self.spatial = nn.Conv2d(hidden, K, 1)
        self.magnitude = nn.Sequential(nn.Linear(hidden + 1, 32), nn.ReLU(), nn.Linear(32, K))
        nn.init.constant_(self.magnitude[2].bias, 0.5)
        self.log_report = nn.Parameter(torch.zeros(len(SOURCE_FAMILIES)))
        frac = torch.from_numpy(t.frac)
        self.register_buffer("frac_norm", frac / frac.sum(dim=(1, 2), keepdim=True).clamp_min(1e-9))
        self.register_buffer(
            "log_frac",
            torch.where(frac > 0, frac.clamp_min(1e-9).log(), torch.full_like(frac, -1e4)),
        )
        area = (t.frac * t.area_km2[None]).sum(axis=(1, 2))
        la = np.log(np.maximum(area, 1e-3))
        self.register_buffer(
            "log_area", torch.from_numpy(((la - la.mean()) / (la.std() + 1e-6)).astype(np.float32))
        )

    def reporting_factors(self):
        mask = torch.ones_like(self.log_report)
        mask[0] = 0
        return self.log_report * mask

    def intensities(self, X):
        F = self.encoder(X)  # T,F,H,W
        s = self.spatial(F)  # T,K,H,W
        T = F.shape[0]
        Fd = torch.einsum("tfhw,dhw->tdf", F, self.frac_norm)
        Fd = torch.cat([Fd, self.log_area[None, :, None].expand(T, -1, 1)], dim=-1)
        N = torch.exp(self.magnitude(Fd)).permute(0, 2, 1)  # T,K,D
        logits = s[:, :, None] + self.log_frac[None, None]  # T,K,D,H,W
        p = torch.softmax(logits.flatten(3), dim=-1).view_as(logits)
        lam = torch.einsum("tkd,tkdhw->tkhw", N, p)
        return lam, N

    def observe(self, d):
        lam, N = self.intensities(d["X"])
        scale = torch.exp(self.reporting_factors())[:, None, None] * d["cover"]
        mu_c = lam[None] * (scale * d["located"][:, :, None])[..., None, None]
        mu_d = N[None] * (scale * (1 - d["located"][:, :, None]))[..., None]
        return mu_c, mu_d, lam, N, scale


def two_head_nll(model, d, mask):
    mu_c, mu_d, *_ = model.observe(d)
    mc = mask[:, :, None, None, None] * d["valid"]
    md = mask[:, :, None, None]
    nll_c = ((mu_c - d["y_cell"] * torch.log(mu_c + 1e-8)) * mc).sum()
    nll_d = ((mu_d - d["y_dist"] * torch.log(mu_d + 1e-8)) * md).sum()
    events = (d["y_cell"] * mc).sum() + (d["y_dist"] * md).sum()
    return (nll_c + nll_d) / events.clamp(min=1)


def two_head_predict(model, t):
    d = to_torch(t)
    with torch.no_grad():
        mu_c, _, lam, N, scale = model.observe(d)
    return {
        "mu_cell": mu_c.numpy(),
        "mu_district_total": (N[None] * scale[..., None]).numpy(),
        "lambda": lam.numpy(),
    }


# ----------------------------------------------------------------------------- training
def fit_candidate(t, fold, cand, seed, device="cuda", max_epochs=300, patience=40):
    set_determinism(seed, 8, device)
    d = to_torch(t, device)
    two = cand in ("C3", "C4")
    model = (
        TwoHead(t)
        if two
        else SpatioTemporalModel(
            t.X.shape[1], len(SUBPERIODS), len(SOURCE_FAMILIES), 32, 0.1, "convlstm"
        )
    ).to(device)
    nll = two_head_nll if two else poisson_nll
    opt = torch.optim.Adam(model.parameters(), lr=0.003, weight_decay=1e-4)
    train = year_mask(t, fold["train"]).to(device)
    fixed = fold.get("stop") is None
    stop = None if fixed else year_mask(t, fold["stop"]).to(device)
    best = (float("inf"), None, 0)
    for epoch in range(fold["epochs"] if fixed else max_epochs):
        model.train()
        opt.zero_grad()
        loss = nll(model, d, train)
        loss.backward()
        opt.step()
        if fixed:
            best = (0.0, None, epoch)
            continue
        model.eval()
        with torch.no_grad():
            v = nll(model, d, stop).item()
        if v < best[0] - 1e-5:
            best = (v, {k: x.detach().clone() for k, x in model.state_dict().items()}, epoch)
        elif epoch - best[2] >= patience:
            break
    if best[1] is not None:
        model.load_state_dict(best[1])
    model = model.cpu().eval()
    p = two_head_predict(model, t) if two else predict(model, t)
    return p, best[2]


MEMORY = {"C0": "none", "C1": "all", "C2": "multi", "C3": "none", "C4": "multi"}


def load_fold(name):
    f = FOLDS[name]
    norm = sorted({y for ys in f["train"].values() for y in ys})  # stop/eval years excluded
    return f, load_dataset(DATASET, f["years"], norm_years=norm)


def train(folds, cands):
    for name in folds:
        f, base = load_fold(name)
        for cand in cands:
            out = OUT / name / cand
            out.mkdir(parents=True, exist_ok=True)
            t = add_memory(_copy(base), "all" if MEMORY[cand] == "all" else MEMORY[cand])
            for seed in SEEDS:
                path = out / f"s{seed}.npz"
                if path.exists():
                    continue
                start = time.perf_counter()
                p, epoch = fit_candidate(t, f, cand, seed)
                np.savez_compressed(
                    path,
                    mu_cell=p["mu_cell"].astype(np.float32),
                    mu_district_total=p["mu_district_total"].astype(np.float32),
                    best_epoch=epoch,
                )
                print(name, cand, seed, epoch, round(time.perf_counter() - start, 1), flush=True)
                torch.cuda.empty_cache()


def _copy(t):
    import copy

    c = copy.copy(t)
    c.X = t.X.copy()
    c.channels = list(t.channels)
    return c


# ----------------------------------------------------------------------------- evaluation
def strata_targets(t, family, year):
    """Annual cell counts by location precision, from the fused events."""
    index = {u: (r, c) for u, r, c in zip(t.unit_ids, t.rows, t.cols, strict=True)}
    allm = np.zeros(t.valid.shape)
    precise = np.zeros(t.valid.shape)
    with (DATASET / "events.csv").open(encoding="utf-8") as fh:
        for e in csv.DictReader(fh):
            if e["family"] != family or int(e["year"]) != year or e["precision"] == "district":
                continue
            for u, w in json.loads(e["allocation"]).items():
                r, c = index[u]
                allm[r, c] += w
                if e["precision"] in ("intersection", "point"):
                    precise[r, c] += w
    return {"all_located": allm[t.valid], "precise": precise[t.valid]}


def ap_ties(pos, score):
    order = np.argsort(-score, kind="stable")
    s, p = score[order], pos[order].astype(float)
    if p.sum() == 0:
        return float("nan")
    last = np.r_[np.nonzero(np.diff(s))[0], len(s) - 1]
    tp = np.cumsum(p)[last]
    prec = tp / (last + 1)
    rec = tp / p.sum()
    return float(np.sum((rec - np.r_[0, rec[:-1]]) * prec))


def auc_ranks(pos, score):
    order = np.argsort(score, kind="stable")
    ranks = np.empty(len(score))
    xs = score[order]
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2 + 1
        i = j + 1
    n1 = pos.sum()
    n0 = len(pos) - n1
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def capture_ties(obs, score, share):
    """Share of obs in the top `share` of units; tied units at the cut count proportionally."""
    k = share * len(score)
    order = np.argsort(-score, kind="stable")
    s = score[order]
    cut = s[min(len(s) - 1, int(np.ceil(k)) - 1)]
    above = score > cut
    tie = score == cut
    slots = k - above.sum()
    got = obs[above].sum() + (obs[tie].sum() * slots / tie.sum() if tie.sum() else 0)
    return float(got / obs.sum()) if obs.sum() > 0 else float("nan")


def ranking(obs, score):
    pos = obs >= 0.5
    return {
        "auc": auc_ranks(pos, score),
        "average_precision": ap_ties(pos, score),
        "capture_top5": capture_ties(obs, score, 0.05),
        "capture_top10": capture_ties(obs, score, 0.10),
        "capture_top20": capture_ties(obs, score, 0.20),
        "positives": int(pos.sum()),
        "mass": float(obs.sum()),
    }


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def deviance(y, mu):
    mu = np.maximum(mu, 1e-9)
    return float(2 * np.mean(np.where(y > 0, y * np.log(np.maximum(y, 1e-9) / mu), 0) - (y - mu)))


def decayed_average(t, s, ti):
    prior = [p for p in range(ti) if t.cover[s, p].max() > 0]
    if not prior:
        return None
    w = np.array([0.5 ** ((ti - 1 - p) / HALF_LIFE) for p in prior])
    w /= w.sum()
    cell = sum(
        wi * t.y_cell[s, p] / (t.cover[s, p][:, None, None] * max(float(t.located[s, p]), 1e-6))
        for wi, p in zip(w, prior, strict=True)
    )
    dist = sum(
        wi * t.events_total[s, p] / t.cover[s, p][:, None] for wi, p in zip(w, prior, strict=True)
    )
    return cell * (t.cover[s, ti][:, None, None] * t.located[s, ti]), dist * t.cover[s, ti][:, None]


def score_unit(t, strata, s, ti, mu_cell, mu_dist):
    obs_d = t.events_total[s, ti]
    cell_score = mu_cell.sum(axis=0)[t.valid]
    res = {
        "district": {
            "mae": float(np.abs(mu_dist - obs_d).mean()),
            "deviance": deviance(obs_d, mu_dist),
            "spearman": spearman(mu_dist.sum(axis=0), obs_d.sum(axis=0)),
            "capture_top20": capture_ties(obs_d.sum(axis=0), mu_dist.sum(axis=0), 0.2),
        }
    }
    for k, obs in strata.items():
        res[k] = ranking(obs, cell_score) if obs.sum() > 0 else None
    return res


def evaluate_fold(name, cands):
    f, t = load_fold(name)
    fam, year = f["eval"]
    s, ti = SOURCE_FAMILIES.index(fam), t.years.index(year)
    strata = strata_targets(t, fam, year)
    rows = {}
    hc, hd = historical_average(t, s, ti)
    rows["historical"] = score_unit(t, strata, s, ti, hc, hd)
    dc, dd = decayed_average(t, s, ti)
    rows["decayed_historical"] = score_unit(t, strata, s, ti, dc, dd)
    for cand in cands:
        files = sorted((OUT / name / cand).glob("s*.npz"))
        if not files:
            continue
        zs = [np.load(p) for p in files]
        mc = np.mean([z["mu_cell"] for z in zs], axis=0)[s, ti]
        md = np.mean([z["mu_district_total"] for z in zs], axis=0)[s, ti]
        rows[cand] = score_unit(t, strata, s, ti, mc, md) | {"members": len(zs)}
    return rows


def report(folds, cands):
    allrows = {name: evaluate_fold(name, cands) for name in folds}
    out = Path("evidence/benchmarking/performance-v10")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"evaluation-{'-'.join(folds)}.json").write_text(
        json.dumps(allrows, indent=2), encoding="utf-8"
    )
    for name, rows in allrows.items():
        print(f"\n== {name} eval {FOLDS[name]['eval']}")
        for k, r in rows.items():
            line = f"{k:20s} dMAE {r['district']['mae']:.4f} rho {r['district']['spearman']:.3f} dcap20 {r['district']['capture_top20']:.3f}"
            for st in ("all_located", "precise"):
                if r.get(st):
                    x = r[st]
                    line += f" | {st[:3]} AUC {x['auc']:.3f} AP {x['average_precision']:.3f} c10 {x['capture_top10']:.3f} c20 {x['capture_top20']:.3f}"
            print(line)
    if {"D1", "D2"} <= set(allrows):
        print(
            "\n== selection score (mean D1,D2 of relative gains over historical: AP all-located, district MAE)"
        )
        for cand in cands:
            gains = []
            for name in ("D1", "D2"):
                r, h = allrows[name].get(cand), allrows[name]["historical"]
                if not r:
                    break
                ap_gain = (
                    r["all_located"]["average_precision"] - h["all_located"]["average_precision"]
                ) / h["all_located"]["average_precision"]
                mae_gain = (h["district"]["mae"] - r["district"]["mae"]) / h["district"]["mae"]
                gains.append((ap_gain + mae_gain) / 2)
            if len(gains) == 2:
                d3 = allrows.get("D3", {}).get(cand)
                print(
                    f"{cand}: score {np.mean(gains) * 100:+.2f} %  D3 AP {d3['all_located']['average_precision'] if d3 else float('nan'):.3f}"
                )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("train", "report"))
    ap.add_argument("--folds", default="D1,D2,D3")
    ap.add_argument("--cands", default="C0,C1,C2,C3,C4")
    a = ap.parse_args()
    folds, cands = a.folds.split(","), a.cands.split(",")
    (train if a.action == "train" else report)(folds, cands)


if __name__ == "__main__":
    main()
