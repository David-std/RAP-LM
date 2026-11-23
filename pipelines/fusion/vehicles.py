"""Vehicle type and transport service of each fused event (dataset v1.2, D-12).

Neither attribute is in the harmonized table, so both are read back from the
raw sources and linked to the harmonized events:

* CENACOM (2011-2017): chapter 100 of the INEI microdata (dBase inside ZIP).
  ``source_row`` is the 1-based ordinal of the record (verified: the event date
  matches the record date in 98-100 % of the events of every edition). Fields
  AT106_1..AT106_18 flag each vehicle type involved and AT107_1..3 the service
  (public, private, not identified).
* ONSV (2021-2024): the fatal-crash register linked by date, time and district
  (crash class ``ATROPELLO`` / ``ATROPELLO FUGA`` breaks the few ties), then the
  vehicle register by crash code (``VEHÍCULO``, ``MODALIDAD DE TRANSPORTE``).

An event with several vehicles splits its unit weight equally among their
classes, so class totals add up to the event count. Events that cannot be
linked keep the class ``no_identificado`` rather than a guessed value.
"""

from __future__ import annotations

import csv
import glob
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from pipelines.fusion.dbf import read_dbf_bytes

VEHICLE_CLASSES = (
    "auto",
    "camioneta",
    "combi_minibus",
    "bus",
    "carga",
    "moto",
    "mototaxi",
    "bicicleta",
    "no_identificado",
)
SERVICE_CLASSES = ("publico", "particular", "carga", "no_identificado")

# CENACOM AT106_k -> class. The questionnaire changed between editions, so the
# code list depends on how many AT106 fields the edition has (read from each
# edition's chapter 100 dictionary and checked against the flag counts).
_A, _C, _K, _B, _G = "auto", "camioneta", "combi_minibus", "bus", "carga"
_M, _T, _Y, _N = "moto", "mototaxi", "bicicleta", "no_identificado"
CENACOM_VEHICLE = {
    # 2012: single ómnibus code; 12 moto lineal, 13 motocar, 14 triciclo, 15 bicicleta.
    17: dict(enumerate([_A, _A, _C, _K, _C, _B, _G, _G, _G, _N, _N, _M, _T, _Y, _Y, _N, _N], 1)),
    # 2016-2017: urban and interprovincial ómnibus; 13 moto lineal ... 16 bicicleta.
    18: dict(
        enumerate([_A, _A, _C, _K, _C, _B, _B, _G, _G, _G, _N, _N, _M, _T, _Y, _Y, _N, _N], 1)
    ),
    # 2013-2015: tracto camión and trayler split; 14 moto lineal ... 17 bicicleta.
    19: dict(
        enumerate([_A, _A, _C, _K, _C, _B, _B, _G, _G, _G, _G, _N, _N, _M, _T, _Y, _Y, _N, _N], 1)
    ),
}
CENACOM_SERVICE = {1: "publico", 2: "particular", 3: "no_identificado"}

