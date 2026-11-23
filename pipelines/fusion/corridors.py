"""Street corridors with recorded pedestrian collisions (analyst view, D-09).

Usage::

    python -m pipelines.fusion.corridors --dataset artifacts/datasets/fused-v1.0.0 \
        --harmonized <harmonized_crash_events.csv> [--results artifacts/runs/<run>/results.csv]

A corridor is one named street inside one district (the part of the OSM
street within the district polygon). Events are assigned without inventing
positions:

* street-precision events -> their matched street (weight 1);
* intersection events -> each of the two matched streets (weight 0.5 each,
  so totals are conserved);
* ONSV points -> the nearest named street of the district within
  ``SNAP_M`` metres (weight 1); otherwise not assigned to a corridor.

District-only events are not assigned to streets. The concentration curve
(share of located events vs share of corridor length, ranked by events per
km) is the analogue of the "high injury network" used by Vision Zero
programmes; like those networks it describes recorded history, it is not a
prediction. With ``--results`` each corridor also gets the length-weighted mean
risk index of the cells it crosses (model estimate, latest published year).
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from shapely.geometry import Point, mapping

from pipelines.fusion.events import SUBPERIODS, TIME_BANDS
from pipelines.fusion.geocode import DistrictStreetIndex
from pipelines.fusion.streets import read_streets
from pipelines.spatial.grid import TO_ANALYSIS, load_districts, to_public

SNAP_M = 60.0


def build(dataset: Path, harmonized: Path, boundary: Path, results: Path | None) -> dict:
    districts = {d.ubigeo: d for d in load_districts(boundary)}
    streets = read_streets(dataset / "streets.json")
    index = {u: DistrictStreetIndex(d, streets) for u, d in districts.items()}
    coords = {}
    with harmonized.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["latitude"] and r["longitude"]:
                coords[r["event_id"]] = (float(r["longitude"]), float(r["latitude"]))

    k_index = {f"{d}|{b}": i for i, (d, b) in enumerate(SUBPERIODS)}
    agg: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "events": 0.0,
            "by_family": defaultdict(float),
            "by_year": defaultdict(float),
            "by_subperiod": [0.0] * len(SUBPERIODS),
            "by_vehicle": defaultdict(float),
            "injured": 0.0,
            "deceased": 0.0,
            "via": defaultdict(float),
        }
    )
    assigned = unassigned = 0
    with (dataset / "events.csv").open(encoding="utf-8") as f:
        for e in csv.DictReader(f):
            ubigeo = e["district_ubigeo"]
            idx = index[ubigeo]
            targets: list[tuple[str, float, str]] = []
            if e["precision"] == "street" and e["matched_streets"]:
                targets = [(e["matched_streets"], 1.0, "street")]
            elif e["precision"] == "intersection" and e["matched_streets"]:
                targets = [(s, 0.5, "intersection") for s in e["matched_streets"].split("|")[:2]]
            elif e["precision"] == "point" and e["event_id"] in coords:
                x, y = TO_ANALYSIS.transform(*coords[e["event_id"]])
                p = Point(x, y)
                best = min(idx.streets.items(), key=lambda kv: kv[1].distance(p), default=None)
                if best and best[1].distance(p) <= SNAP_M:
                    targets = [(best[0], 1.0, "point")]
            if not targets:
                unassigned += 1
                continue
            assigned += 1
            k = k_index[f"{e['day_type']}|{e['band']}"]
            for core, w, via in targets:
                a = agg[(ubigeo, core)]
                a["events"] += w
                a["by_family"][e["family"]] += w
                a["by_year"][e["year"]] += w
                a["by_subperiod"][k] += w
                for vehicle, share in json.loads(e.get("vehicles") or "{}").items():
                    a["by_vehicle"][vehicle] += w * share
                a["injured"] += w * float(e["pedestrian_injured"] or 0)
                a["deceased"] += w * float(e["pedestrian_deceased"] or 0)
                a["via"][via] += w

    risk = cell_risk(results) if results else {}
    grid = json.loads((dataset / "grid.geojson").read_text(encoding="utf-8"))
    spec = grid["grid"]
    features = []
    for (ubigeo, core), a in agg.items():
        line = index[ubigeo].streets.get(core)
        if line is None:
            continue
        line = line.intersection(districts[ubigeo].geometry)
        length_km = line.length / 1000
        if length_km <= 0:
            continue
        mean_risk = length_weighted_risk(line, spec, risk) if risk else None
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "corridor_id": f"{ubigeo}:{core}",
                    "district_id": ubigeo,
                    "street": core.title(),
                    "length_km": round(length_km, 3),
                    "events": round(a["events"], 2),
                    "events_per_km": round(a["events"] / max(length_km, 0.1), 3),
                    "by_family": {k: round(v, 2) for k, v in a["by_family"].items()},
                    "by_year": {k: round(v, 2) for k, v in sorted(a["by_year"].items())},
                    "by_subperiod": [round(v, 2) for v in a["by_subperiod"]],
                    "by_vehicle": {k: round(v, 2) for k, v in sorted(a["by_vehicle"].items())},
                    "injured": round(a["injured"], 1),
                    "deceased": round(a["deceased"], 1),
                    "located_via": {k: round(v, 2) for k, v in a["via"].items()},
                    "mean_risk_index": mean_risk,
                },
                "geometry": mapping(to_public(line.simplify(5))),
            }
        )
    features.sort(key=lambda f: -f["properties"]["events_per_km"])
    total_events = sum(f["properties"]["events"] for f in features)
    total_km = sum(f["properties"]["length_km"] for f in features)
    cum_e = cum_km = 0.0
    curve = []
    for rank, f in enumerate(features, start=1):
        cum_e += f["properties"]["events"]
        cum_km += f["properties"]["length_km"]
        f["properties"]["rank"] = rank
        f["properties"]["cumulative_event_share"] = round(cum_e / total_events, 4)
        curve.append((round(cum_km / total_km, 4), round(cum_e / total_events, 4)))
    summary = {
        "corridors": len(features),
        "events_assigned": assigned,
        "events_not_on_corridor": unassigned,
        "total_length_km": round(total_km, 1),
        "snap_m": SNAP_M,
        "concentration": {
            f"{int(s * 100)}%_length": next(share for (length, share) in curve if length >= s)
            for s in (0.05, 0.10, 0.20)
        },
        "bands": [f"{a}-{b}" for a, b in TIME_BANDS],
    }
    return {"type": "FeatureCollection", "summary": summary, "features": features}


def cell_risk(results: Path) -> dict[str, float]:
    """Mean risk index per cell over the subperiods of the latest published year."""
    acc: dict[str, list[float]] = defaultdict(list)
    latest = None
    with results.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["representation_id"] == "grid-1km"]
    latest = max(r["period_id"][:4] for r in rows)
    for r in rows:
        if r["period_id"].startswith(latest) and r["risk_index"]:
            acc[r["unit_id"]].append(float(r["risk_index"]))
    return {u: sum(v) / len(v) for u, v in acc.items()}


def length_weighted_risk(line, spec: dict, risk: dict[str, float]) -> float | None:
    from shapely.geometry import box

    size = spec["cell_size_m"]
    minx, miny, maxx, maxy = line.bounds
    total = weighted = 0.0
    c0 = int((minx - spec["origin_x"]) // size) + 1
    c1 = int((maxx - spec["origin_x"]) // size) + 1
    r0 = int((spec["origin_y"] - maxy) // size) + 1
    r1 = int((spec["origin_y"] - miny) // size) + 1
    for row in range(r0, r1 + 1):
        for col in range(c0, c1 + 1):
            uid = f"F{row}-C{col}"
            if uid not in risk:
                continue
            left = spec["origin_x"] + (col - 1) * size
            top = spec["origin_y"] - (row - 1) * size
            seg = line.intersection(box(left, top - size, left + size, top)).length
            total += seg
            weighted += seg * risk[uid]
    return round(weighted / total, 2) if total else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--harmonized", type=Path, required=True)
    ap.add_argument("--boundary", type=Path, required=True)
    ap.add_argument("--results", type=Path)
    args = ap.parse_args()
    fc = build(args.dataset, args.harmonized, args.boundary, args.results)
    (args.dataset / "corridors.geojson").write_text(
        json.dumps(fc, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(fc["summary"], indent=2))


if __name__ == "__main__":
    main()
