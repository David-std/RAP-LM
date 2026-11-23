"""Vehicle type, transport service and recorded contributing factors of each event (D-12).

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

Contributing factors (dataset v1.3) are the causes the police record after the
event: CENACOM AT109_k (12, 15, 18 or 19 codes depending on the edition) and the
ONSV specific cause. An event may carry several factors, so factor counts are
multi-label. They describe the record and are never network inputs: they only
exist once the collision has happened, so using them would leak the outcome.
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
FACTOR_CLASSES = (
    "velocidad",
    "conductor_alcohol",
    "conductor_conducta",
    "peaton_conducta",
    "peaton_alcohol",
    "senalizacion",
    "iluminacion",
    "via_mal_estado",
    "vehiculo",
    "clima",
    "otro",
    "sin_causa",
)
_V, _CA, _CC = "velocidad", "conductor_alcohol", "conductor_conducta"
_PC, _PA, _S = "peaton_conducta", "peaton_alcohol", "senalizacion"
_I, _VM, _VE = "iluminacion", "via_mal_estado", "vehiculo"
_CL, _O, _SC = "clima", "otro", "sin_causa"
_BASE14 = [_V, _CC, _I, _VE, _CA, _CC, _VE, _VM, _PC, _PA, _CL, _S, _CC, _CC]
CENACOM_FACTOR = {
    # 2012: 3 falta de luces, 9 desacato del peatón, 12 otro; no señalización code.
    12: dict(enumerate([_V, _CC, _I, _VE, _CA, _CC, _VE, _VM, _PC, _PA, _CL, _O], 1)),
    # 2013-2015: adds señalización defectuosa, cansancio, celular; 15 otro.
    15: dict(enumerate([*_BASE14, _O], 1)),
    # 2016: adds impericia, deslizamiento; 17 otro, 18 no identifica.
    18: dict(enumerate([*_BASE14, _CC, _CL, _O, _SC], 1)),
    # 2017: adds desobediencia a la autoridad; 18 no identifica, 19 otro.
    19: dict(enumerate([*_BASE14, _CC, _CL, _CC, _SC, _O], 1)),
}
ONSV_FACTOR = {
    "EXCESO DE VELOCIDAD": _V,
    "CONDUCIR EN ESTADO DE EBRIEDAD Y/O DROGADICCION": _CA,
    "CRUCE INDEBIDO POR LA CALZADA": _PC,
    "OTRO (IMPRUDENCIA DEL PEATON)": _PC,
    "SENALIZACION DEFECTUOSA": _S,
    "FACTOR AMBIENTAL": _CL,
    "NO ENCENDER LAS LUCES": _VE,
    "CONDUCIR CON FALLAS DE FRENOS": _VE,
    "CONDUCIR CON FALLAS ELECTRICAS": _VE,
}

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


def _cenacom(raw: Path) -> dict[tuple[str, int], tuple[list[str], list[str], list[str]]]:
    """(source_id, 1-based record) -> (vehicle classes, service classes, factors)."""
    out: dict[tuple[str, int], tuple[list[str], list[str], list[str]]] = {}
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
                    n_fac = sum(1 for f in fields if f.startswith("AT109_") and f[6:].isdigit())
                    factor_codes = CENACOM_FACTOR[n_fac]
                    for i, r in enumerate(rows, start=1):
                        veh = [c for k, c in codes.items() if _flagged(r.get(f"AT106_{k}", ""))]
                        svc = [
                            c
                            for k, c in CENACOM_SERVICE.items()
                            if _flagged(r.get(f"AT107_{k}", ""))
                        ]
                        fac = sorted(
                            {
                                c
                                for k, c in factor_codes.items()
                                if _flagged(r.get(f"AT109_{k}", ""))
                            }
                        )
                        out[(f"cenacom_{year_dir.name}", i)] = (veh, svc, fac)
    return out


def _onsv_factor(principal: str, specific: str) -> list[str]:
    """Map the ONSV principal and specific cause to the common factor classes."""
    if specific in ONSV_FACTOR:
        return [ONSV_FACTOR[specific]]
    if specific == "ESTADO DE EBRIEDAD Y/O DROGADICCION":
        return [_PA if "PEATON" in principal else _CA]
    if "INVESTIGACION" in principal or not principal or principal == "NAN":
        return [_SC]
    if "INFRAESTRUCTURA" in principal:
        return [_VM]
    if "PEATON" in principal:
        return [_PC]
    if "CONDUCTOR" in principal:
        return [_CC]
    return [_O]


def _onsv(raw: Path) -> dict[tuple[str, str, str], list[tuple]]:
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
        fac = _onsv_factor(_norm(c["CAUSA FACTOR PRINCIPAL"]), _norm(c["CAUSA ESPECIFICA"]))
        out[key].append((_norm(c["CLASE SINIESTRO"]), veh, svc, fac))
    return out


def vehicle_profiles(raw: Path, harmonized_csv: Path) -> tuple[dict[str, tuple], dict]:
    """event_id -> (vehicle shares, service shares, factors), plus a linkage report."""
    cen = _cenacom(raw)
    onsv = _onsv(raw)
    profiles: dict[str, tuple] = {}
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
                hit = (cands[0][1], cands[0][2], cands[0][3]) if cands else None
                family = "onsv"
            else:
                continue
            report[f"{family}:linked" if hit else f"{family}:unlinked"] += 1
            veh, svc, fac = hit if hit else ([], [], [])
            report[f"{family}:vehicle_identified"] += bool(veh) and veh != [
                "no_identificado"
            ] * len(veh)
            report[f"{family}:factor_recorded"] += bool(fac) and fac != [_SC]
            profiles[row["event_id"]] = (_split(veh), _split(svc), fac or [_SC])
    return profiles, dict(sorted(report.items()))
