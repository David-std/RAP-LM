"""V9 selection on validation average precision; test scored once. See docs/ml/performance-v9.md."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ml.experiments.ensemble_select import WEIGHTS, year_scores
from ml.experiments.long_memory import FOLDS
from ml.fused.tensors import load_dataset
from pipelines.fusion.events import SOURCE_FAMILIES

MEMBERS = Path("artifacts/runs/performance-v9-members")
OUT = Path("evidence/benchmarking/performance-v9")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for fold in ("cenacom", "onsv"):
        cfg = json.loads((Path("ml/configs") / FOLDS[fold]).read_text(encoding="utf-8"))
        t = load_dataset(Path("artifacts/datasets/fused-v1.4.0"), cfg["years"])
        s = SOURCE_FAMILIES.index(fold)
        (vy,) = cfg["split"]["validation"][fold]
        (ty,) = cfg["split"]["test"][fold]
        vi, ti = t.years.index(vy), t.years.index(ty)
        rows = {}
        for name, seeds in (("v9-5", range(1, 6)), ("v9-10", range(1, 11))):
            zs = [np.load(MEMBERS / fold / f"s{k}.npz") for k in seeds]
            mu_d = np.mean([z["mu_district_total"] for z in zs], axis=0)
            mu_c = np.mean([z["mu_cell"] for z in zs], axis=0)
            val = {float(w): year_scores(t, mu_d, mu_c, s, vi, w) for w in WEIGHTS}
            w = max(val, key=lambda k: (val[k]["cell_year"]["average_precision"], k))
            for label, weight in ((name, 1.0), (f"{name}+hist", w)):
                rows[label] = {"weight": weight, "validation": val[weight], "mu": (mu_d, mu_c)}
        best = max(
            rows, key=lambda k: (rows[k]["validation"]["cell_year"]["average_precision"], -len(k))
        )
        mu_d, mu_c = rows[best]["mu"]
        test = year_scores(t, mu_d, mu_c, s, ti, rows[best]["weight"])
        hist = year_scores(t, mu_d, mu_c, s, ti, 0.0)
        report[fold] = {
            "validation_year": vy,
            "test_year": ty,
            "validation": {k: {"weight": r["weight"], **r["validation"]} for k, r in rows.items()},
            "selected": best,
            "test": test,
            "test_historical_average": hist,
        }
        for k, r in rows.items():
            v = r["validation"]
            print(
                fold,
                "VAL",
                k,
                r["weight"],
                round(v["improvement_pct"], 2),
                {
                    m: round(v["cell_year"][m], 3)
                    for m in ("auc", "average_precision", "capture_top10", "capture_top20")
                },
                flush=True,
            )
        print(
            fold,
            "TEST",
            best,
            round(test["improvement_pct"], 2),
            {
                m: round(test["cell_year"][m], 3)
                for m in ("auc", "average_precision", "capture_top10", "capture_top20")
            },
            "HA",
            {
                m: round(hist["cell_year"][m], 3)
                for m in ("auc", "average_precision", "capture_top10", "capture_top20")
            },
            flush=True,
        )
    (OUT / "selection.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
