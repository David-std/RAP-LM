"""Scale-free prioritisation metrics of the published v4 runs on their test years.

Ranking quality does not depend on the total recorded volume, so it is unaffected
by recording-level breaks. Unit = cell-year (annual sum over subperiods) and
district-year. Positive cell = at least half a located event (same rule as the
existing annual-cell report). Baseline = historical average; random = expectation.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ml.experiments.combination import district_estimates
from ml.fused.tensors import load_dataset
from ml.fused.train import historical_average
from pipelines.fusion.events import SOURCE_FAMILIES

FOLDS = (
    ("onsv", "fused-cnnlstm-2026.11-v4", "v4-main.json"),
    ("cenacom", "fused-cnnlstm-backtest-2017-v4", "v4-backtest-2017.json"),
)


def ranks(x):
    """Average ranks (1-based) with ties."""
    order = np.argsort(x, kind="stable")
    r = np.empty(len(x), float)
    xs = x[order]
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and xs[j + 1] == xs[i]:
            j += 1
        r[order[i : j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return r


def roc_auc_score(positive, score):
    """Mann-Whitney AUC, ties counted as one half."""
    r = ranks(score)
    n1 = positive.sum()
    n0 = positive.size - n1
    return (r[positive].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def average_precision_score(positive, score):
    order = np.argsort(-score, kind="stable")
    hits = positive[order].astype(float)
    precision = np.cumsum(hits) / np.arange(1, len(hits) + 1)
    return float((precision * hits).sum() / hits.sum())


def spearmanr(a, b):
    return float(np.corrcoef(ranks(a), ranks(b))[0, 1])


def capture(obs, score, share):
    k = max(1, int(round(share * score.size)))
    top = np.argsort(-score, kind="stable")[:k]
    return float(obs[top].sum() / obs.sum())


def scores(obs, score, positive):
    out = {
        "auc": float(roc_auc_score(positive, score)),
        "average_precision": float(average_precision_score(positive, score)),
        "capture_top5": capture(obs, score, 0.05),
        "capture_top10": capture(obs, score, 0.10),
        "capture_top20": capture(obs, score, 0.20),
    }
    out["lift_top10"] = out["capture_top10"] / 0.10
    return out


def main():
    report = []
    for family, run, cfg_name in FOLDS:
        cfg = json.loads((Path("ml/configs") / cfg_name).read_text(encoding="utf-8"))
        t = load_dataset(Path("artifacts/datasets/fused-v1.4.0"), cfg["years"])
        z = np.load(Path("artifacts/runs") / run / "estimates.npz")
        s = SOURCE_FAMILIES.index(family)
        (year,) = cfg["split"]["test"][family]
        ti = t.years.index(year)
        lam = z["lam"][ti].sum(axis=0)[t.valid]
        base_cell, base_dist = historical_average(t, s, ti)
        base = base_cell.sum(axis=0)[t.valid]
        obs = t.y_cell[s, ti].sum(axis=0)[t.valid]
        positive = obs >= 0.5
        rng = np.random.default_rng(0)
        random_score = rng.random(obs.size)
        mu = district_estimates(t, z["lam"], z["rho"])[s, ti].sum(axis=0)
        d_obs = t.events_total[s, ti].sum(axis=0)
        bd = base_dist.sum(axis=0)
        top_obs = set(np.argsort(-d_obs)[:10])
        report.append(
            {
                "fold": family,
                "test_year": year,
                "cells": int(obs.size),
                "positive_cells": int(positive.sum()),
                "cell_year": {
                    "model": scores(obs, lam, positive),
                    "historical_average": scores(obs, base, positive),
                    "random_expected": {
                        "auc": 0.5,
                        "average_precision": float(positive.mean()),
                        "capture_top10": 0.10,
                        "lift_top10": 1.0,
                        "seeded_draw": scores(obs, random_score, positive),
                    },
                },
                "district_year": {
                    "model_spearman": float(spearmanr(mu, d_obs)),
                    "baseline_spearman": float(spearmanr(bd, d_obs)),
                    "model_top10_overlap": len(top_obs & set(np.argsort(-mu)[:10])),
                    "baseline_top10_overlap": len(top_obs & set(np.argsort(-bd)[:10])),
                },
            }
        )
        print(json.dumps(report[-1], indent=1), flush=True)
    out = Path("evidence/benchmarking/performance-v7/ranking_test.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
