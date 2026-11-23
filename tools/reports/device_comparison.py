"""Compare the same run configuration trained on CPU and on GPU (plan resource: GPU).

Usage::

    python -m tools.reports.device_comparison \
        --cpu artifacts/runs/<run> --gpu artifacts/runs/<run>

Writes evidence/benchmarking/device_comparison.json: training time of the search
plus ensemble on each device, ensemble validation error, and agreement of the
exported results (risk level, absolute difference and rank correlation of the 0-100 index). The GPU
model name is not recorded, only the device type.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "benchmarking" / "device_comparison.json"


def summary(run: Path) -> dict:
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    return {
        "run_id": manifest["run_id"],
        "device": manifest["config"].get("device", "cpu"),
        "torch": manifest["torch"],
        "minutes": round(manifest["elapsed_seconds"] / 60, 2),
        "validation_E": metrics["validation"][0]["model"]["district_mae"],
        "selected": {
            k: metrics["selected_config"][k] for k in ("variant", "hidden", "dropout", "lr")
        },
    }


def results(run: Path) -> dict[tuple[str, str, str], tuple[float, str]]:
    with (run / "results.csv").open(encoding="utf-8", newline="") as f:
        return {
            (r["representation_id"], r["unit_id"], r["period_id"]): (
                float(r["risk_index"] or 0),
                r["risk_level"],
            )
            for r in csv.DictReader(f)
        }


def spearman(x: list[float], y: list[float]) -> float:
    """Rank correlation (average ranks for ties)."""

    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=v.__getitem__)
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r

    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    sx = sum((a - mx) ** 2 for a in rx) ** 0.5
    sy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (sx * sy)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=Path, required=True)
    ap.add_argument("--gpu", type=Path, required=True)
    args = ap.parse_args()
    a, b = results(args.cpu), results(args.gpu)
    keys = sorted(set(a) & set(b))
    level = sum(a[k][1] == b[k][1] for k in keys)
    diff = sorted(abs(b[k][0] - a[k][0]) for k in keys)
    out = {
        "runs": [summary(args.cpu), summary(args.gpu)],
        "units_periods": len(keys),
        "level_match_pct": round(level / len(keys) * 100, 2),
        "index_mean_abs_diff": round(statistics.fmean(diff), 2),
        "index_p95_abs_diff": round(diff[int(0.95 * (len(diff) - 1))], 2),
        "index_spearman": round(spearman([a[k][0] for k in keys], [b[k][0] for k in keys]), 4),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
