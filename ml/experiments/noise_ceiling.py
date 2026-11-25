"""Noise ceiling and mean-versus-median point forecasts for district x subperiod MAE (v7).

Floor: expected MAE if the v4 intensity, rescaled to the observed total, were the truth.
It approximates the error that Poisson variability leaves even for a perfect intensity.
Median: the MAE-optimal point forecast of a Poisson predictive distribution
(Gneiting 2011, Making and evaluating point forecasts, JASA 106:746-762).
"""

from __future__ import annotations

import json
from math import lgamma
from pathlib import Path

import numpy as np

from ml.experiments.combination import FOLDS, district_estimates
from ml.fused.tensors import load_dataset
from ml.fused.train import historical_average
from pipelines.fusion.events import SOURCE_FAMILIES

K = np.arange(0, 300)[:, None]
LOG_FACT = np.array([lgamma(k + 1.0) for k in range(300)])[:, None]


def pmf(mu: np.ndarray) -> np.ndarray:
    m = np.maximum(mu.ravel()[None], 1e-12)
    return np.exp(K * np.log(m) - m - LOG_FACT)


def poisson_median(mu: np.ndarray) -> np.ndarray:
    cdf = np.cumsum(pmf(mu), axis=0)
    return (cdf < 0.5).sum(axis=0).reshape(mu.shape).astype(float)


def expected_abs_error(mu: np.ndarray) -> np.ndarray:
    m = np.maximum(mu.ravel()[None], 1e-12)
    return (pmf(mu) * np.abs(K - m)).sum(axis=0).reshape(mu.shape)


def mae(pred: np.ndarray, obs: np.ndarray) -> float:
    return float(np.abs(pred - obs).mean())


def main() -> None:
    report = []
    for family, run, cfg_name in FOLDS:
        cfg = json.loads((Path("ml/configs") / cfg_name).read_text(encoding="utf-8"))
        t = load_dataset(Path("artifacts/datasets/fused-v1.4.0"), cfg["years"])
        z = np.load(Path("artifacts/runs") / run / "estimates.npz")
        s = SOURCE_FAMILIES.index(family)
        mu = district_estimates(t, z["lam"], z["rho"])
        for year in cfg["split"]["validation"][family] + cfg["split"]["test"][family]:
            ti = t.years.index(year)
            obs = t.events_total[s, ti]
            model = mu[s, ti]
            base = historical_average(t, s, ti)[1]
            floor = float(expected_abs_error(model * obs.sum() / model.sum()).mean())
            row = {
                "fold": family,
                "year": year,
                "baseline_mean": mae(base, obs),
                "baseline_median": mae(poisson_median(base), obs),
                "model_mean": mae(model, obs),
                "model_median": mae(poisson_median(model), obs),
                "noise_floor": floor,
            }
            b = row["baseline_mean"]
            row["max_improvement_pct"] = (b - floor) / b * 100
            row["achieved_improvement_pct"] = (b - row["model_mean"]) / b * 100
            report.append(row)
            print(json.dumps(row), flush=True)
    out = Path("evidence/benchmarking/performance-v7/noise_ceiling.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
