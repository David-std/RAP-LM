"""Publish analyst layers of an already published run (corridors, explanations, card).

Usage::

    RAPLM_PUBLISHER_URL=... python -m pipelines.publication.extras \
        --dataset artifacts/datasets/fused-v1.0.0 --run artifacts/runs/<run_id>

One transaction: previous layers of the same run are replaced; nothing else
changes. Requires ``ml.fused.explain`` and ``pipelines.fusion.corridors``
outputs. Decision D-09.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb


def publish_extras(url: str, dataset: Path, run: Path) -> dict:
    run_id = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))["run_id"]
    ex = run / "explanations"
    series = json.loads((ex / "series.json").read_text(encoding="utf-8"))
    attribution = json.loads((ex / "attribution.json").read_text(encoding="utf-8"))
    whatif = json.loads((ex / "whatif.json").read_text(encoding="utf-8"))
    card = json.loads((ex / "card.json").read_text(encoding="utf-8"))
    corridors = json.loads((dataset / "corridors.geojson").read_text(encoding="utf-8"))

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM model_run WHERE run_id = %s", (run_id,))
        row = cur.fetchone()
        if not row or row[0] != "published":
            raise SystemExit(f"run {run_id} is not published")
        for table in ("corridor", "unit_explanation", "model_card"):
            cur.execute(f"DELETE FROM {table} WHERE run_id = %s", (run_id,))  # noqa: S608
        cur.execute(
            "INSERT INTO model_card VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                run_id,
                Jsonb(card),
                Jsonb(series["years"]),
                Jsonb(series["observing_family"]),
                attribution["year"],
                Jsonb(attribution["groups"]),
                Jsonb(whatif["factors"]),
                Jsonb(whatif["variables"]),
                Jsonb(corridors["summary"]),
            ),
        )
        n_units = 0
        for rep, key in (("grid-1km", "cell"), ("district-43", "district")):
            for unit_id, s in series[key].items():
                cur.execute(
                    "INSERT INTO unit_explanation VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        run_id,
                        rep,
                        unit_id,
                        Jsonb(s["expected"]),
                        Jsonb(s["observed"]),
                        Jsonb(attribution[key][unit_id]),
                        Jsonb(whatif["district"].get(unit_id)) if key == "district" else None,
                    ),
                )
                n_units += 1
        for f in corridors["features"]:
            p = f["properties"]
            cur.execute(
                """INSERT INTO corridor VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   %s, %s, %s, %s,
                   ST_Multi(ST_CollectionExtract(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 2)))""",
                (
                    run_id,
                    p["corridor_id"],
                    p["district_id"],
                    p["street"],
                    p["length_km"],
                    p["events"],
                    p["events_per_km"],
                    p["rank"],
                    p["cumulative_event_share"],
                    p["injured"],
                    p["deceased"],
                    p["mean_risk_index"],
                    Jsonb(p["by_family"]),
                    Jsonb(p["by_year"]),
                    Jsonb(p["by_subperiod"]),
                    Jsonb(p["located_via"]),
                    json.dumps(f["geometry"]),
                ),
            )
    return {"run_id": run_id, "explained_units": n_units, "corridors": len(corridors["features"])}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--run", type=Path, required=True)
    args = ap.parse_args()
    url = os.environ.get("RAPLM_PUBLISHER_URL")
    if not url:
        raise SystemExit("Set RAPLM_PUBLISHER_URL (raplm_publisher role)")
    url = url.replace("postgresql+psycopg://", "postgresql://")
    print(json.dumps(publish_extras(url, args.dataset, args.run), indent=2))


if __name__ == "__main__":
    main()
