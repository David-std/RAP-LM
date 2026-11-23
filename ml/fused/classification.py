"""High-level classification errors (plan v1.6, model evaluation paragraph).

"A false positive is a unit classified as high whose reference category is
lower; a false negative is a reference-high unit classified below that level."
Model, baseline and observed reference are placed on the **same frozen scale**:
each value is converted to the annualised density of the latent intensity and
ranked in the reference distribution of the training-year estimates, then cut
with the frozen thresholds (levels-v1).

Observed reference for a test family-year: located events of the cell,
divided by coverage, located share and the family's reporting factor (so a
fatal-only observation is brought to the all-severity scale), annualised per
km2. This is a noisy reference (a cell with one event jumps to a high
percentile), which is why the counts are reported, not only the ratios.
"""

from __future__ import annotations

import numpy as np

from ml.fused.tensors import Tensors
from pipelines.fusion.events import SOURCE_FAMILIES, SUBPERIODS, days_of_type


def _density(t: Tensors, counts_cell: np.ndarray, ti: int, area_floor: float) -> np.ndarray:
    """[K, H, W] latent-scale counts -> annualised density per km2."""
    days = np.array([days_of_type(t.years[ti], dt) for (dt, _b) in SUBPERIODS], dtype=float)
    area = np.maximum(t.area_km2, area_floor)
    return counts_cell / days[:, None, None] * 365.0 / np.where(t.valid, area, 1.0)


def _levels(values: np.ndarray, reference: np.ndarray, low: float, mid: float) -> np.ndarray:
    pct = np.searchsorted(reference, values, side="right") / reference.size * 100
    return np.where(pct >= mid, 2, np.where(pct >= low, 1, 0))


def _confusion(pred_high: np.ndarray, ref_high: np.ndarray) -> dict[str, float]:
    tp = int(np.sum(pred_high & ref_high))
    fp = int(np.sum(pred_high & ~ref_high))
    fn = int(np.sum(~pred_high & ref_high))
    tn = int(np.sum(~pred_high & ~ref_high))
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def high_level_report(
    t: Tensors,
    pred: dict[str, np.ndarray],
    baseline_cell: dict[tuple[str, int], np.ndarray | None],
    reference: np.ndarray,
    thresholds: dict,
    years_by_family: dict[str, list[int]],
    area_floor: float,
) -> list[dict]:
    """Confusion of the 'high' level for model and baseline, per test family-year."""
    low, mid = thresholds["low_max"], thresholds["medium_max"]
    rows = []
    rho = pred["rho"]
    for s, fam in enumerate(SOURCE_FAMILIES):
        for y in years_by_family.get(fam, []):
            ti = t.years.index(y)
            if t.cover[s, ti].max() <= 0:
                continue
            q = max(float(t.located[s, ti]), 1e-6)
            scale = (t.cover[s, ti] * q * rho[s])[:, None, None]  # [K,1,1]
            observed = _density(t, t.y_cell[s, ti] / np.maximum(scale, 1e-9), ti, area_floor)
            model = _density(t, pred["lambda"][ti], ti, area_floor)
            mask = np.broadcast_to(t.valid, observed.shape)
            ref_high = _levels(observed[mask], reference, low, mid) == 2
            row = {
                "family": fam,
                "year": y,
                "units": int(mask.sum()),
                "reference_high": int(ref_high.sum()),
                "model": _confusion(_levels(model[mask], reference, low, mid) == 2, ref_high),
            }
            base = baseline_cell.get((fam, y))
            if base is not None:
                base_density = _density(t, base / np.maximum(scale, 1e-9), ti, area_floor)
                row["baseline"] = _confusion(
                    _levels(base_density[mask], reference, low, mid) == 2, ref_high
                )
            rows.append(row)
    return rows


def main() -> None:
    """CLI: --dataset <dir> --run <dir>; writes <run>/high_level.json."""
    import argparse
    import json
    from pathlib import Path

    from ml.fused.tensors import load_dataset
    from ml.fused.train import historical_average

    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--run", type=Path, required=True)
    args = ap.parse_args()
    cfg = json.loads((args.run / "run_manifest.json").read_text(encoding="utf-8"))["config"]
    t = load_dataset(args.dataset, cfg["years"])
    est = np.load(args.run / "estimates.npz")
    pred = {"lambda": est["lam"], "rho": est["rho"]}
    baseline = {}
    for s, fam in enumerate(SOURCE_FAMILIES):
        for y in cfg["split"]["test"].get(fam, []):
            hist = historical_average(t, s, t.years.index(y))
            baseline[(fam, y)] = None if hist is None else hist[0]
    rows = high_level_report(
        t,
        pred,
        baseline,
        est["reference"],
        cfg["thresholds"],
        cfg["split"]["test"],
        cfg["area_floor_km2"],
    )
    (args.run / "high_level.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
