"""V8 selection: validation-only choice among fixed ensembles, single test scoring.

See docs/ml/performance-v8.md.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ml.experiments.ranking_report import scores
from ml.fused.tensors import load_dataset
from ml.fused.train import historical_average
from pipelines.fusion.events import SOURCE_FAMILIES

FOLDS = {"onsv": "v4-main.json", "cenacom": "v4-backtest-2017.json"}
WEIGHTS = np.round(np.arange(0, 1.0001, 0.05), 2)


def candidates(pool: list[dict]) -> dict[str, list[tuple[int, int]]]:
    best = {}
    for i, c in enumerate(pool):
        best.setdefault(c["variant"], i)
    seeds10 = range(1, 11)
    return {
        "A": [(0, s) for s in range(1, 6)],
        "B": [(0, s) for s in seeds10],
        "C": [(i, s) for i in sorted(best.values()) for s in seeds10],
        "D": [(i, s) for i in range(len(pool)) for s in seeds10],
    }


def year_scores(t, mu_dist, mu_cell, s, ti, w):
    obs_d = t.events_total[s, ti]
    base_cell, base_dist = historical_average(t, s, ti)
    pred_d = w * mu_dist[s, ti] + (1 - w) * base_dist
    base_mae = float(np.abs(base_dist - obs_d).mean())
    mae = float(np.abs(pred_d - obs_d).mean())
    cell_score = (w * mu_cell[s, ti] + (1 - w) * base_cell).sum(axis=0)[t.valid]
    obs_c = t.y_cell[s, ti].sum(axis=0)[t.valid]
    rank = scores(obs_c, cell_score, obs_c >= 0.5)
    return {
        "district_mae": mae,
        "baseline_mae": base_mae,
        "improvement_pct": (base_mae - mae) / base_mae * 100,
        "cell_year": rank,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--members", type=Path, default=Path("artifacts/runs/performance-v8-members"))
    ap.add_argument("--dataset", type=Path, default=Path("artifacts/datasets/fused-v1.4.0"))
    ap.add_argument("--out", type=Path, default=Path("evidence/benchmarking/performance-v8"))
    ap.add_argument("--folds", default="onsv,cenacom")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report = {}
    for fold in args.folds.split(","):
        cfg = json.loads((Path("ml/configs") / FOLDS[fold]).read_text(encoding="utf-8"))
        t = load_dataset(args.dataset, cfg["years"])
        s = SOURCE_FAMILIES.index(fold)
        (vy,) = cfg["split"]["validation"][fold]
        (ty,) = cfg["split"]["test"][fold]
        vi, ti = t.years.index(vy), t.years.index(ty)
        pool = json.loads((args.members / fold / "pool.json").read_text(encoding="utf-8"))
        members = {}
        rows = {}
        for name, keys in candidates(pool).items():
            for k in keys:
                if k not in members:
                    z = np.load(args.members / fold / f"c{k[0]}_s{k[1]}.npz")
                    members[k] = (z["mu_district_total"], z["mu_cell"])
            mu_d = np.mean([members[k][0] for k in keys], axis=0)
            mu_c = np.mean([members[k][1] for k in keys], axis=0)
            val = {float(w): year_scores(t, mu_d, mu_c, s, vi, w) for w in WEIGHTS}
            w_best = min(val, key=lambda w: (val[w]["district_mae"], -w))
            rows[name] = {
                "members": len(keys),
                "mu": (mu_d, mu_c),
                "val_model": val[1.0],
                "w": w_best,
                "val_comb": val[w_best],
            }
        options = [(r["val_model"]["district_mae"], r["members"], n, 1.0) for n, r in rows.items()]
        options += [
            (r["val_comb"]["district_mae"], r["members"], n, r["w"]) for n, r in rows.items()
        ]
        _, _, sel_name, sel_w = min(options)
        out = {
            "validation_year": vy,
            "test_year": ty,
            "pool": pool,
            "selected": {"candidate": sel_name, "weight": sel_w},
        }
        out["validation"] = {
            n: {
                "members": r["members"],
                "model_only": r["val_model"],
                "combined": {"weight": r["w"], **r["val_comb"]},
            }
            for n, r in rows.items()
        }
        test = {}
        for n, w in (("A", 1.0), (sel_name, 1.0), (sel_name, sel_w)):
            mu_d, mu_c = rows[n]["mu"]
            test[f"{n}@{w}"] = year_scores(t, mu_d, mu_c, s, ti, w)
        out["test"] = test
        report[fold] = out
        print(json.dumps({"fold": fold, "selected": out["selected"]}), flush=True)
        for n, r in out["validation"].items():
            print(
                fold,
                "val",
                n,
                r["members"],
                round(r["model_only"]["improvement_pct"], 2),
                "comb",
                r["combined"]["weight"],
                round(r["combined"]["improvement_pct"], 2),
                "AP",
                round(r["model_only"]["cell_year"]["average_precision"], 3),
                "AUC",
                round(r["model_only"]["cell_year"]["auc"], 3),
                flush=True,
            )
        for n, r in test.items():
            print(
                fold,
                "TEST",
                n,
                round(r["improvement_pct"], 2),
                "AUC",
                round(r["cell_year"]["auc"], 3),
                "AP",
                round(r["cell_year"]["average_precision"], 3),
                "cap20",
                round(r["cell_year"]["capture_top20"], 3),
                flush=True,
            )
    (args.out / "selection.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
