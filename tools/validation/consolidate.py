"""Consolidate specialist sessions into M-10, M-11 and M-12 (WBS 4.5).

Usage::

    python -m tools.validation.consolidate <sessions.csv> <answers.csv> [--out DIR]

Denominators are kept explicit. With no rows the metrics are written as
"not_measured" (an empty denominator never counts as met).
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def seconds(row: dict) -> float:
    return (
        datetime.fromisoformat(row["ended_at"]) - datetime.fromisoformat(row["started_at"])
    ).total_seconds()


def consolidate(sessions: list[dict], answers: list[dict]) -> dict:
    started = {
        p: [r for r in sessions if r["procedure"] == p and r["outcome"] != "not_feasible"]
        for p in ("mvp", "onsv")
    }
    success = {p: sum(r["outcome"] == "correct" for r in rows) for p, rows in started.items()}

    times: dict[str, dict[tuple[str, str], float]] = defaultdict(dict)
    for r in sessions:
        if r["outcome"] == "correct":
            times[r["procedure"]][(r["participant"], r["task"])] = seconds(r)
    paired = set(times["mvp"]) & set(times["onsv"])
    mean = {
        p: (sum(times[p][k] for k in paired) / len(paired)) if paired else None
        for p in ("mvp", "onsv")
    }

    interp = [a for a in answers if a["item"].startswith("Q") and a["correct"] != ""]
    utility = [
        float(a["utility_score"])
        for a in answers
        if a["item"].startswith("U") and a["utility_score"]
    ]

    def pct(n, d):
        return round(n / d * 100, 2) if d else None

    return {
        "participants": sorted({r["participant"] for r in sessions}),
        "M-10": {
            "numerator": success["mvp"],
            "denominator": len(started["mvp"]),
            "value": pct(success["mvp"], len(started["mvp"])),
            "reference_value": pct(success["onsv"], len(started["onsv"])),
            "target": ">= 80 % and >= reference",
        },
        "M-11": {
            "paired_correct_tasks": len(paired),
            "mean_seconds_mvp": mean["mvp"],
            "mean_seconds_onsv": mean["onsv"],
            "value": (
                round((mean["onsv"] - mean["mvp"]) / mean["onsv"] * 100, 2)
                if paired and mean["onsv"]
                else None
            ),
            "target": "> 0 %",
        },
        "M-12a": {
            "numerator": sum(a["correct"] == "1" for a in interp),
            "denominator": len(interp),
            "value": pct(sum(a["correct"] == "1" for a in interp), len(interp)),
            "target": ">= 80 %",
        },
        "M-12b": {
            "responses": len(utility),
            "value": round(sum(utility) / len(utility), 3) if utility else None,
            "target": ">= 4",
        },
        "status": "measured" if sessions else "not_measured: no session recorded",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", type=Path)
    ap.add_argument("answers", type=Path)
    ap.add_argument("--out", type=Path, default=Path("evidence/validation"))
    a = ap.parse_args()
    read = lambda p: list(csv.DictReader(p.open(encoding="utf-8")))  # noqa: E731
    result = consolidate(read(a.sessions), read(a.answers))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "M-10_M-12.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
