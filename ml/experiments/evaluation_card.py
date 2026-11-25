"""Out-of-sample evidence block of the model card (D-17, D-18).

Collects the single final scoring (v10 T1f/T2f), the chained horizons (V14) and the
ablation (v10 A2) into ``evaluation.json``, which ``ml.fused.card_refresh`` adds to the
card of the published run. Every figure comes from a model trained without the year it
is scored on; the published run's own estimates for those years are in-sample.

    python -m ml.experiments.evaluation_card --out artifacts/runs/<run_id>/evaluation.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

EVIDENCE = Path("evidence/benchmarking")
POPULATION = {
    "cenacom": "Atropellos de todas las severidades",
    "onsv": "Siniestros fatales con peatón",
}
ABLATION = {
    "C0": "Red completa",
    "A_cnn": "Sin recurrencia",
    "A_rnn": "Sin convolución espacial",
    "A_noctx": "Sin contexto urbano",
    "A_nohist": "Sin historial del año anterior",
}


def compact(r: dict) -> dict:
    keep = (
        "auc",
        "average_precision",
        "capture_top5",
        "capture_top10",
        "capture_top20",
        "positives",
    )
    out = {
        "district": {k: r["district"][k] for k in ("mae", "deviance", "spearman", "capture_top20")}
    }
    for stratum in ("all_located", "precise"):
        if r.get(stratum):
            out[stratum] = {k: r[stratum][k] for k in keep}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    final = json.loads(
        (EVIDENCE / "performance-v10/evaluation-T1f-T2f.json").read_text(encoding="utf-8")
    )
    tests = []
    for fold, family, year in (("T1f", "cenacom", 2017), ("T2f", "onsv", 2024)):
        rows = final[fold]
        tests.append(
            {
                "family": family,
                "year": year,
                "population": POPULATION[family],
                "model": compact(rows["C0"]),
                "historical": compact(rows["historical"]),
            }
        )
    horizons = [
        {
            "family": h["family"],
            "last_observed": h["last_observed"],
            "target": h["target"],
            "horizon": h["horizon"],
            "model": compact(h["model"]),
            "historical": compact(h["historical"]),
        }
        for h in json.loads(
            (EVIDENCE / "performance-v14/horizons.json").read_text(encoding="utf-8")
        )
    ]
    dev = json.loads(
        (EVIDENCE / "performance-v10/evaluation-D2b-D3b.json").read_text(encoding="utf-8")
    )
    ablation = []
    for arm, label in (("historical", "Promedio histórico"), *ABLATION.items()):
        a, b = dev["D2b"].get(arm), dev["D3b"].get(arm)
        if a and b:
            ablation.append(
                {
                    "arm": arm,
                    "label": label,
                    "cenacom_2016": {
                        "mae": a["district"]["mae"],
                        "average_precision": a["all_located"]["average_precision"],
                        "auc": a["all_located"]["auc"],
                    },
                    "onsv_2023": {
                        "mae": b["district"]["mae"],
                        "average_precision": b["all_located"]["average_precision"],
                        "auc": b["all_located"]["auc"],
                    },
                }
            )
    payload = {
        "protocol": "docs/ml/performance-v10.md",
        "note": (
            "Models trained without the scored year (fixed 150 epochs); "
            "2017 and 2024 were consulted in earlier iterations."
        ),
        "tests": tests,
        "horizons": horizons,
        "ablation": ablation,
    }
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("evaluation written:", args.out)


if __name__ == "__main__":
    main()
