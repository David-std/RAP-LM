"""Annual chained forecast with the published network (RM-04, D-11, D-16).

Usage::

    python -m ml.fused.forecast --dataset artifacts/datasets/fused-v1.1.0 \
        --run artifacts/runs/<run_id> [--horizon 2025] [--steps 3]

The network is causal: the inputs of year t are built only from observations of
year t-1 (``ml.fused.tensors``). Appending the horizon year to the time axis
therefore yields a genuine forecast: its inputs are the last observed year and
no observation of the horizon exists. The same weights produced the 2024 test
estimate from data up to 2023, which is the out-of-sample evidence reported in
the model card. The script checks that the in-sample years are reproduced
exactly before writing anything.

For later horizons, use the preceding ensemble mean at the ONSV reporting scale
as the next lag, with covariates frozen at the last observed year. Member spread
is descriptive, not a calibrated prediction interval.

Output ``forecast.csv`` (one row per unit, subperiod and horizon):
index and level against the frozen training reference, the ensemble range of
the index (minimum and maximum member), the index of the same subperiod in the
preceding year (historical estimate or prior projection) and, for districts,
the expected number of collisions at
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
from pipelines.fusion.events import SOURCE_FAMILIES, SUBPERIODS, days_of_type

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
    ap.add_argument("--steps", type=int, default=1, help="chained years ahead (1 = horizon only)")
    args = ap.parse_args()
    if not 1 <= args.steps <= 3:
        ap.error("--steps must be between 1 and 3")

    cfg = json.loads((args.run / "run_manifest.json").read_text(encoding="utf-8"))["config"]
    set_determinism(cfg.get("seed", 0), args.threads)
    years = list(cfg["years"])
    if args.horizon != years[-1] + 1:
        raise SystemExit(f"horizon must be {years[-1] + 1} (one step after the last year)")
    # Covariates frozen at the last observed year: no information of the horizon year.
    horizons = [args.horizon + i for i in range(args.steps)]
    t = load_dataset(args.dataset, years + horizons, norm_years=years, covariates_asof=years[-1])
    members = load_members(args.run, t)
    est = np.load(args.run / "estimates.npz")
    # Chained forecast: the inputs of year h+1 are built from the forecast of year h
    # as if it had been observed by the source that observes the last years (ONSV),
    # at that source's reporting scale. Errors therefore compound with each step.
    s_obs = SOURCE_FAMILIES.index("onsv")
    base = len(t.context_order) + 1
    d_area_all = np.einsum("dhw,hw->d", t.frac, t.area_km2)
    for step in range(args.steps):
        lam_m = member_lambdas(members, t.X, t.valid)  # [M, T+steps, K, H, W]
        if step == args.steps - 1:
            break
        hi = len(years) + step
        expected = lam_m.mean(axis=0)[hi].sum(axis=0) * float(est["rho"][s_obs])  # [H, W]
        dist = np.einsum("hw,dhw->d", expected, t.frac) / d_area_all
        spread = np.tensordot(dist, t.frac, axes=(0, 0))
        t.X[hi + 1, base + 3 * s_obs] = np.log1p(expected) * t.valid
        t.X[hi + 1, base + 3 * s_obs + 1] = np.log1p(spread) * t.valid
        t.X[hi + 1, base + 3 * s_obs + 2] = t.valid
    lam = lam_m.mean(axis=0)

    # Causality check: in-sample years must equal the published estimates.
    gap = float(np.abs(lam[: len(years)] - est["lam"]).max())
    if gap > 1e-4:
        raise SystemExit(f"in-sample estimates differ from the published run ({gap:.2e})")

    th = cfg["thresholds"]
    th_low, th_med = th["low_max"], th["medium_max"]
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
    ref_districts = np.sort(
        est_district_values(est["lam"], t, days[: len(years)], d_area)[train_t].ravel()
    )

    rows: list[list[str]] = []
    cells = list(zip(t.unit_ids, t.rows, t.cols, strict=True))
    for h in range(len(years), len(years) + args.steps):
        prev, year_h = h - 1, t.years[h]
        for k, (day_type, band) in enumerate(SUBPERIODS):
            pid = period_id(year_h, day_type, band)
            idx = percentile_index(value[h, k], ref_cells)
            idx_m = np.stack([percentile_index(v[h, k], ref_cells) for v in value_m])
            idx_prev = percentile_index(value[prev, k], ref_cells)
            for unit, r, c in cells:
                rows.append(
                    [
                        "cell",
                        unit,
                        pid,
                        str(year_h),
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
                        str(year_h),
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
                "horizon_year": horizons[0],
                "horizon_years": horizons,
                "recursive_input": "ensemble_mean_at_onsv_reporting_scale",
                "range_method": "ensemble_member_min_max_not_prediction_interval",
                "inputs_last_year": years[-1],
                "covariates_asof": years[-1],
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