ONSV_VEHICLE = {
    "AUTOMOVIL": "auto",
    "STATION WAGON": "auto",
    "CAMIONETA PICK UP": "camioneta",
    "CAMIONETA PANEL": "camioneta",
    "CAMIONETA RURAL": "combi_minibus",
    "MINIBUS": "combi_minibus",
    "OMNIBUS": "bus",
    "CAMION": "carga",
    "REMOLCADOR": "carga",
    "REMOLCADOR-SEMIREMOLQUE": "carga",
    "SEMIREMOLQUE": "carga",
    "REMOLQUE": "carga",
    "MOTOCICLETA": "moto",
    "MOTOCICLETA ELECTRICA": "moto",
    "BICIMOTO": "moto",
    "SCOOTER": "moto",
    "TRIMOTO PASAJERO": "mototaxi",
    "TRIMOTO CARGA": "mototaxi",
    "TRICICLO MOTORIZADO": "mototaxi",
    "BICICLETA": "bicicleta",
    "TRICICLO NO MOTORIZADO": "bicicleta",
}
ONSV_SERVICE = {
    "PARTICULAR": "particular",
    "CARGA": "carga",
    "MATERIALES PELIGROSOS": "carga",
    "PUBLICO URBANO": "publico",
    "SERVICIO ESPECIAL DE PASAJEROS": "publico",
    "REGULAR(INTERPROVINCIAL)": "publico",
    "TAXI": "publico",
    "TURISTICO": "publico",
    "TRABAJADORES": "publico",
    "AUTO COLECTIVO": "publico",
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return " ".join(text.upper().split())


def _flagged(value: str) -> bool:
    return value not in ("", "0") and not value.startswith("*")


def _split(classes: list[str]) -> dict[str, float]:
    """Equal shares per class occurrence; an empty list becomes ``no_identificado``."""
    if not classes:
        return {"no_identificado": 1.0}
    counts = Counter(classes)
    return {k: round(v / len(classes), 6) for k, v in counts.items()}


def _cenacom(raw: Path) -> dict[tuple[str, int], tuple[list[str], list[str]]]:
    """(source_id, 1-based record) -> (vehicle classes, service classes)."""
    out: dict[tuple[str, int], tuple[list[str], list[str]]] = {}
    for year_dir in sorted((raw / "accidents" / "cenacom").glob("20*")):
        for archive in sorted(glob.glob(str(year_dir / "microdata" / "*.zip"))):
            with zipfile.ZipFile(archive) as z:
                for name in z.namelist():
                    if not name.lower().endswith(".dbf"):
                        continue
                    fields, rows = read_dbf_bytes(z.read(name))
                    if "AT105" not in fields:
                        continue
                    n_codes = sum(1 for f in fields if f.startswith("AT106_") and f[6:].isdigit())
                    codes = CENACOM_VEHICLE[n_codes]
                    for i, r in enumerate(rows, start=1):
                        veh = [c for k, c in codes.items() if _flagged(r.get(f"AT106_{k}", ""))]
                        svc = [
                            c
                            for k, c in CENACOM_SERVICE.items()
                            if _flagged(r.get(f"AT107_{k}", ""))
                        ]
                        out[(f"cenacom_{year_dir.name}", i)] = (veh, svc)
    return out


def _onsv(raw: Path) -> dict[tuple[str, str, str], list[tuple[str, list[str], list[str]]]]:
    """(date, HH:MM, district) -> [(crash class, vehicle classes, service classes)]."""
    import pandas as pd

    base = raw / "accidents" / "onsv"
    crashes = pd.read_excel(base / "onsv_fatal_crashes_2021_2025.xlsx", header=4, dtype=str)
    vehicles = pd.read_excel(base / "onsv_vehicles_2021_2025.xlsx", header=4, dtype=str)
    crashes.columns = [_norm(c) for c in crashes.columns]
    vehicles.columns = [_norm(c) for c in vehicles.columns]
    by_code: dict[str, tuple[list[str], list[str]]] = defaultdict(lambda: ([], []))
    for _, v in vehicles.iterrows():
        veh, svc = by_code[v["CODIGO SINIESTRO"]]
        veh.append(ONSV_VEHICLE.get(_norm(v["VEHICULO"]), "no_identificado"))
        svc.append(ONSV_SERVICE.get(_norm(v["MODALIDAD DE TRANSPORTE"]), "no_identificado"))
    out: dict[tuple[str, str, str], list] = defaultdict(list)
    dates = pd.to_datetime(crashes["FECHA SINIESTRO"], dayfirst=True, errors="coerce")
    for (_, c), d in zip(crashes.iterrows(), dates, strict=True):
        if pd.isna(d):
            continue
        key = (d.strftime("%Y-%m-%d"), str(c["HORA SINIESTRO"])[:5], _norm(c["DISTRITO"]))
        veh, svc = by_code.get(c["CODIGO SINIESTRO"], ([], []))
        out[key].append((_norm(c["CLASE SINIESTRO"]), veh, svc))
    return out


def vehicle_profiles(raw: Path, harmonized_csv: Path) -> tuple[dict[str, tuple[dict, dict]], dict]:
    """event_id -> (vehicle shares, service shares), plus a linkage report."""
    cen = _cenacom(raw)
    onsv = _onsv(raw)
    profiles: dict[str, tuple[dict, dict]] = {}
    report: Counter = Counter()
    with harmonized_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            source = row["source_id"]
            if source.startswith("cenacom"):
                hit = cen.get((source, int(row["source_row"])))
                family = "cenacom"
            elif source.startswith("onsv"):
                key = (
                    row["event_date"],
                    (row["event_time"] or "")[:5],
                    _norm(row["district_name"]),
                )
                cands = onsv.get(key, [])
                if len(cands) > 1:
                    cands = [c for c in cands if c[0].startswith("ATROPELLO")] or cands
                hit = (cands[0][1], cands[0][2]) if cands else None
                family = "onsv"
            else:
                continue
            report[f"{family}:linked" if hit else f"{family}:unlinked"] += 1
            veh, svc = hit if hit else ([], [])
            report[f"{family}:vehicle_identified"] += bool(veh) and veh != [
                "no_identificado"
            ] * len(veh)
            profiles[row["event_id"]] = (_split(veh), _split(svc))
    return profiles, dict(sorted(report.items()))
