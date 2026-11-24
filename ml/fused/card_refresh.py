"""Add evaluation reports to an existing model card without recomputing explanations.

Usage::

    python -m ml.fused.card_refresh --run artifacts/runs/<run_id> \
        --prioritisation evidence/benchmarking/performance-v7/ranking_test.json \
        --noise-ceiling evidence/benchmarking/performance-v7/noise_ceiling.json

Copies each report into the run directory (``prioritisation.json``,
``noise_ceiling.json``), the same files ``explain.py`` reads, and updates
``explanations/card.json``. Republish with ``pipelines.publication.extras``.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--prioritisation", type=Path)
    ap.add_argument("--noise-ceiling", type=Path)
    args = ap.parse_args()
    card_path = args.run / "explanations" / "card.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    for key, src in (
        ("prioritisation", args.prioritisation),
        ("noise_ceiling", args.noise_ceiling),
    ):
        if src is None:
            continue
        dst = args.run / f"{key}.json"
        shutil.copyfile(src, dst)
        card[key] = json.loads(dst.read_text(encoding="utf-8"))
    card_path.write_text(json.dumps(card), encoding="utf-8")
    print("card updated:", card_path)


if __name__ == "__main__":
    main()
