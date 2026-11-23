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

Why the precision of the "high" level is low on fatal-only test years: the
level is a percentile of a continuous risk scale (index >= 70), so the model
marks a large share of cell-subperiods as high, while the fatal-only reference
is rare (a few hundred cell-subperiods). Precision is then bounded by
positives / predicted-high even for a perfect ranking. The ranking block
therefore adds measures that do not depend on that mismatch, for model and
baseline alike: precision at k = number of reference positives, average
precision (area under the precision-recall curve, chance level = base rate),
and precision, recall and F1 at an index threshold chosen on the validation
year only (maximum F1) and applied once to the test year.
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


def _average_precision(score: np.ndarray, positive: np.ndarray) -> float | None:
    """Area under the precision-recall curve (step interpolation)."""
    n_pos = int(positive.sum())
    if n_pos == 0:
        return None
    order = np.argsort(-score, kind="stable")
    hits = positive[order].astype(float)
    precision_at = np.cumsum(hits) / np.arange(1, hits.size + 1)
    return float((precision_at * hits).sum() / n_pos)


def _ranking(score: np.ndarray, positive: np.ndarray, threshold: float | None) -> dict:
    """Precision at k (k = positives), average precision and metrics at a fixed threshold."""
    k = int(positive.sum())
    order = np.argsort(-score, kind="stable")
    out: dict = {
        "k": k,
        "precision_at_k": float(positive[order[:k]].mean()) if k else None,
        "average_precision": _average_precision(score, positive),
    }
    if threshold is not None:
        out["at_validation_threshold"] = _confusion(score >= threshold, positive)
    return out


def _annual(t: Tensors, s: int, ti: int, lam: np.ndarray, base: np.ndarray | None) -> dict:
    """Operational grain: 1 km cells over the whole year (all day types and bands).

    A cell is positive when it holds at least half a located event of the family in
    the year (street-allocated events are split among cells). Scores are the yearly
    expected counts; capture is the share of positive cells inside the top 10 %.
    """
    positive = t.y_cell[s, ti].sum(axis=0)[t.valid] >= 0.5
    out = {"cells": int(positive.size), "positives": int(positive.sum())}
    scorers = {"model": lam.sum(axis=0)[t.valid]}
    if base is not None:
        scorers["baseline"] = base.sum(axis=0)[t.valid]
    top = max(1, int(0.1 * positive.size))
    for name, score in scorers.items():
        rank = _ranking(score, positive, None)
        order = np.argsort(-score, kind="stable")
        rank["capture_top10"] = float(positive[order[:top]].sum() / max(positive.sum(), 1))
        out[name] = rank
    return out


def best_threshold(score: np.ndarray, positive: np.ndarray) -> float | None:
    """Index threshold with maximum F1 (ties: the higher threshold)."""
    if not positive.any():
        return None
    best, best_f1 = None, -1.0
    for th in np.unique(np.round(score, 1))[::-1]:
        f1 = _confusion(score >= th, positive)["f1"] or 0.0
        if f1 > best_f1:
            best, best_f1 = float(th), f1
    return best


def high_level_report(
    t: Tensors,
    pred: dict[str, np.ndarray],
    baseline_cell: dict[tuple[str, int], np.ndarray | None],
    reference: np.ndarray,
    thresholds: dict,
    years_by_family: dict[str, list[int]],
    area_floor: float,
    thresholds_by_scorer: dict[str, float | None] | None = None,
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
            pct = lambda v: np.searchsorted(reference, v, side="right") / reference.size * 100  # noqa: E731
            th = thresholds_by_scorer or {}
            row = {
                "family": fam,
                "year": y,
                "units": int(mask.sum()),
                "reference_high": int(ref_high.sum()),
                "model": _confusion(_levels(model[mask], reference, low, mid) == 2, ref_high),
                "base_rate": float(ref_high.mean()),
                "model_ranking": _ranking(pct(model[mask]), ref_high, th.get("model")),
                "annual_cell": _annual(t, s, ti, pred["lambda"][ti], baseline_cell.get((fam, y))),
                "model_index": pct(model[mask]),  # removed before writing
                "reference_positive": ref_high,  # removed before writing
            }
            base = baseline_cell.get((fam, y))
            if base is not None:
                base_density = _density(t, base / np.maximum(scale, 1e-9), ti, area_floor)
                row["baseline"] = _confusion(
                    _levels(base_density[mask], reference, low, mid) == 2, ref_high
                )
                row["baseline_ranking"] = _ranking(
                    pct(base_density[mask]), ref_high, th.get("baseline")
                )
                row["baseline_index"] = pct(base_density[mask])  # removed before writing
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

    def baselines(split: dict) -> dict:
        out = {}
        for s, fam in enumerate(SOURCE_FAMILIES):
            for y in split.get(fam, []):
                hist = historical_average(t, s, t.years.index(y))
                out[(fam, y)] = None if hist is None else hist[0]
        return out

    common = (est["reference"], cfg["thresholds"])
    validation = high_level_report(
        t,
        pred,
        baselines(cfg["split"]["validation"]),
        *common,
        cfg["split"]["validation"],
        cfg["area_floor_km2"],
    )
    # Thresholds are chosen on the validation year(s) only, then applied once to test.
    chosen = {
        "model": best_threshold(
            np.concatenate([r["model_index"] for r in validation]),
            np.concatenate([r["reference_positive"] for r in validation]),
        ),
        "baseline": best_threshold(
            np.concatenate([r["baseline_index"] for r in validation if "baseline_index" in r]),
            np.concatenate([r["reference_positive"] for r in validation if "baseline_index" in r]),
        )
        if any("baseline_index" in r for r in validation)
        else None,
    }
    rows = high_level_report(
        t,
        pred,
        baselines(cfg["split"]["test"]),
        *common,
        cfg["split"]["test"],
        cfg["area_floor_km2"],
        chosen,
    )
    for r in rows:
        r["validation_thresholds"] = chosen
    for r in [*rows, *validation]:
        for key in ("model_index", "baseline_index", "reference_positive"):
            r.pop(key, None)
    rows += [{**r, "partition": "validation"} for r in validation]
    (args.run / "high_level.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
