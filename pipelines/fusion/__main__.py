"""Build a versioned fused dataset (WBS 3.2.1; HT-05, HT-06; RD-03..RD-06, RNF-02).

Usage::

    python -m pipelines.fusion \
        --raw <RAP-LM-DATA dir> \
        --harmonized <RAP-LM-HARMONIZED/data/harmonized_crash_events.csv> \
        --out artifacts/datasets/fused-v1.0.0

Outputs (outside Git; see .gitignore): grid/district GeoJSON, fused events,
per-cell context, geocoding report and ``dataset_manifest.json`` with SHA-256
of every input and output.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import time
from collections import Counter
from pathlib import Path

import numpy as np

from pipelines.fusion.context import CONTEXT_VARIABLES, build_context
from pipelines.fusion.events import (
    COVERAGE,
    SOURCE_FAMILIES,
    allocate,
    read_events,
)
from pipelines.fusion.geocode import DistrictStreetIndex
from pipelines.fusion.streets import extract_streets, read_streets, write_streets
from pipelines.lineage import git_sha, tree_is_clean
from pipelines.spatial.grid import build_grid, load_districts, write_districts, write_grid

DATASET_VERSION = "fused-v1.0.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--harmonized", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cell-size", type=int, default=1000)
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()

    boundary = args.raw / "geography/boundaries/lima_43_districts_inei.geojson"
    districts = load_districts(boundary)
    spec, cells = build_grid(districts, args.cell_size)
    write_grid(out / "grid.geojson", spec, cells)
    write_districts(out / "districts.geojson", districts)
    print(f"grid: {spec.rows}x{spec.cols}, {len(cells)} cells, {len(districts)} districts")

    streets_path = out / "streets.json"
    pbf = args.raw / "geography/roads/osm/Lima.osm.pbf"
    if streets_path.exists():
        streets = read_streets(streets_path)
    else:
        streets = extract_streets(pbf)
        write_streets(streets_path, streets)
    print(f"named streets: {len(streets)}")

    indexes = {d.ubigeo: DistrictStreetIndex(d, streets) for d in districts}
    events, report = read_events(args.harmonized, districts, indexes)
    allocate(events, spec, cells)
    print(f"fused events: {len(events)}")

    with (out / "events.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "event_id",
                "source_id",
                "family",
                "year",
                "day_type",
                "band",
                "district_ubigeo",
                "location_basis",
                "precision",
                "matched_streets",
                "pedestrian_injured",
                "pedestrian_deceased",
                "allocation",
            ]
        )
        for e in events:
            writer.writerow(
                [
                    e.event_id,
                    e.source_id,
                    e.family,
                    e.year,
                    e.day_type,
                    e.band,
                    e.district_ubigeo,
                    e.location_basis,
                    e.precision,
                    "|".join(e.matched_streets),
                    "" if e.injured is None else e.injured,
                    "" if e.deceased is None else e.deceased,
                    json.dumps(
                        {k: round(v, 6) for k, v in e.allocation.items()}, separators=(",", ":")
                    ),
                ]
            )

    context = build_context(args.raw, spec, cells, streets)
    np.savez_compressed(
        out / "context.npz",
        unit_ids=np.array([c.unit_id for c in cells]),
        **{k: v.astype(np.float32) for k, v in context.items()},
    )

    precision = Counter((e.family, e.precision) for e in events)
    geocoding = {
        "rules": "pipelines/fusion/geocode.py module docstring",
        "precision_by_family": {f"{f}:{p}": n for (f, p), n in sorted(precision.items())},
        "located_share_by_family": {
            fam: round(
                sum(n for (f, p), n in precision.items() if f == fam and p != "district")
                / max(1, sum(n for (f, _), n in precision.items() if f == fam)),
                4,
            )
            for fam in SOURCE_FAMILIES
        },
        **report.to_dict(),
    }
    (out / "fusion_report.json").write_text(json.dumps(geocoding, indent=2), encoding="utf-8")

    manifest = {
        "dataset_version": DATASET_VERSION,
        "target_population": "all_pedestrian_collisions",
        "target_definition": (
            "Every recorded collision with a pedestrian involved (run over, hit-and-run, "
            "collision followed by run over, or any crash with a pedestrian victim), "
            "regardless of severity."
        ),
        "created_unix": int(started),
        "code_commit_sha": git_sha(),
        "code_tree_clean": tree_is_clean(),
        "python": platform.python_version(),
        "grid": spec.to_dict() | {"cells": len(cells), "districts": len(districts)},
        "coverage": {
            fam: {str(y): [s.isoformat(), e.isoformat()] for y, (s, e) in win.items()}
            for fam, win in COVERAGE.items()
        },
        "context_variables": [v.__dict__ for v in CONTEXT_VARIABLES],
        "inputs": {
            "boundary": {"path": boundary.name, "sha256": sha256(boundary)},
            "osm_extract": {"path": pbf.name, "sha256": sha256(pbf)},
            "harmonized_events": {"path": args.harmonized.name, "sha256": sha256(args.harmonized)},
        },
        "outputs": {
            p.name: sha256(p)
            for p in sorted(out.iterdir())
            if p.is_file() and p.name != "dataset_manifest.json"
        },
        "fusion_report": geocoding,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    (out / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(geocoding["precision_by_family"], indent=2))
    print(json.dumps(geocoding["excluded_by_reason"], indent=2))


if __name__ == "__main__":
    main()
