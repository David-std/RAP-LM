"""Regular analysis grid over the 43 districts of the province of Lima.

WBS 3.2.1 / HT-05 (RD-03, RD-04, RG-01). The grid is built in a projected CRS
(EPSG:32718, WGS 84 / UTM zone 18S) so that every cell is a true 1 km square.
Cells are clipped to the union of the 43 district polygons: no unit extends
outside the approved scope (Callao is not part of the INEI boundary layer).

Cell-district rule (documented, deterministic):
* ``district_fractions`` stores the share of the clipped cell area that falls in
  each district (sums to 1.0).
* ``district_ubigeo`` is the district holding the largest share (ties broken by
  the lowest UBIGEO). It is used only for display and filtering; event counts
  are assigned by point-in-polygon, never by this label.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from pyproj import Transformer
from shapely import Geometry
from shapely.geometry import box, mapping, shape
from shapely.ops import transform, unary_union
from shapely.prepared import prep

ANALYSIS_CRS = "EPSG:32718"
PUBLIC_CRS = "EPSG:4326"
TO_ANALYSIS = Transformer.from_crs(PUBLIC_CRS, ANALYSIS_CRS, always_xy=True)
TO_PUBLIC = Transformer.from_crs(ANALYSIS_CRS, PUBLIC_CRS, always_xy=True)
LIMA_PROVINCE_PREFIX = "1501"
EXPECTED_DISTRICTS = 43


@dataclass(frozen=True)
class District:
    ubigeo: str
    name: str
    geometry: Geometry  # analysis CRS


@dataclass(frozen=True)
class Cell:
    unit_id: str
    row: int
    col: int
    geometry: Geometry  # analysis CRS, clipped to the 43-district union
    district_ubigeo: str
    district_fractions: dict[str, float]

    @property
    def area_km2(self) -> float:
        return self.geometry.area / 1_000_000


@dataclass(frozen=True)
class GridSpec:
    cell_size_m: int
    origin_x: float  # west edge, analysis CRS
    origin_y: float  # north edge, analysis CRS
    rows: int
    cols: int
    crs: str = ANALYSIS_CRS

    def cell_index(self, x: float, y: float) -> tuple[int, int] | None:
        """Return 1-based (row, col) for a point in analysis CRS, or None."""
        col = math.floor((x - self.origin_x) / self.cell_size_m) + 1
        row = math.floor((self.origin_y - y) / self.cell_size_m) + 1
        if 1 <= row <= self.rows and 1 <= col <= self.cols:
            return row, col
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "cell_size_m": self.cell_size_m,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "rows": self.rows,
            "cols": self.cols,
            "crs": self.crs,
        }


def unit_id_for(row: int, col: int) -> str:
    return f"F{row}-C{col}"


def to_analysis(geometry: Geometry) -> Geometry:
    return transform(TO_ANALYSIS.transform, geometry)


def to_public(geometry: Geometry) -> Geometry:
    return transform(TO_PUBLIC.transform, geometry)


def load_districts(path: Path) -> list[District]:
    """Load the INEI 43-district boundary layer and validate its scope."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    districts: list[District] = []
    for feature in payload["features"]:
        props = feature["properties"]
        ubigeo = str(props["ubigeo"]).strip()
        if not ubigeo.startswith(LIMA_PROVINCE_PREFIX):
            raise ValueError(f"District {ubigeo} is outside the province of Lima")
        geometry = to_analysis(shape(feature["geometry"]).buffer(0))
        districts.append(District(ubigeo, str(props["nombdist"]).strip(), geometry))
    ubigeos = {d.ubigeo for d in districts}
    if len(ubigeos) != EXPECTED_DISTRICTS:
        raise ValueError(f"Expected {EXPECTED_DISTRICTS} districts, found {len(ubigeos)}")
    return sorted(districts, key=lambda d: d.ubigeo)


def build_grid(districts: list[District], cell_size_m: int = 1000) -> tuple[GridSpec, list[Cell]]:
    scope = unary_union([d.geometry for d in districts])
    minx, miny, maxx, maxy = scope.bounds
    origin_x = math.floor(minx / cell_size_m) * cell_size_m
    origin_y = math.ceil(maxy / cell_size_m) * cell_size_m
    cols = math.ceil((maxx - origin_x) / cell_size_m)
    rows = math.ceil((origin_y - miny) / cell_size_m)
    spec = GridSpec(cell_size_m, origin_x, origin_y, rows, cols)

    prepared = [(d, prep(d.geometry)) for d in districts]
    cells: list[Cell] = []
    for row in range(1, rows + 1):
        top = origin_y - (row - 1) * cell_size_m
        for col in range(1, cols + 1):
            left = origin_x + (col - 1) * cell_size_m
            square = box(left, top - cell_size_m, left + cell_size_m, top)
            shares: dict[str, float] = {}
            parts = []
            for district, fast in prepared:
                if not fast.intersects(square):
                    continue
                part = district.geometry.intersection(square)
                if part.area > 0:
                    shares[district.ubigeo] = part.area
                    parts.append(part)
            total = sum(shares.values())
            if total <= 0:
                continue
            fractions = {k: round(v / total, 6) for k, v in sorted(shares.items())}
            owner = sorted(shares.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            clipped = unary_union(parts)
            cells.append(Cell(unit_id_for(row, col), row, col, clipped, owner, fractions))
    return spec, cells


def _rounded(geometry: Geometry, digits: int = 6) -> dict[str, object]:
    def rnd(value):
        if isinstance(value, (list, tuple)):
            if value and isinstance(value[0], (int, float)):
                return [round(float(v), digits) for v in value]
            return [rnd(v) for v in value]
        return value

    m = mapping(geometry)
    return {"type": m["type"], "coordinates": rnd(m["coordinates"])}


def write_grid(path: Path, spec: GridSpec, cells: list[Cell]) -> None:
    features = [
        {
            "type": "Feature",
            "properties": {
                "unit_id": c.unit_id,
                "row": c.row,
                "col": c.col,
                "district_ubigeo": c.district_ubigeo,
                "district_fractions": c.district_fractions,
                "area_km2": round(c.area_km2, 6),
            },
            "geometry": _rounded(to_public(c.geometry)),
        }
        for c in cells
    ]
    payload = {"type": "FeatureCollection", "grid": spec.to_dict(), "features": features}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_districts(path: Path, districts: list[District]) -> None:
    features = [
        {
            "type": "Feature",
            "properties": {
                "unit_id": d.ubigeo,
                "ubigeo": d.ubigeo,
                "name": d.name,
                "area_km2": round(d.geometry.area / 1_000_000, 6),
            },
            "geometry": _rounded(to_public(d.geometry)),
        }
        for d in districts
    ]
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )
