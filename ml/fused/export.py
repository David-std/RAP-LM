"""Export publishable results of a trained run (HT-11 input; RM-04, M-04).

Usage::

    python -m ml.fused.export --dataset artifacts/datasets/fused-v1.0.0 \
        --run artifacts/runs/<run_id>

Writes ``results.csv`` (deterministic formatting, sorted) and ``periods.csv``
plus their SHA-256 in ``export_manifest.json``. The publisher loads these
files as they are; the reconciliation test compares them with the database
and the API.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np

from ml.fused.indicators import exposure_lambda, fatal_share
from ml.fused.tensors import load_dataset
from ml.fused.train import year_mask
from pipelines.fusion.events import SOURCE_FAMILIES, SUBPERIODS, TIME_BANDS, days_of_type

FAMILY_SOURCE = {"cenacom": "mininter_cenacom", "onsv": "onsv_georeferenced_crashes"}
DAY_LABEL = {"weekday": "weekday", "weekend": "weekend"}


def period_id(year: int, day_type: str, band: int) -> str:
    start, end = TIME_BANDS[band]
    return f"{year}-{'wd' if day_type == 'weekday' else 'we'}-{start:02d}{end:02d}"


def percentile_index(values: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Percentile rank (0-100) of each value in the frozen reference distribution."""
    ranks = np.searchsorted(reference, values, side="right")
    return np.clip(ranks / reference.size * 100.0, 0, 100)


def level_of(index: float, low_max: float, medium_max: float) -> str:
    if index < low_max:
        return "low"
    if index < medium_max:
        return "medium"
    return "high"


