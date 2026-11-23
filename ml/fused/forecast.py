"""One-step-ahead forecast with the published network (RM-04, D-11).

Usage::

    python -m ml.fused.forecast --dataset artifacts/datasets/fused-v1.1.0 \
        --run artifacts/runs/<run_id> [--horizon 2025]

The network is causal: the inputs of year t are built only from observations of
year t-1 (``ml.fused.tensors``). Appending the horizon year to the time axis
therefore yields a genuine forecast: its inputs are the last observed year and
no observation of the horizon exists. The same weights produced the 2024 test
estimate from data up to 2023, which is the out-of-sample evidence reported in
the model card. The script checks that the in-sample years are reproduced
exactly before writing anything.

Output ``forecast.csv`` (one row per unit and subperiod of the horizon):
index and level against the frozen training reference, the ensemble range of
the index (minimum and maximum member), the index of the same subperiod in the
last observed year, and, for districts, the expected number of collisions at
the reference reporting scale (CENACOM, rho = 1).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from ml.fused.explain import load_members
from ml.fused.export import level_of, percentile_index, period_id
from ml.fused.tensors import load_dataset
from ml.fused.train import indicator, set_determinism
from pipelines.fusion.events import SUBPERIODS, days_of_type

HEADER = [
    "unit_type",
    "unit_id",
    "period_id",
    "horizon_year",
    "day_type",
    "band",
    "risk_index",
    "risk_level",
    "index_low",
    "index_high",
    "previous_index",
    "expected_events",
]


def member_lambdas(members, X: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """[M, T, K, H, W] latent expected collisions of each ensemble member."""
    x = torch.from_numpy(X)
    v = torch.from_numpy(valid.astype(np.float32))
    with torch.no_grad():
        return np.stack([(torch.exp(m(x)) * v).numpy() for m in members])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--horizon", type=int, default=2025)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    cfg = json.loads((args.run / "run_manifest.json").read_text(encoding="utf-8"))["config"]
    set_determinism(cfg.get("seed", 0), args.threads)
    years = list(cfg["years"])
    if args.horizon != years[-1] + 1:
        raise SystemExit(f"horizon must be {years[-1] + 1} (one step after the last year)")
    t = load_dataset(args.dataset, years + [args.horizon])
    members = load_members(args.run, t)
    lam_m = member_lambdas(members, t.X, t.valid)  # [M, T+1, K, H, W]
    lam = lam_m.mean(axis=0)

    # Causality check: in-sample years must equal the published estimates.
    est = np.load(args.run / "estimates.npz")
    gap = float(np.abs(lam[:-1] - est["lam"]).max())
    if gap > 1e-4:
        raise SystemExit(f"in-sample estimates differ from the published run ({gap:.2e})")

    th = cfg["thresholds"]
    th_low, th_med = th["low_max"], th["medium_max"]
    h, prev = len(years), len(years) - 1
    value_m = np.stack([indicator(t, lm, cfg["area_floor_km2"]) for lm in lam_m])  # [M,T,K,H,W]
    value = value_m.mean(axis=0)

    # District values aggregate counts first, then density (as in ml.fused.export).
    d_area = np.einsum("dhw,hw->d", t.frac, t.area_km2)
    days = np.array(
        [[days_of_type(y, dt) for (dt, _b) in SUBPERIODS] for y in t.years], dtype=float
    )
    lam_d_m = np.einsum("mtkhw,dhw->mtkd", lam_m, t.frac)
    value_d_m = lam_d_m / days[None, :, :, None] * 365.0 / d_area[None, None, None]
    value_d = value_d_m.mean(axis=0)
    train_years = sorted({y for ys in cfg["split"]["train"].values() for y in ys})
    train_t = [i for i, y in enumerate(years) if y in train_years and t.cover[:, i].max() > 0]
    ref_cells = est["reference"]
    ref_districts = np.sort(est_district_values(est["lam"], t, days[:-1], d_area)[train_t].ravel())

    rows: list[list[str]] = []
    cells = list(zip(t.unit_ids, t.rows, t.cols, strict=True))
    for k, (day_type, band) in enumerate(SUBPERIODS):
        pid = period_id(args.horizon, day_type, band)
        idx = percentile_index(value[h, k], ref_cells)
        idx_m = np.stack([percentile_index(v[h, k], ref_cells) for v in value_m])
        idx_prev = percentile_index(value[prev, k], ref_cells)
        for unit, r, c in cells:
            rows.append(
                [
                    "cell",
                    unit,
                    pid,
                    str(args.horizon),
                    day_type,
                    str(band),
                    f"{idx[r, c]:.2f}",
                    level_of(idx[r, c], th_low, th_med),
                    f"{idx_m[:, r, c].min():.2f}",
                    f"{idx_m[:, r, c].max():.2f}",
                    f"{idx_prev[r, c]:.2f}",
                    "",
                ]
            )
        didx = percentile_index(value_d[h, k], ref_districts)
        didx_m = np.stack([percentile_index(v[h, k], ref_districts) for v in value_d_m])
        didx_prev = percentile_index(value_d[prev, k], ref_districts)
        expected = lam_d_m[:, h, k].mean(axis=0)
        for di, ubigeo in enumerate(t.district_ids):
            rows.append(
                [
                    "district",
                    ubigeo,
                    pid,
                    str(args.horizon),
                    day_type,
                    str(band),
                    f"{didx[di]:.2f}",
                    level_of(didx[di], th_low, th_med),
                    f"{didx_m[:, di].min():.2f}",
                    f"{didx_m[:, di].max():.2f}",
                    f"{didx_prev[di]:.2f}",
                    f"{expected[di]:.3f}",
                ]
            )
    rows.sort(key=lambda row: (row[0], row[1], row[2]))
    out = args.run / "forecast.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle, lineterminator="\n")
        w.writerow(HEADER)
        w.writerows(rows)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    (args.run / "forecast_manifest.json").write_text(
        json.dumps(
            {
                "horizon_year": args.horizon,
                "inputs_last_year": years[-1],
                "members": len(members),
                "in_sample_max_abs_gap": gap,
                "rows": len(rows),
                "sha256": digest,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"forecast {args.horizon}: {len(rows)} rows, in-sample gap {gap:.1e}, sha256 {digest[:12]}"
    )


def est_district_values(lam: np.ndarray, t, days: np.ndarray, d_area: np.ndarray) -> np.ndarray:
    """District density [T, K, D] of the published estimates (training reference)."""
    lam_d = np.einsum("tkhw,dhw->tkd", lam, t.frac[:, :, :])
    return lam_d / days[:, :, None] * 365.0 / d_area[None, None]


if __name__ == "__main__":
    main()
