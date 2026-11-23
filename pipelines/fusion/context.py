"""Per-cell context variables (exposure and urban context proxies).

WBS 3.2.1, HT-06 (RD-05). Conceptual groups follow the report: *exposure*
(resident population, transit stops, transit routes) and *context* (named
street length, signalised intersections, pedestrian crossings, special road
types). All are **proxies**: none measures pedestrians x time, so no rate per
pedestrian is derived from them.

Temporal limitation: MINAM layers are 2021 snapshots, WorldPop is 2020 and the
OSM extract is 2026. They are used as time-invariant context for every period
and this is declared in provenance (dimension not incorporated: historical
infrastructure versions).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from shapely.geometry import shape

from pipelines.fusion.osm_context import build_osm_context
from pipelines.fusion.streets import Street
from pipelines.spatial.grid import TO_ANALYSIS, Cell, GridSpec, to_analysis


@dataclass(frozen=True)
class ContextVariable:
    variable_id: str
    label: str
    group: str  # exposure | context
    unit: str
    source_id: str
    reference_year: str


CONTEXT_VARIABLES = (
    ContextVariable(
        "population", "Resident population", "exposure", "persons", "worldpop_2020", "2020"
    ),
    ContextVariable(
        "transit_stops",
        "Public transport stops",
        "exposure",
        "count",
        "minam_transit_stops",
        "2021",
    ),
    ContextVariable(
        "transit_route_km",
        "Public transport route length",
        "exposure",
        "km",
        "minam_public_transport_routes",
        "2021",
    ),
    ContextVariable(
        "street_km", "Named street length", "context", "km", "osm_lima_extract", "2026"
    ),
    ContextVariable(
        "traffic_lights",
        "Signalised intersections",
        "context",
        "count",
        "minam_traffic_lights",
        "2021",
    ),
    ContextVariable(
        "pedestrian_crossings",
        "Pedestrian crossings and bridges",
        "context",
        "count",
        "minam_pedestrian_crossings",
        "2021",
    ),
    ContextVariable(
        "special_road_km",
        "Special road types (freight, express)",
        "context",
        "km",
        "minam_road_types",
        "2021",
    ),
    # Dataset v1.1 (D-10): OSM 2026 proxies of activity, walkability and traffic.
    ContextVariable(
        "poi_commerce",
        "Commerce and services POIs",
        "exposure",
        "count",
        "osm_lima_extract",
        "2026",
    ),
    ContextVariable(
        "poi_education", "Education POIs", "exposure", "count", "osm_lima_extract", "2026"
    ),
    ContextVariable("poi_health", "Health POIs", "exposure", "count", "osm_lima_extract", "2026"),
    ContextVariable(
        "osm_crossings",
        "Mapped pedestrian crossings",
        "context",
        "count",
        "osm_lima_extract",
        "2026",
    ),
    ContextVariable(
        "osm_signals", "Mapped traffic signals", "context", "count", "osm_lima_extract", "2026"
    ),
    ContextVariable(
        "footway_km",
        "Footway and pedestrian street length",
        "context",
        "km",
        "osm_lima_extract",
        "2026",
    ),
    ContextVariable(
        "arterial_km",
        "Arterial road length (traffic volume proxy)",
        "context",
        "km",
        "osm_lima_extract",
        "2026",
    ),
    ContextVariable(
        "collector_km", "Collector road length", "context", "km", "osm_lima_extract", "2026"
    ),
)


def _features(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def _point_counts(path: Path, spec: GridSpec, lookup: dict[tuple[int, int], int]) -> np.ndarray:
    out = np.zeros(len(lookup), dtype=np.float64)
    for feature in _features(path):
        coords = feature["geometry"]["coordinates"]
        x, y = TO_ANALYSIS.transform(coords[0], coords[1])
        idx = spec.cell_index(x, y)
        if idx in lookup:
            out[lookup[idx]] += 1
    return out


def _line_km(geoms, cells: list[Cell]) -> np.ndarray:
    from shapely import STRtree

    out = np.zeros(len(cells), dtype=np.float64)
    tree = STRtree([c.geometry for c in cells])
    for geom in geoms:
        for i in tree.query(geom):
            length = geom.intersection(cells[i].geometry).length
            if length > 0:
                out[i] += length / 1000
    return out


def _worldpop(path: Path, spec: GridSpec, lookup: dict[tuple[int, int], int]) -> np.ndarray:
    import rasterio
    from rasterio.windows import from_bounds

    out = np.zeros(len(lookup), dtype=np.float64)
    with rasterio.open(path) as src:
        window = from_bounds(-77.25, -12.55, -76.6, -11.55, src.transform)
        band = src.read(1, window=window, masked=True)
        transform = src.window_transform(window)
        rows, cols = np.nonzero(~np.ma.getmaskarray(band))
        values = band.data[rows, cols].astype(np.float64)
        xs, ys = rasterio.transform.xy(transform, rows, cols)
        ux, uy = TO_ANALYSIS.transform(np.asarray(xs), np.asarray(ys))
        for x, y, v in zip(ux, uy, values, strict=True):
            if v <= 0:
                continue
            idx = spec.cell_index(x, y)
            if idx in lookup:
                out[lookup[idx]] += v
    return out


def build_context(
    raw_root: Path, spec: GridSpec, cells: list[Cell], streets: list[Street]
) -> dict[str, np.ndarray]:
    """Return one array per variable, aligned with ``cells`` order."""
    lookup = {(c.row, c.col): i for i, c in enumerate(cells)}
    minam = raw_root / "mobility" / "minam"

    def lines(name: str):
        return [
            to_analysis(shape(f["geometry"])) for f in _features(minam / name / f"{name}.geojson")
        ]

    context = {
        "population": _worldpop(
            raw_root
            / "population/worldpop/2020/peru_worldpop_population_2020_constrained_100m.tif",
            spec,
            lookup,
        ),
        "transit_stops": _point_counts(minam / "transit_stops/transit_stops.geojson", spec, lookup),
        "transit_route_km": _line_km(lines("public_transport_routes"), cells),
        "street_km": _line_km([s.geometry for s in streets], cells),
        "traffic_lights": _point_counts(
            minam / "traffic_lights/traffic_lights.geojson", spec, lookup
        ),
        "pedestrian_crossings": _point_counts(
            minam / "pedestrian_crossings/pedestrian_crossings.geojson", spec, lookup
        ),
        "special_road_km": _line_km(lines("road_types"), cells),
    }
    context.update(build_osm_context(raw_root / "geography/roads/osm/Lima.osm.pbf", spec, cells))
    return context
