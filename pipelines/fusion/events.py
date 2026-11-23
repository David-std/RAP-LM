"""Fusion of pedestrian-collision events from heterogeneous sources.

WBS 3.2.1, HT-05/HT-06 (RD-03, RD-04, RD-05, RG-01). Target population: **every
pedestrian collision regardless of severity or subtype** (atropello, atropello
y fuga, choque y atropello, and any crash with a pedestrian victim). Severity is
kept only as part of the historical record shown to users; it never filters the
target.

Each source is a partial observation of the same phenomenon:

* ``cenacom``: MININTER/INEI police-station census 2011-2017 (all severities).
  2011-2014 records only carry the reporting station's district
  (``station_proxy``); 2015-2017 carry the occurrence district.
* ``onsv``: ONSV georeferenced crashes 2021-2024 with at least one fatal
  victim. They are a severity-truncated observation of the same population.

The model (``ml/``) estimates one latent intensity per cell and period and
links each source to it through a source-specific reporting factor and a
coverage offset. Incomplete years are handled with that offset, never by
filling missing months with zeros.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from shapely import Geometry
from shapely.geometry import Point
from shapely.prepared import prep

from pipelines.fusion.geocode import DistrictStreetIndex
from pipelines.spatial.grid import TO_ANALYSIS, Cell, District, GridSpec

DAY_TYPES = ("weekday", "weekend")
TIME_BANDS = ((0, 6), (6, 12), (12, 18), (18, 24))
SUBPERIODS = tuple((d, b) for d in DAY_TYPES for b in range(len(TIME_BANDS)))

# Source cohorts admitted into the fused target and their family.
SOURCE_FAMILY = {
    "cenacom_2012": "cenacom",
    "cenacom_2013": "cenacom",
    "cenacom_2014": "cenacom",
    "cenacom_2015": "cenacom",
    "cenacom_2016": "cenacom",
    "cenacom_2017": "cenacom",
    "onsv_fatal_2021_2025": "onsv",
}
SOURCE_FAMILIES = ("cenacom", "onsv")

# Observation windows per family and year: (first day, last day) inclusive.
# CENACOM edition 2017 reports January-June 2017 only; ONSV 2025 (January to
# early April) is excluded because the year is not closed.
COVERAGE = {
    "cenacom": {y: (date(y, 1, 1), date(y, 12, 31)) for y in range(2011, 2017)}
    | {2017: (date(2017, 1, 1), date(2017, 6, 30))},
    "onsv": {y: (date(y, 1, 1), date(y, 12, 31)) for y in range(2021, 2025)},
}
EXCLUDED_COHORTS = {
    "san_isidro_2026": "Single municipality, January-April 2026, no event time: cannot be "
    "assigned to a time band nor compared across the 43 districts.",
}


def coverage_fraction(family: str, year: int, day_type: str) -> float:
    """Share of the year's days of ``day_type`` observed by ``family`` (0..1)."""
    window = COVERAGE.get(family, {}).get(year)
    if window is None:
        return 0.0
    start, end = window
    observed = total = 0
    day = date(year, 1, 1)
    while day.year == year:
        if day_type_of(day) == day_type:
            total += 1
            if start <= day <= end:
                observed += 1
        day = date.fromordinal(day.toordinal() + 1)
    return observed / total if total else 0.0


def days_of_type(year: int, day_type: str) -> int:
    day = date(year, 1, 1)
    n = 0
    while day.year == year:
        n += day_type_of(day) == day_type
        day = date.fromordinal(day.toordinal() + 1)
    return n


def day_type_of(value: date) -> str:
    return "weekend" if value.weekday() >= 5 else "weekday"


def band_of(hhmm: str) -> int | None:
    try:
        hour = int(hhmm.split(":")[0])
    except (ValueError, AttributeError, IndexError):
        return None
    if not 0 <= hour <= 23:
        return None
    return hour // 6


