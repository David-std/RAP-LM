"""Post-hoc forecast combination of published v4 estimates with the historical average.

Rule fixed before looking at test years: for each fold, the convex weight
w in {0, .05, ..., 1} on the model (1 - w on the historical average) is the one
with the lowest district x subperiod MAE on that fold's validation year. The same
w is then applied once to the fold's test year. No retraining, no new data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ml.fused.tensors import load_dataset
from ml.fused.train import historical_average
from pipelines.fusion.events import SOURCE_FAMILIES

FOLDS = (
    ("onsv", "fused-cnnlstm-2026.11-v4", "v4-main.json"),
    ("cenacom", "fused-cnnlstm-backtest-2017-v4", "v4-backtest-2017.json"),
)
GRID = np.round(np.arange(0, 1.0001, 0.05), 2)


def district_estimates(t, lam, rho):
    total = np.einsum("tkhw,dhw->tkd", lam, t.frac)
    return total[None] * (rho[:, None, None] * t.cover)[..., None]


def fold_scores(t, mu, family, year):
    s = SOURCE_FAMILIES.index(family)
    ti = t.years.index(year)
    obs = t.events_total[s, ti]
    _, base = historical_average(t, s, ti)
    model = mu[s, ti]
    base_mae = float(np.abs(base - obs).mean())
    out = {}
    for w in GRID:
        mae = float(np.abs(w * model + (1 - w) * base - obs).mean())
        out[float(w)] = {"mae": mae, "improvement_pct": (base_mae - mae) / base_mae * 100}
    return base_mae, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("artifacts/datasets/fused-v1.4.0"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = []
    for family, run, cfg_name in FOLDS:
        cfg = json.loads((Path("ml/configs") / cfg_name).read_text(encoding="utf-8"))
        train_years = sorted({y for ys in cfg["split"]["train"].values() for y in ys})
        t = load_dataset(args.dataset, cfg["years"], norm_years=train_years)
        z = np.load(Path("artifacts/runs") / run / "estimates.npz")
        assert list(z["years"]) == t.years
        mu = district_estimates(t, z["lam"], z["rho"])
        (vy,) = cfg["split"]["validation"][family]
        (ty,) = cfg["split"]["test"][family]
        vbase, val = fold_scores(t, mu, family, vy)
        w = min(val, key=lambda k: (val[k]["mae"], -k))
        tbase, test = fold_scores(t, mu, family, ty)
        report.append(
            {
                "fold": family,
                "run": run,
                "validation_year": vy,
                "test_year": ty,
                "selected_weight": w,
                "validation": {"baseline_mae": vbase, "model_only": val[1.0], "combined": val[w]},
                "test": {"baseline_mae": tbase, "model_only": test[1.0], "combined": test[w]},
                "test_curve": test,
            }
        )
        print(json.dumps({k: v for k, v in report[-1].items() if k != "test_curve"}, indent=1))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "combination.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
