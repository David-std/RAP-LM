"""Compare the same run configuration trained on CPU and on GPU (plan resource: GPU).

Usage::

    python -m tools.reports.device_comparison \
        --cpu artifacts/runs/<run> --gpu artifacts/runs/<run>

Writes evidence/benchmarking/device_comparison.json: training time of the search
plus ensemble on each device, ensemble validation error, and agreement of the
exported results (risk level and relative difference of the indicator). The GPU
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
    }


def results(run: Path) -> dict[tuple[str, str, str], tuple[float, str]]:
    with (run / "results.csv").open(encoding="utf-8", newline="") as f:
        return {
            (r["representation_id"], r["unit_id"], r["period_id"]): (
                float(r["indicator_value"] or 0),
                r["risk_level"],
            )
            for r in csv.DictReader(f)
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=Path, required=True)
    ap.add_argument("--gpu", type=Path, required=True)
    args = ap.parse_args()
    a, b = results(args.cpu), results(args.gpu)
    keys = sorted(set(a) & set(b))
    level = sum(a[k][1] == b[k][1] for k in keys)
    rel = [abs(b[k][0] - a[k][0]) / a[k][0] * 100 for k in keys if a[k][0] > 0]
    out = {
        "runs": [summary(args.cpu), summary(args.gpu)],
        "units_periods": len(keys),
        "level_match_pct": round(level / len(keys) * 100, 2),
        "median_rel_diff_pct": round(statistics.median(rel), 3),
        "p95_rel_diff_pct": round(sorted(rel)[int(0.95 * (len(rel) - 1))], 3),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
