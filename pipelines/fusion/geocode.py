"""Rule-based geocoding of police road references against named OSM streets.

WBS 3.2.1, HT-05 (RD-03). Unlocks gate G4 only under the explicit rules below;
no coordinate is ever invented:

* The search is restricted to the event's declared district (occurrence district
  when the source records it, otherwise the reporting police-station district,
  flagged as ``station_proxy``) buffered by ``DISTRICT_BUFFER_M``.
* ``intersection`` precision: two different named streets are matched in that
  district and their geometries meet (within ``INTERSECTION_TOLERANCE_M``). The
  location is the nearest meeting point, which must lie inside the district.
* ``street`` precision: exactly one street is matched. The location is the part
  of that street inside the district; the event is later spread along its
  length (line allocation), never collapsed to an arbitrary point.
* ``district`` precision: no reliable match. The event is kept as a district
  observation only.

Block numbers ("CUADRA 5") are not converted into positions: Lima block
numbering is not encoded in OSM and any conversion would fabricate precision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from shapely import Geometry
from shapely.geometry import Point
from shapely.ops import nearest_points
from shapely.prepared import prep

from pipelines.fusion.streets import (
    STREET_TYPES,
    Street,
    normalize_text,
    numbers_to_digits,
    street_core,
)
from pipelines.spatial.grid import District

DISTRICT_BUFFER_M = 150.0
INTERSECTION_TOLERANCE_M = 30.0
FUZZY_THRESHOLD = 0.88
MIN_CORE_LENGTH = 3

# Phrases that never name a street.
NOISE_PATTERNS = [
    r"\bSIN (REFERENCIA|REF|NOMBRE|NUMERO)\b",
    r"\bS ?N\b",
    r"\bNO (ESPEC|IDENTIF|PRECIS|REGISTR)[A-Z]*",
    r"\bCARRIL( DERECHO| IZQUIERDO)?\b",
    r"\b[A-Z]$",
    r"\b(SENTIDO )?(DE )?(NORTE|SUR|ESTE|OESTE) A (NORTE|SUR|ESTE|OESTE)\b",
    r"\bSENTIDO\b",
    r"\b(KM|KILOMETRO)S? ?[0-9 ]*\b",
    r"\bAA ?HH\b.*$",
    r"\bASENTAMIENTO HUMANO\b.*$",
    r"\bURB(ANIZACION)?\b.*$",
    r"\bMZ\b.*$",
    r"\bLOTE?\b.*$",
]
# Connectors that introduce a cross street.
CROSS_SPLIT = re.compile(
    r"\b(?:CON|CRUCE(?: CON)?|ESQ(?:UINA)?(?: CON)?|INTERSECCION(?: CON)?|Y)\b"
)
# Connectors after which the text is a landmark or block number, not a street.
LANDMARK_SPLIT = re.compile(
    r"\b(?:ALTURA|ALT|FRENTE|PARADERO|CUADRA|CDA|CDRA|CD|NRO|NUMERO|N|PUERTA|"
    r"EXTERIOR|INTERIOR|COSTADO|POR|EN EL|EN LA|CERCA|ANTES|DESPUES|ENTRE)\b"
)
GENERIC_CORES = {
    "PRINCIPAL",
    "CENTRAL",
    "FINAL",
    "NESP",
    "ATROPELLO",
    "AUXILIAR",
    "PISTA",
    "CARRIL",
    "DERECHO",
    "IZQUIERDO",
    "PANAMERICANA",
    "CARRETERA",
    "INTERIOR",
    "PUBLICA",
    "NUEVA",
}
MONTHS = (
    "ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SETIEMBRE|SEPTIEMBRE|OCTUBRE|"
    "NOVIEMBRE|DICIEMBRE"
)
# A street-type word in the middle of the text starts a new street name.
TYPE_SPLIT = re.compile(
    r"\s(?=(?:AV|AVENIDA|JR|JIRON|CALLE|CA|PASAJE|PJE|PSJE|PROL|PROLONGACION)\s)"
)


@dataclass(frozen=True)
class GeocodeResult:
    precision: str  # intersection | street | district
    geometry: Geometry | None  # analysis CRS; Point for intersection, lines for street
    matched: tuple[str, ...]
    candidates: tuple[str, ...]


def candidate_streets(description: str) -> list[str]:
    """Extract ordered street-name candidates from a police road reference."""
    text = normalize_text(description)
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, " ", text)
    text = numbers_to_digits(re.sub(r"\s+", " ", text).strip())
    chunks = [c for part in CROSS_SPLIT.split(text) for c in TYPE_SPLIT.split(" " + part)]
    candidates: list[str] = []
    for chunk in chunks:
        head = LANDMARK_SPLIT.split(chunk.strip())[0]
        # Keep dates used as street names ("15 DE ABRIL"); drop other loose numbers.
        head = re.sub(rf"\b[0-9]+\b(?! DE (?:{MONTHS})\b)", " ", head)
        core = street_core(head)
        tokens = [t for t in core.split() if t not in STREET_TYPES]
        # Police text repeats words ("CANETE CANETE"): drop consecutive duplicates.
        core = " ".join(t for i, t in enumerate(tokens) if i == 0 or t != tokens[i - 1])
        if len(core) >= MIN_CORE_LENGTH and core not in candidates:
            candidates.append(core)
    return candidates


class DistrictStreetIndex:
    """Named streets clipped to one district (plus a small buffer)."""

    def __init__(self, district: District, streets: list[Street]):
        self.district = district
        area = district.geometry.buffer(DISTRICT_BUFFER_M)
        fast = prep(area)
        self.inside = prep(district.geometry)
        self.streets: dict[str, Geometry] = {}
        for street in streets:
            if fast.intersects(street.geometry):
                clipped = street.geometry.intersection(area)
                if not clipped.is_empty and clipped.length > 0:
                    self.streets[street.core] = clipped
        self.cores = sorted(self.streets)
        self.core_tokens = [(c, set(c.split())) for c in self.cores]
        self._cache: dict[str, str | None] = {}

    def match(self, candidate: str) -> str | None:
        if candidate not in self._cache:
            self._cache[candidate] = self._match(candidate)
        return self._cache[candidate]

    def _match(self, candidate: str) -> str | None:
        if candidate in GENERIC_CORES or all(t in GENERIC_CORES for t in candidate.split()):
            return None
        if candidate in self.streets:
            return candidate
        cand_tokens = set(candidate.split())
        scored: list[tuple[float, str]] = []
        matcher = SequenceMatcher(None, "", candidate)
        for core, tokens in self.core_tokens:
            if cand_tokens and cand_tokens <= tokens and max(map(len, cand_tokens)) >= 5:
                # Police text often drops a first name ("WIESSE" for "FERNANDO WIESSE").
                scored.append((0.95 - 0.01 * (len(tokens) - len(cand_tokens)), core))
                continue
            matcher.set_seq1(core)
            if (
                matcher.real_quick_ratio() < FUZZY_THRESHOLD
                or matcher.quick_ratio() < FUZZY_THRESHOLD
            ):
                continue
            ratio = matcher.ratio()
            if ratio >= FUZZY_THRESHOLD:
                scored.append((ratio, core))
        if not scored:
            return None
        scored.sort(reverse=True)
        if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.02:
            return None  # ambiguous: refuse rather than guess
        return scored[0][1]

    def geocode(self, description: str) -> GeocodeResult:
        candidates = candidate_streets(description)
        matched: list[str] = []
        for candidate in candidates:
            core = self.match(candidate)
            if core and core not in matched:
                matched.append(core)
        if len(matched) >= 2:
            a, b = self.streets[matched[0]], self.streets[matched[1]]
            if a.distance(b) <= INTERSECTION_TOLERANCE_M:
                meet = a.intersection(b)
                if meet.is_empty:
                    p1, p2 = nearest_points(a, b)
                    point = Point((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)
                else:
                    point = meet.representative_point()
                if self.inside.contains(point):
                    return GeocodeResult(
                        "intersection", point, tuple(matched[:2]), tuple(candidates)
                    )
        if matched:
            line = self.streets[matched[0]].intersection(self.district.geometry)
            if not line.is_empty and line.length > 0:
                return GeocodeResult("street", line, (matched[0],), tuple(candidates))
        return GeocodeResult("district", None, tuple(matched), tuple(candidates))