def _int(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


@dataclass
class FusedEvent:
    event_id: str
    source_id: str
    family: str
    year: int
    day_type: str
    band: int
    district_ubigeo: str
    location_basis: str  # point | occurrence_district | station_proxy
    precision: str  # point | intersection | street | district
    geometry: Geometry | None
    matched_streets: tuple[str, ...] = ()
    injured: int | None = None
    deceased: int | None = None
    collision_type: str = ""
    severity: str = ""
    allocation: dict[str, float] = field(default_factory=dict)  # unit_id -> weight
    vehicles: dict[str, float] = field(default_factory=dict)  # vehicle class -> share (D-12)
    service: dict[str, float] = field(default_factory=dict)  # transport service -> share
    factors: list[str] = field(default_factory=list)  # recorded contributing factors


@dataclass
class FusionReport:
    read: Counter = field(default_factory=Counter)
    excluded: Counter = field(default_factory=Counter)
    precision: Counter = field(default_factory=Counter)

    def to_dict(self) -> dict[str, object]:
        return {
            "rows_read_by_source": dict(self.read),
            "excluded_by_reason": dict(self.excluded),
            "precision_by_source": {k: v for k, v in sorted(self.precision.items())},
            "excluded_cohorts": EXCLUDED_COHORTS,
        }


def read_events(
    harmonized_csv: Path,
    districts: list[District],
    indexes: dict[str, DistrictStreetIndex],
) -> tuple[list[FusedEvent], FusionReport]:
    """Read the harmonized v0.2.0 events and locate each one without invention."""
    by_ubigeo = {d.ubigeo: d for d in districts}
    inside = {d.ubigeo: prep(d.geometry) for d in districts}
    report = FusionReport()
    events: list[FusedEvent] = []
    with harmonized_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            source = row["source_id"]
            report.read[source] += 1
            family = SOURCE_FAMILY.get(source)
            if family is None:
                report.excluded[f"{source}:cohort_not_fused"] += 1
                continue
            try:
                occurred = date.fromisoformat(row["event_date"])
            except ValueError:
                report.excluded[f"{source}:invalid_date"] += 1
                continue
            if occurred.year not in COVERAGE[family]:
                report.excluded[f"{source}:year_outside_closed_coverage"] += 1
                continue
            start, end = COVERAGE[family][occurred.year]
            if not start <= occurred <= end:
                report.excluded[f"{source}:date_outside_observation_window"] += 1
                continue
            band = band_of(row["event_time"])
            if band is None:
                report.excluded[f"{source}:missing_time"] += 1
                continue

            if row["district_ubigeo"]:
                ubigeo, basis = row["district_ubigeo"], "occurrence_district"
            else:
                ubigeo, basis = row["reporting_police_ubigeo"], "station_proxy"
            if ubigeo not in by_ubigeo:
                report.excluded[f"{source}:district_outside_43"] += 1
                continue

            event = FusedEvent(
                event_id=row["event_id"],
                source_id=source,
                family=family,
                year=occurred.year,
                day_type=day_type_of(occurred),
                band=band,
                district_ubigeo=ubigeo,
                location_basis=basis,
                precision="district",
                geometry=None,
                injured=_int(row["pedestrian_injured_count"]),
                deceased=_int(row["pedestrian_deceased_count"]),
                collision_type=row["collision_type"],
                severity=row["incident_severity"] or "unknown",
            )
            lat, lon = row["latitude"], row["longitude"]
            if lat and lon and row["coordinate_status"] == "within_declared_district":
                x, y = TO_ANALYSIS.transform(float(lon), float(lat))
                point = Point(x, y)
                if inside[ubigeo].contains(point):
                    event.precision, event.geometry = "point", point
                    event.location_basis = "point"
            if event.precision == "district" and row["location_description"]:
                result = indexes[ubigeo].geocode(row["location_description"])
                event.precision = result.precision
                event.geometry = result.geometry
                event.matched_streets = result.matched
            report.precision[f"{family}:{basis}:{event.precision}"] += 1
            events.append(event)
    return events, report


def allocate(events: list[FusedEvent], spec: GridSpec, cells: list[Cell]) -> None:
    """Assign located events to cells: points to one cell, streets by length share."""
    by_index = {(c.row, c.col): c for c in cells}
    for event in events:
        if event.geometry is None:
            continue
        if event.precision in ("point", "intersection"):
            idx = spec.cell_index(event.geometry.x, event.geometry.y)
            cell = by_index.get(idx) if idx else None
            if cell is None:
                event.precision, event.geometry = "district", None
                continue
            event.allocation = {cell.unit_id: 1.0}
        elif event.precision == "street":
            weights: dict[str, float] = {}
            minx, miny, maxx, maxy = event.geometry.bounds
            first = spec.cell_index(minx, maxy) or (1, 1)
            last = spec.cell_index(maxx, miny) or (spec.rows, spec.cols)
            for row in range(first[0], last[0] + 1):
                for col in range(first[1], last[1] + 1):
                    cell = by_index.get((row, col))
                    if cell is None:
                        continue
                    length = event.geometry.intersection(cell.geometry).length
                    if length > 0:
                        weights[cell.unit_id] = length
            total = sum(weights.values())
            if total <= 0:
                event.precision, event.geometry = "district", None
                continue
            event.allocation = {k: v / total for k, v in weights.items()}
