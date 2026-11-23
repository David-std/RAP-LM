"""Named-street index from an OpenStreetMap extract (WBS 3.2.1, HT-05).

Only ways carrying both ``highway`` and ``name`` tags are kept. Geometries are
stored in the analysis CRS. Names are normalised with :func:`normalize_text`
and the street-type prefix is removed so that ``"Avenida Túpac Amaru"`` and the
police wording ``"AV TUPAC AMARU"`` share the core ``"TUPAC AMARU"``.

The extract is a 2026 snapshot: streets renamed or built after an event date
can create false matches or misses. This limitation is recorded in the
geocoding report and in provenance.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from shapely import Geometry
from shapely.geometry import LineString, mapping, shape
from shapely.ops import linemerge, unary_union

from pipelines.spatial.grid import to_analysis

STREET_TYPES = {
    "AVENIDA": "AV",
    "AV": "AV",
    "AVDA": "AV",
    "JIRON": "JR",
    "JR": "JR",
    "CALLE": "CA",
    "CA": "CA",
    "CAL": "CA",
    "PASAJE": "PJ",
    "PSJE": "PJ",
    "PJE": "PJ",
    "CARRETERA": "CARR",
    "CARR": "CARR",
    "PROLONGACION": "PROL",
    "PROL": "PROL",
    "MALECON": "MAL",
    "OVALO": "OVALO",
    "PLAZA": "PLAZA",
    "VIA": "VIA",
    "AUTOPISTA": "VIA",
    "ALAMEDA": "ALAMEDA",
}
STOP_WORDS = {"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y"}
NUMBER_WORDS = {
    "UNO": 1,
    "PRIMERO": 1,
    "DOS": 2,
    "TRES": 3,
    "CUATRO": 4,
    "CINCO": 5,
    "SEIS": 6,
    "SIETE": 7,
    "OCHO": 8,
    "NUEVE": 9,
    "DIEZ": 10,
    "ONCE": 11,
    "DOCE": 12,
    "TRECE": 13,
    "CATORCE": 14,
    "QUINCE": 15,
    "DIECISEIS": 16,
    "DIECISIETE": 17,
    "DIECIOCHO": 18,
    "DIECINUEVE": 19,
    "VEINTE": 20,
    "VEINTIUNO": 21,
    "VEINTIDOS": 22,
    "VEINTITRES": 23,
    "VEINTICUATRO": 24,
    "VEINTICINCO": 25,
    "VEINTISEIS": 26,
    "VEINTISIETE": 27,
    "VEINTIOCHO": 28,
    "VEINTINUEVE": 29,
    "TREINTA": 30,
}


def numbers_to_digits(text: str) -> str:
    return " ".join(str(NUMBER_WORDS[t]) if t in NUMBER_WORDS else t for t in text.split())


LIMA_BBOX = (-77.25, -12.55, -76.6, -11.55)  # lon/lat, generous envelope of the 43 districts


def normalize_text(value: str) -> str:
    """Uppercase ASCII, replacement characters dropped, single spaces."""
    value = (value or "").replace("�", "N")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.upper()
    value = re.sub(r"[^A-Z0-9 ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def street_core(name: str) -> str:
    """Normalised street name without its type prefix and stop words."""
    tokens = numbers_to_digits(normalize_text(name)).split()
    while tokens and tokens[0] in STREET_TYPES:
        tokens = tokens[1:]
    core = [t for t in tokens if t not in STOP_WORDS]
    return " ".join(core)


@dataclass(frozen=True)
class Street:
    core: str
    names: tuple[str, ...]
    geometry: Geometry  # merged lines, analysis CRS


def extract_streets(pbf_path: Path) -> list[Street]:
    """Read named highways inside the Lima envelope from an OSM PBF file."""
    import osmium  # local import: only the batch pipeline needs it

    lines_by_core: dict[str, list[LineString]] = defaultdict(list)
    names_by_core: dict[str, set[str]] = defaultdict(set)
    minx, miny, maxx, maxy = LIMA_BBOX

    processor = (
        osmium.FileProcessor(str(pbf_path))
        .with_locations()
        .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
        .with_filter(osmium.filter.KeyFilter("highway"))
    )
    for way in processor:
        name = way.tags.get("name")
        if not name:
            continue
        try:
            coords = [(n.lon, n.lat) for n in way.nodes]
        except osmium.InvalidLocationError:
            continue
        if len(coords) < 2:
            continue
        if not any(minx <= x <= maxx and miny <= y <= maxy for x, y in coords):
            continue
        core = street_core(name)
        if len(core) < 3:
            continue
        lines_by_core[core].append(to_analysis(LineString(coords)))
        names_by_core[core].add(name)

    streets = []
    for core, lines in sorted(lines_by_core.items()):
        union = unary_union(lines)
        merged = linemerge(union) if union.geom_type == "MultiLineString" else union
        streets.append(Street(core, tuple(sorted(names_by_core[core])), merged))
    return streets


def write_streets(path: Path, streets: list[Street]) -> None:
    payload = [
        {"core": s.core, "names": list(s.names), "geometry": mapping(s.geometry)} for s in streets
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def read_streets(path: Path) -> list[Street]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Street(p["core"], tuple(p["names"]), shape(p["geometry"])) for p in payload]
