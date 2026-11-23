"""Urban-environment profile of every cell and district (decision D-12).

Answers the analyst question "how does this zone compare with the rest of
Lima?" (for example: few traffic signals per km of street). The indicators are
the same pre-existing conditions the network reads, expressed in readable
units, with the zone's percentile among all units of the same view. They are
observations of the environment; they do not prescribe interventions (RG-03).

Each profile is a list of ``[indicator_id, value, percentile]``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# indicator id -> (numerator variables, denominator: "street_km" | "area")
INDICATORS: dict[str, tuple[tuple[str, ...], str]] = {
    "signals_per_street_km": (("traffic_lights", "osm_signals"), "street_km"),
    "crossings_per_street_km": (("pedestrian_crossings", "osm_crossings"), "street_km"),
    "footway_per_street_km": (("footway_km",), "street_km"),
    "arterial_km_per_km2": (("arterial_km",), "area"),
    "commerce_per_km2": (("poi_commerce",), "area"),
    "schools_per_km2": (("poi_education",), "area"),
    "health_per_km2": (("poi_health",), "area"),
    "transit_stops_per_km2": (("transit_stops",), "area"),
    "population_per_km2": (("population",), "area"),
}
MIN_STREET_KM = 0.5  # below this a per-km ratio is not meaningful


def _percentile(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Percentile rank (0-100) among valid entries; NaN where not valid."""
    out = np.full(values.shape, np.nan)
    ref = np.sort(values[valid])
    if ref.size:
        out[valid] = np.searchsorted(ref, values[valid], side="right") / ref.size * 100
    return out


def _profiles(ids: list[str], totals: dict[str, np.ndarray], area: np.ndarray) -> dict[str, list]:
    street = totals["street_km"]
    columns = []
    for name, (num, den) in INDICATORS.items():
        n = sum(totals[v] for v in num)
        if den == "street_km":
            valid = street >= MIN_STREET_KM
            value = np.where(valid, n / np.maximum(street, 1e-9), np.nan)
        else:
            valid = area > 0
            value = np.where(valid, n / np.maximum(area, 1e-9), np.nan)
        columns.append((name, value, _percentile(value, valid)))
    out = {}
    for i, unit in enumerate(ids):
        out[unit] = [
            [name, round(float(v[i]), 3), round(float(p[i]), 1)]
            for name, v, p in columns
            if np.isfinite(v[i])
        ]
    return out


def build(dataset: Path, population_year: int = 2024) -> dict[str, dict[str, list]]:
    """{"cell": {unit_id: profile}, "district": {ubigeo: profile}}."""
    ctx = np.load(dataset / "context.npz")
    grid = json.loads((dataset / "grid.geojson").read_text(encoding="utf-8"))
    props = [f["properties"] for f in grid["features"]]
    ids = [p["unit_id"] for p in props]
    assert list(ctx["unit_ids"]) == ids, "context.npz is not aligned with grid.geojson"
    needed = {v for num, _ in INDICATORS.values() for v in num} | {"street_km"}
    cell = {v: ctx[v].astype(np.float64) for v in needed}
    if "population_by_year" in ctx.files:  # dataset v1.2+: population of the reference year
        years = [int(y) for y in ctx["population_years"]]
        cell["population"] = ctx["population_by_year"][years.index(population_year)].astype(float)
    area = np.array([p["area_km2"] for p in props])

    districts = sorted({d for p in props for d in p["district_fractions"]})
    frac = np.zeros((len(districts), len(ids)))
    for j, p in enumerate(props):
        for d, share in p["district_fractions"].items():
            frac[districts.index(d), j] = share
    dist = {v: frac @ x for v, x in cell.items()}
    return {
        "cell": _profiles(ids, cell, area),
        "district": _profiles(districts, dist, frac @ area),
    }
