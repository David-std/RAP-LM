"""OSM-derived exposure and road-environment variables per cell (dataset v1.1, D-10).

The integrated plan (v1.6, §1.2, citing Guo et al., 2024 and Hu et al., 2024)
relates pedestrian risk to exposure, points of interest, walkability, traffic
volume and road environment, beyond the count of events. No public measured
pedestrian or vehicle volume exists for the 43 districts, so these variables
are **proxies** taken from the OpenStreetMap extract (2026 snapshot):

* activity / exposure: commerce and services POIs, education POIs, health POIs;
* walkability / pedestrian infrastructure: footway length, crossings;
* traffic: arterial road length (motorway, trunk, primary and links) as a
  proxy of traffic volume, collector length (secondary, tertiary);
* control: traffic-signal nodes.

All counts and lengths are computed per 1 km cell in the analysis CRS.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from shapely import STRtree
from shapely.geometry import LineString

from pipelines.fusion.streets import LIMA_BBOX
from pipelines.spatial.grid import TO_ANALYSIS, Cell, GridSpec

COMMERCE = {
    "restaurant",
    "fast_food",
    "cafe",
    "bank",
    "pharmacy",
    "marketplace",
    "bar",
    "atm",
    "fuel",
    "food_court",
    "ice_cream",
    "bureau_de_change",
}
EDUCATION = {"school", "kindergarten", "university", "college", "language_school", "library"}
HEALTH = {"hospital", "clinic", "doctors", "dentist"}
FOOTWAY = {"footway", "pedestrian", "path", "steps", "living_street"}
ARTERIAL = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link"}
COLLECTOR = {"secondary", "secondary_link", "tertiary", "tertiary_link"}

OSM_VARIABLES = (
    "poi_commerce",
    "poi_education",
    "poi_health",
    "osm_crossings",
    "osm_signals",
    "footway_km",
    "arterial_km",
    "collector_km",
)


def build_osm_context(pbf: Path, spec: GridSpec, cells: list[Cell]) -> dict[str, np.ndarray]:
    import osmium

    lookup = {(c.row, c.col): i for i, c in enumerate(cells)}
    out = {name: np.zeros(len(cells), dtype=np.float64) for name in OSM_VARIABLES}
    minx, miny, maxx, maxy = LIMA_BBOX
    lines: dict[str, list[LineString]] = {"footway_km": [], "arterial_km": [], "collector_km": []}

    def add_point(name: str, lon: float, lat: float) -> None:
        if not (minx <= lon <= maxx and miny <= lat <= maxy):
            return
        idx = spec.cell_index(*TO_ANALYSIS.transform(lon, lat))
        if idx in lookup:
            out[name][lookup[idx]] += 1

    processor = (
        osmium.FileProcessor(str(pbf))
        .with_locations()
        .with_filter(osmium.filter.KeyFilter("amenity", "shop", "highway"))
    )
    for obj in processor:
        tags = obj.tags
        if obj.is_node():
            lon, lat = obj.location.lon, obj.location.lat
            amenity = tags.get("amenity")
            if "shop" in tags or amenity in COMMERCE:
                add_point("poi_commerce", lon, lat)
            if amenity in EDUCATION:
                add_point("poi_education", lon, lat)
            if amenity in HEALTH:
                add_point("poi_health", lon, lat)
            if tags.get("highway") == "crossing":
                add_point("osm_crossings", lon, lat)
            if tags.get("highway") == "traffic_signals":
                add_point("osm_signals", lon, lat)
        elif obj.is_way():
            hw = tags.get("highway")
            target = (
                "footway_km"
                if hw in FOOTWAY
                else "arterial_km"
                if hw in ARTERIAL
                else "collector_km"
                if hw in COLLECTOR
                else None
            )
            if target is None:
                continue
            try:
                coords = [(n.lon, n.lat) for n in obj.nodes]
            except osmium.InvalidLocationError:
                continue
            inside = any(minx <= x <= maxx and miny <= y <= maxy for x, y in coords)
            if len(coords) < 2 or not inside:
                continue
            xs, ys = TO_ANALYSIS.transform([c[0] for c in coords], [c[1] for c in coords])
            lines[target].append(LineString(list(zip(xs, ys, strict=True))))

    tree = STRtree([c.geometry for c in cells])
    for name, geoms in lines.items():
        for geom in geoms:
            for i in tree.query(geom):
                length = geom.intersection(cells[i].geometry).length
                if length > 0:
                    out[name][i] += length / 1000
    return out