def fmt(x: float | None, digits: int = 6) -> str:
    if x is None or not np.isfinite(x):
        return ""
    return f"{x:.{digits}f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.run / "run_manifest.json").read_text(encoding="utf-8"))
    cfg = manifest["config"]
    th = cfg["thresholds"]
    t = load_dataset(args.dataset, cfg["years"])
    est = np.load(args.run / "estimates.npz")
    lam, value, ref_cells, rho = est["lam"], est["indicator"], est["reference"], est["rho"]
    area_floor = cfg["area_floor_km2"]

    split = cfg["split"]
    partition_of: dict[int, str] = {}
    for part in ("train", "validation", "test"):
        for ys in split[part].values():
            for y in ys:
                partition_of[y] = part
    published = [
        (ti, y) for ti, y in enumerate(t.years) if t.cover[:, ti].max() > 0 and y in partition_of
    ]

    # District representation: aggregate counts first (never labels), then density.
    d_area = np.einsum("dhw,hw->d", t.frac, t.area_km2)
    lam_d = np.einsum("tkhw,dhw->tkd", lam, t.frac)
    days = np.array(
        [[days_of_type(y, dt) for (dt, _b) in SUBPERIODS] for y in t.years], dtype=float
    )
    value_d = lam_d / days[:, :, None] * 365.0 / d_area[None, None]
    train_t = [ti for ti, y in published if partition_of[y] == "train"]
    ref_districts = np.sort(value_d[train_t].ravel())

    area = np.maximum(t.area_km2, area_floor)

    # Severity and exposure components (D-10): derived offline from the same lambda.
    train_years = [y for _ti, y in published if partition_of[y] == "train"]
    p_fatal = fatal_share(t, train_years)  # [H, W]
    sev_cell = value * p_fatal[None, None]  # expected fatal-outcome collisions / km2 / year
    sev_d = np.einsum("tkhw,dhw->tkd", lam * p_fatal[None, None], t.frac)
    sev_d = sev_d / days[:, :, None] * 365.0 / d_area[None, None]
    lam_exp = exposure_lambda(t, year_mask(t, split["train"]), cfg)
    ratio_cell = lam / np.maximum(lam_exp, 1e-9)
    ratio_d = lam_d / np.maximum(np.einsum("tkhw,dhw->tkd", lam_exp, t.frac), 1e-9)
    ref_sev_cell = np.sort(sev_cell[train_t][:, :, t.valid].ravel())
    ref_sev_d = np.sort(sev_d[train_t].ravel())
    ref_ratio_cell = np.sort(ratio_cell[train_t][:, :, t.valid].ravel())
    ref_ratio_d = np.sort(ratio_d[train_t].ravel())

    def breakdown(
        sev: np.ndarray | None,
        typ: np.ndarray | None,
        veh: np.ndarray | None = None,
        svc: np.ndarray | None = None,
    ) -> str:
        """Historical record by severity, subtype, vehicle type and transport service."""
        if sev is None or typ is None:
            return ""
        out = {
            "severity": [round(float(v), 2) for v in sev],
            "type": [round(float(v), 2) for v in typ],
        }
        if veh is not None and svc is not None:
            out["vehicle"] = [round(float(v), 2) for v in veh]
            out["service"] = [round(float(v), 2) for v in svc]
        return json.dumps(out, separators=(",", ":"))

    def hist_cell(s: int, ti: int) -> np.ndarray | None:
        prior = [p for p in range(ti) if t.cover[s, p].max() > 0]
        if not prior:
            return None
        rates = [
            t.y_cell[s, p] / (t.cover[s, p][:, None, None] * max(t.located[s, p], 1e-6))
            for p in prior
        ]
        latent = np.mean(rates, axis=0) / rho[s]
        return latent / days[ti][:, None, None] * 365.0 / area[None]

    def hist_district(s: int, ti: int) -> np.ndarray | None:
        prior = [p for p in range(ti) if t.cover[s, p].max() > 0]
        if not prior:
            return None
        rates = [t.events_total[s, p] / t.cover[s, p][:, None] for p in prior]
        latent = np.mean(rates, axis=0) / rho[s]
        return latent / days[ti][:, None] * 365.0 / d_area[None]

    rows: list[list[str]] = []
    period_rows: list[list[str]] = []
    unit_pos = list(zip(t.unit_ids, t.rows, t.cols, strict=True))
    for ti, year in published:
        observing = [s for s in range(len(SOURCE_FAMILIES)) if t.cover[s, ti].max() > 0]
        hc = [h for h in (hist_cell(s, ti) for s in observing) if h is not None]
        hd = [h for h in (hist_district(s, ti) for s in observing) if h is not None]
        h_cell = hc[0] if hc else None
        h_dist = hd[0] if hd else None
        idx_cells = percentile_index(value[ti], ref_cells)
        idx_dist = percentile_index(value_d[ti], ref_districts)
        sidx_cells = percentile_index(sev_cell[ti], ref_sev_cell)
        sidx_dist = percentile_index(sev_d[ti], ref_sev_d)
        ridx_cells = percentile_index(ratio_cell[ti], ref_ratio_cell)
        ridx_dist = percentile_index(ratio_d[ti], ref_ratio_d)
        for k, (day_type, band) in enumerate(SUBPERIODS):
            pid = period_id(year, day_type, band)
            start, end = TIME_BANDS[band]
            period_rows.append(
                [
                    pid,
                    str(year),
                    day_type,
                    str(band),
                    date(year, 1, 1).isoformat(),
                    date(year + 1, 1, 1).isoformat(),
                    str(start),
                    str(end),
                    partition_of[year],
                    "|".join(FAMILY_SOURCE[SOURCE_FAMILIES[s]] for s in observing),
                    f"{year}, {day_type}, {start}-{end} h",
                ]
            )
            obs_cell = t.y_cell[:, ti, k].sum(axis=0)
            for unit_id, r, c in unit_pos:
                v = float(value[ti, k, r, c])
                ix = float(idx_cells[k, r, c])
                rows.append(
                    [
                        "grid-1km",
                        unit_id,
                        pid,
                        "estimated",
                        fmt(v),
                        fmt(ix, 4),
                        level_of(ix, th["low_max"], th["medium_max"]),
                        fmt(None if h_cell is None else float(h_cell[k, r, c])),
                        fmt(float(obs_cell[r, c]), 4),
                        str(int(round(float(t.injured[ti, k, r, c])))),
                        str(int(round(float(t.deceased[ti, k, r, c])))),
                        fmt(float(sev_cell[ti, k, r, c])),
                        fmt(float(sidx_cells[k, r, c]), 4),
                        fmt(float(ratio_cell[ti, k, r, c]), 4),
                        fmt(float(ridx_cells[k, r, c]), 4),
                        breakdown(
                            None if t.severity_cell is None else t.severity_cell[ti, k, :, r, c],
                            None if t.type_cell is None else t.type_cell[ti, k, :, r, c],
                            None if t.vehicle_cell is None else t.vehicle_cell[ti, k, :, r, c],
                            None if t.service_cell is None else t.service_cell[ti, k, :, r, c],
                        ),
                    ]
                )
            obs_d = t.events_total[:, ti, k].sum(axis=0)
            for di, district_id in enumerate(t.district_ids):
                v = float(value_d[ti, k, di])
                ix = float(idx_dist[k, di])
                rows.append(
                    [
                        "district-43",
                        district_id,
                        pid,
                        "estimated",
                        fmt(v),
                        fmt(ix, 4),
                        level_of(ix, th["low_max"], th["medium_max"]),
                        fmt(None if h_dist is None else float(h_dist[k, di])),
                        fmt(float(obs_d[di]), 4),
                        str(int(t.injured_dist[ti, k, di])),
                        str(int(t.deceased_dist[ti, k, di])),
                        fmt(float(sev_d[ti, k, di])),
                        fmt(float(sidx_dist[k, di]), 4),
                        fmt(float(ratio_d[ti, k, di]), 4),
                        fmt(float(ridx_dist[k, di]), 4),
                        breakdown(
                            None if t.severity_dist is None else t.severity_dist[ti, k, :, di],
                            None if t.type_dist is None else t.type_dist[ti, k, :, di],
                            None if t.vehicle_dist is None else t.vehicle_dist[ti, k, :, di],
                            None if t.service_dist is None else t.service_dist[ti, k, :, di],
                        ),
                    ]
                )

    rows.sort(key=lambda r: (r[0], r[2], r[1]))
    header = [
        "representation_id",
        "unit_id",
        "period_id",
        "availability",
        "indicator_value",
        "risk_index",
        "risk_level",
        "historical_average",
        "observed_events",
        "observed_injured",
        "observed_deceased",
        "severity_value",
        "severity_index",
        "exposure_ratio",
        "exposure_index",
        "breakdown",
    ]
    out = args.run
    with (out / "results.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    with (out / "periods.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(
            [
                "period_id",
                "year",
                "day_type",
                "time_band",
                "start_date",
                "end_date",
                "start_hour",
                "end_hour",
                "partition",
                "observing_sources",
                "label",
            ]
        )
        w.writerows(period_rows)
    np.save(out / "reference_districts.npy", ref_districts)
    export = {
        "results_rows": len(rows),
        "periods": len(period_rows),
        "results_sha256": hashlib.sha256((out / "results.csv").read_bytes()).hexdigest(),
        "periods_sha256": hashlib.sha256((out / "periods.csv").read_bytes()).hexdigest(),
    }
    (out / "export_manifest.json").write_text(json.dumps(export, indent=2), encoding="utf-8")
    print(json.dumps(export, indent=2))


if __name__ == "__main__":
    main()
