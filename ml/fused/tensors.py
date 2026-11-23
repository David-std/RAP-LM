"""Tensor construction for the fused CNN-LSTM (WBS 3.2.1-3.2.3; HT-06..HT-08).

Shapes (documented contract, checked by tests):

* ``X``      [T, C, H, W]  inputs per year; channel list in ``Tensors.channels``.
* ``valid``  [H, W]        True where a grid cell exists (inside the 43 districts).
* ``y_cell`` [S, T, K, H, W] located events (fractional allocation) per family.
* ``y_dist`` [S, T, K, D]  district-precision events per family.
* ``cover``  [S, T, K]     observed share of the year's days of that day type.
* ``located``[S, T]        located share of each family-year (thinning offset).
* ``frac``   [D, H, W]     area share of each cell in each district.

Causality: inputs of year ``t`` contain static context plus observations of
year ``t-1`` only. The year being estimated never feeds its own input.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pipelines.fusion.events import SOURCE_FAMILIES, SUBPERIODS, coverage_fraction

# Severity and subtype classes of the historical record (dataset v1.1).
SEVERITY_CLASSES = ("fatal", "nonfatal", "material_only", "unknown")
TYPE_CLASSES = ("atropello", "atropello_fuga", "choque_y_atropello", "otro")
SEVERITY_MAP = {"fatal": 0, "fatal_incident": 0, "nonfatal": 1, "material_only": 2}
TYPE_MAP = {"atropello": 0, "atropello_fuga": 1, "choque_y_atropello": 2}

# v1.0 order; datasets declare their own order in dataset_manifest.json.
CONTEXT_ORDER = (
    "population",
    "transit_stops",
    "transit_route_km",
    "street_km",
    "traffic_lights",
    "pedestrian_crossings",
    "special_road_km",
)


@dataclass
class Tensors:
    years: list[int]
    unit_ids: list[str]  # valid cells in row-major order
    rows: np.ndarray  # 0-based row per unit
    cols: np.ndarray
    district_ids: list[str]
    X: np.ndarray
    channels: list[str]
    valid: np.ndarray
    y_cell: np.ndarray
    y_dist: np.ndarray
    cover: np.ndarray
    located: np.ndarray
    frac: np.ndarray
    area_km2: np.ndarray  # [H, W]
    injured: np.ndarray  # [T, K, H, W] observed pedestrian injured (located events)
    deceased: np.ndarray
    events_total: np.ndarray  # [S, T, K, D] all events (located + district) per district
    injured_dist: np.ndarray  # [T, K, D] pedestrians injured, all events of the district
    deceased_dist: np.ndarray
    context_order: tuple[str, ...] = CONTEXT_ORDER
    severity_cell: np.ndarray | None = None  # [T, K, 4, H, W] located events by severity class
    type_cell: np.ndarray | None = None  # [T, K, 4, H, W] located events by subtype
    severity_dist: np.ndarray | None = None  # [T, K, 4, D] all events by severity class
    type_dist: np.ndarray | None = None


def load_dataset(dataset_dir: Path, years: list[int]) -> Tensors:
    grid = json.loads((dataset_dir / "grid.geojson").read_text(encoding="utf-8"))
    spec = grid["grid"]
    H, W = spec["rows"], spec["cols"]
    features = grid["features"]
    unit_ids = [f["properties"]["unit_id"] for f in features]
    rows = np.array([f["properties"]["row"] - 1 for f in features])
    cols = np.array([f["properties"]["col"] - 1 for f in features])
    index = {u: (r, c) for u, r, c in zip(unit_ids, rows, cols, strict=True)}

    districts = json.loads((dataset_dir / "districts.geojson").read_text(encoding="utf-8"))
    district_ids = sorted(f["properties"]["ubigeo"] for f in districts["features"])
    d_index = {d: i for i, d in enumerate(district_ids)}
    D = len(district_ids)

    valid = np.zeros((H, W), dtype=bool)
    valid[rows, cols] = True
    frac = np.zeros((D, H, W), dtype=np.float32)
    area = np.zeros((H, W), dtype=np.float32)
    for f in features:
        p = f["properties"]
        r, c = p["row"] - 1, p["col"] - 1
        area[r, c] = p["area_km2"]
        for d, share in p["district_fractions"].items():
            frac[d_index[d], r, c] = share

    S, T, K = len(SOURCE_FAMILIES), len(years), len(SUBPERIODS)
    y_index = {y: i for i, y in enumerate(years)}
    s_index = {s: i for i, s in enumerate(SOURCE_FAMILIES)}
    k_index = {sp: i for i, sp in enumerate(SUBPERIODS)}
    y_cell = np.zeros((S, T, K, H, W), dtype=np.float32)
    y_dist = np.zeros((S, T, K, D), dtype=np.float32)
    events_total = np.zeros((S, T, K, D), dtype=np.float32)
    injured = np.zeros((T, K, H, W), dtype=np.float32)
    deceased = np.zeros((T, K, H, W), dtype=np.float32)
    injured_dist = np.zeros((T, K, D), dtype=np.float32)
    deceased_dist = np.zeros((T, K, D), dtype=np.float32)
    severity_cell = np.zeros((T, K, 4, H, W), dtype=np.float32)
    type_cell = np.zeros((T, K, 4, H, W), dtype=np.float32)
    severity_dist = np.zeros((T, K, 4, D), dtype=np.float32)
    type_dist = np.zeros((T, K, 4, D), dtype=np.float32)
    n_total = np.zeros((S, T), dtype=np.float64)
    n_located = np.zeros((S, T), dtype=np.float64)

    with (dataset_dir / "events.csv").open(encoding="utf-8", newline="") as handle:
        for e in csv.DictReader(handle):
            year = int(e["year"])
            if year not in y_index:
                continue
            s, t = s_index[e["family"]], y_index[year]
            k = k_index[(e["day_type"], int(e["band"]))]
            n_total[s, t] += 1
            di = d_index[e["district_ubigeo"]]
            events_total[s, t, k, di] += 1
            inj = float(e["pedestrian_injured"] or 0)
            dec = float(e["pedestrian_deceased"] or 0)
            injured_dist[t, k, di] += inj
            deceased_dist[t, k, di] += dec
            sev = SEVERITY_MAP.get(e.get("severity", ""), 3)
            typ = TYPE_MAP.get(e.get("collision_type", ""), 3)
            severity_dist[t, k, sev, di] += 1
            type_dist[t, k, typ, di] += 1
            allocation = json.loads(e["allocation"])
            if allocation:
                n_located[s, t] += 1
                for unit, w in allocation.items():
                    r, c = index[unit]
                    y_cell[s, t, k, r, c] += w
                    severity_cell[t, k, sev, r, c] += w
                    type_cell[t, k, typ, r, c] += w
                    injured[t, k, r, c] += w * inj
                    deceased[t, k, r, c] += w * dec
            else:
                y_dist[s, t, k, d_index[e["district_ubigeo"]]] += 1

    cover = np.zeros((S, T, K), dtype=np.float32)
    for s, fam in enumerate(SOURCE_FAMILIES):
        for t, year in enumerate(years):
            for k, (day_type, _band) in enumerate(SUBPERIODS):
                cover[s, t, k] = coverage_fraction(fam, year, day_type)
    located = np.where(n_total > 0, n_located / np.maximum(n_total, 1), 0).astype(np.float32)

    manifest = json.loads((dataset_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    context_order = tuple(v["variable_id"] for v in manifest["context_variables"])
    context = np.load(dataset_dir / "context.npz")
    ctx_units = list(context["unit_ids"])
    assert ctx_units == unit_ids, "context.npz is not aligned with grid.geojson"
    static = np.zeros((len(context_order), H, W), dtype=np.float32)
    for i, name in enumerate(context_order):
        static[i, rows, cols] = np.log1p(context[name])
    # Standardise over valid cells (context is time-invariant: no split leakage).
    for i in range(static.shape[0]):
        vals = static[i][valid]
        static[i][valid] = (vals - vals.mean()) / (vals.std() + 1e-6)

    channels = list(context_order) + ["valid_cell"]
    dyn_names = []
    for fam in SOURCE_FAMILIES:
        dyn_names += [
            f"{fam}_prev_cell_rate",
            f"{fam}_prev_district_density",
            f"{fam}_prev_observed",
        ]
    channels += dyn_names
    X = np.zeros((T, len(channels), H, W), dtype=np.float32)
    X[:, : len(context_order)] = static[None]
    X[:, len(context_order)] = valid
    base = len(context_order) + 1
    district_area = (frac * area[None]).sum(axis=(1, 2))  # km2 per district
    for t in range(1, T):
        for s in range(S):
            cov = cover[s, t - 1].mean()
            if cov <= 0:
                continue
            q = max(located[s, t - 1], 1e-6)
            cell_rate = y_cell[s, t - 1].sum(axis=0) / (cov * q)
            dist_density = events_total[s, t - 1].sum(axis=0) / cov / district_area
            spread = np.tensordot(dist_density, frac, axes=(0, 0))
            X[t, base + 3 * s] = np.log1p(cell_rate) * valid
            X[t, base + 3 * s + 1] = np.log1p(spread) * valid
            X[t, base + 3 * s + 2] = valid

    return Tensors(
        years=years,
        unit_ids=unit_ids,
        rows=rows,
        cols=cols,
        district_ids=district_ids,
        X=X,
        channels=channels,
        valid=valid,
        y_cell=y_cell,
        y_dist=y_dist,
        cover=cover,
        located=located,
        frac=frac,
        area_km2=area,
        injured=injured,
        deceased=deceased,
        events_total=events_total,
        injured_dist=injured_dist,
        deceased_dist=deceased_dist,
        context_order=context_order,
        severity_cell=severity_cell,
        type_cell=type_cell,
        severity_dist=severity_dist,
        type_dist=type_dist,
    )
