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

from pipelines.fusion.context import CONTEXT_VARIABLES, annual_population, build_context
from pipelines.fusion.events import (
    COVERAGE,
    SOURCE_FAMILIES,
    allocate,
    read_events,
)
from pipelines.fusion.geocode import DistrictStreetIndex
from pipelines.fusion.streets import extract_streets, read_streets, write_streets
from pipelines.fusion.vehicles import vehicle_profiles
from pipelines.lineage import git_sha, tree_is_clean
from pipelines.spatial.grid import build_grid, load_districts, write_districts, write_grid

# Dataset versions by population mode (D-12). Both carry vehicle type, transport
# service and recorded factors; they differ only in the population input:
# v1.1.1 keeps the fixed 2020 surface (network inputs identical to v1.1, so the
# published v2 weights can be exported with it); v1.3.0 uses annual population.
DATASET_VERSIONS = {"static": "fused-v1.1.1", "annual": "fused-v1.3.0"}
STATIC_POPULATION = {
    "label": "Resident population",
    "source_id": "worldpop_2020",
    "reference_year": "2020",
}


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
    parser.add_argument("--population", choices=("annual", "static"), default="annual")
    args = parser.parse_args()
    # Lineage is captured before any work so later commits cannot change it.
    code_sha, code_clean = git_sha(), tree_is_clean()
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
    profiles, vehicle_report = vehicle_profiles(args.raw, args.harmonized)
    unknown = {"no_identificado": 1.0}
    for e in events:
        e.vehicles, e.service, e.factors = profiles.get(
            e.event_id, (unknown, unknown, ["sin_causa"])
        )
    print(f"fused events: {len(events)}; vehicle linkage {vehicle_report}")

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
                "collision_type",
                "severity",
                "vehicles",
                "service",
                "factors",
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
                    e.collision_type,
                    e.severity,
                    json.dumps(e.vehicles, separators=(",", ":"), sort_keys=True),
                    json.dumps(e.service, separators=(",", ":"), sort_keys=True),
                    "|".join(e.factors),
                    json.dumps(
                        {k: round(v, 6) for k, v in e.allocation.items()}, separators=(",", ":")
                    ),
                ]
            )

    context = build_context(args.raw, spec, cells, streets)
    annual: dict[str, np.ndarray] = {}
    pop_sources: list[dict] = []
    if args.population == "annual":
        pop_years, pop_by_year, pop_sources = annual_population(args.raw, spec, cells)
        annual = {
            "population_years": np.array(pop_years),
            "population_by_year": pop_by_year.astype(np.float32),
        }
    np.savez_compressed(
        out / "context.npz",
        unit_ids=np.array([c.unit_id for c in cells]),
        **annual,
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
        "vehicle_linkage": vehicle_report,
    }
    (out / "fusion_report.json").write_text(json.dumps(geocoding, indent=2), encoding="utf-8")

    manifest = {
        "dataset_version": DATASET_VERSIONS[args.population],
        "target_population": "all_pedestrian_collisions",
        "target_definition": (
            "Every recorded collision with a pedestrian involved (run over, hit-and-run, "
            "collision followed by run over, or any crash with a pedestrian victim), "
            "regardless of severity."
        ),
        "created_unix": int(started),
        "code_commit_sha": code_sha,
        "code_tree_clean": code_clean,
        "python": platform.python_version(),
        "grid": spec.to_dict() | {"cells": len(cells), "districts": len(districts)},
        "coverage": {
            fam: {str(y): [s.isoformat(), e.isoformat()] for y, (s, e) in win.items()}
            for fam, win in COVERAGE.items()
        },
        "context_variables": [
            v.__dict__ | STATIC_POPULATION
            if v.variable_id == "population" and args.population == "static"
            else v.__dict__
            for v in CONTEXT_VARIABLES
        ],
        "inputs": {
            "boundary": {"path": boundary.name, "sha256": sha256(boundary)},
            "osm_extract": {"path": pbf.name, "sha256": sha256(pbf)},
            "harmonized_events": {"path": args.harmonized.name, "sha256": sha256(args.harmonized)},
            "population_annual": pop_sources,
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
