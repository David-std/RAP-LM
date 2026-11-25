# ruff: noqa: E501
"""V13 pilot: pretraining on other Peruvian cities, fine-tuning in Lima. See docs/ml/performance-v13.md.

Source provinces contribute CENACOM pedestrian collisions (AT105 in 1, 2, 7) at district
level only (no street geocoding outside Lima). Lima and the sources share one reduced input
set available nationwide: annual population (standardised with Lima's training-year
statistics), the cell mask, and the previous-year district density of each source.

    python -m ml.experiments.transfer build
    python -m ml.experiments.transfer train --folds D2b,D3b
    python -m ml.experiments.transfer report --folds D2b,D3b
"""

from __future__ import annotations

import argparse
import json
import pickle
import time
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import torch
from shapely.geometry import shape

from ml.experiments.v10 import FOLDS, SEEDS, load_fold, score_unit, strata_targets
from ml.experiments.v10 import OUT as V10_OUT
from ml.fused.model import SpatioTemporalModel
from ml.fused.train import (
    historical_average,
    poisson_nll,
    predict,
    set_determinism,
    to_torch,
    year_mask,
)
from pipelines.fusion.context import annual_population
from pipelines.fusion.dbf import read_dbf_bytes
from pipelines.fusion.events import SOURCE_FAMILIES, SUBPERIODS, coverage_fraction
from pipelines.spatial.grid import District, build_grid, to_analysis

RAW = Path(r"C:/Users/david/Downloads/RAP-LM-DATA-LOCAL/raw/RAP-LM-DATA")
BOUNDARIES = RAW / "geography/boundaries/national/peru_distrital_simple.geojson"
SOURCES = ["0401", "0701", "1301", "0801", "1401", "0218", "1201", "2001", "2301", "1101"]
MIN_EVENTS = 15  # urban districts of each source province (2011-2017 total)
OUT = Path("artifacts/runs/performance-v13")
CACHE = OUT / "sources.pkl"
LIMA_CHANNELS = [
    "population",
    "valid_cell",
    "cenacom_prev_district_density",
    "cenacom_prev_observed",
    "onsv_prev_district_density",
    "onsv_prev_observed",
]
K_INDEX = {sp: i for i, sp in enumerate(SUBPERIODS)}


@dataclass
class City:
    name: str
    years: list
    X: np.ndarray
    valid: np.ndarray
    y_cell: np.ndarray
    y_dist: np.ndarray
    events_total: np.ndarray
    cover: np.ndarray
    located: np.ndarray
    frac: np.ndarray
    area_km2: np.ndarray
    pop_log: np.ndarray  # [T_all, H, W] log1p population by calendar year 2011-2025


def _int(v):
    try:
        return int(str(v).strip())
    except ValueError:
        return None


def source_events():
    """Pedestrian collisions of the source provinces from every CENACOM edition."""
    events = []
    for ed in sorted(p for p in (RAW / "accidents/cenacom").iterdir() if p.is_dir()):
        for z in sorted((ed / "microdata").glob("*.zip")):
            zz = zipfile.ZipFile(z)
            names = [
                n
                for n in zz.namelist()
                if n.lower().endswith(".dbf") and ("100" in n or "Cap" in n)
            ]
            if not names:
                continue
            fields, recs = read_dbf_bytes(zz.read(names[0]))
            if "AT105" not in fields:
                continue
            for r in recs:
                if r.get("AT105") not in ("1", "2", "7"):
                    continue
                y, m, d, h = (
                    _int(r.get(k)) for k in ("AT103_A", "AT103_M", "AT103_D", "AT103_HOR")
                )
                if not (y and m and d and h is not None) or not (
                    2011 <= y <= 2017 and 1 <= m <= 12 and 0 <= h <= 23
                ):
                    continue
                try:
                    day = date(y, m, d)
                except ValueError:
                    continue
                pro, dis = r.get("AT104D_PRO", "").strip(), r.get("AT104D_DIS", "").strip()
                if pro and dis and pro.isdigit() and dis.isdigit():
                    ub = (
                        (r.get("AT104D_DPT", "").strip() or r["UBIGEO"][:2]).zfill(2)
                        + pro.zfill(2)
                        + dis.zfill(2)
                    )
                else:
                    ub = r["UBIGEO"].strip()  # station district (2011-2014 editions)
                if ub[:4] not in SOURCES:
                    continue
                day_type = "weekend" if day.weekday() >= 5 else "weekday"
                events.append((ub, y, K_INDEX[(day_type, h // 6)]))
    return events


def lima_population_stats():
    """Mean and std of log1p population over Lima's valid cells and the D2b training years."""
    ctx = np.load("artifacts/datasets/fused-v1.4.0/context.npz")
    years = [int(y) for y in ctx["population_years"]]
    rows = [years.index(y) for y in range(2011, 2016)]
    logs = np.log1p(ctx["population_by_year"][rows])
    return float(logs.mean()), float(logs.std() + 1e-6)


def build():
    events = source_events()
    counts = {}
    for ub, _, _ in events:
        counts[ub] = counts.get(ub, 0) + 1
    payload = json.loads(BOUNDARIES.read_text(encoding="utf-8"))
    cities = {}
    for prov in SOURCES:
        dists = [
            District(
                f["properties"]["IDDIST"],
                f["properties"]["NOMBDIST"],
                to_analysis(shape(f["geometry"]).buffer(0)),
            )
            for f in payload["features"]
            if f["geometry"] and f["properties"]["IDDIST"][:4] == prov
            and counts.get(f["properties"]["IDDIST"], 0) >= MIN_EVENTS
        ]
        if not dists:
            continue
        dists.sort(key=lambda d: d.ubigeo)
        spec, cells = build_grid(dists)
        _, pop, _ = annual_population(RAW, spec, cells)
        H, W = spec.rows, spec.cols
        d_index = {d.ubigeo: i for i, d in enumerate(dists)}
        valid = np.zeros((H, W), bool)
        frac = np.zeros((len(dists), H, W), np.float32)
        area = np.zeros((H, W), np.float32)
        pop_log = np.zeros((pop.shape[0], H, W), np.float32)
        for ci, c in enumerate(cells):
            r, cc = c.row - 1, c.col - 1
            valid[r, cc] = True
            area[r, cc] = c.area_km2
            for ub, share in c.district_fractions.items():
                frac[d_index[ub], r, cc] = share
            pop_log[:, r, cc] = np.log1p(pop[:, ci])
        ev = [(d_index[ub], y, k) for ub, y, k in events if ub in d_index]
        cities[prov] = {
            "valid": valid,
            "frac": frac,
            "area": area,
            "pop_log": pop_log,
            "events": ev,
            "districts": [d.ubigeo for d in dists],
        }
        print(
            prov, len(dists), "districts", int(valid.sum()), "cells", len(ev), "events", flush=True
        )
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(pickle.dumps(cities))


def city_tensors(c, years, train_last, pop_mean, pop_std):
    """City object in the reduced input set; covariates of later years frozen at train_last."""
    T, K, D = len(years), len(SUBPERIODS), c["frac"].shape[0]
    H, W = c["valid"].shape
    S = len(SOURCE_FAMILIES)
    y_dist = np.zeros((S, T, K, D), np.float32)
    for di, y, k in c["events"]:
        if y in years:
            y_dist[0, years.index(y), k, di] += 1
    cover = np.zeros((S, T, K), np.float32)
    for ti, y in enumerate(years):
        for k, (dt, _b) in enumerate(SUBPERIODS):
            cover[0, ti, k] = coverage_fraction("cenacom", y, dt)
    d_area = np.maximum((c["frac"] * c["area"][None]).sum(axis=(1, 2)), 1e-6)
    X = np.zeros((T, len(LIMA_CHANNELS), H, W), np.float32)
    for ti, y in enumerate(years):
        X[ti, 0] = (c["pop_log"][min(y, train_last) - 2011] - pop_mean) / pop_std * c["valid"]
        X[ti, 1] = c["valid"]
        if ti > 0 and cover[0, ti - 1].mean() > 0:
            dens = y_dist[0, ti - 1].sum(axis=0) / cover[0, ti - 1].mean() / d_area
            X[ti, 2] = np.log1p(np.tensordot(dens, c["frac"], axes=(0, 0))) * c["valid"]
            X[ti, 3] = c["valid"]
    return City(
        "src",
        years,
        X,
        c["valid"],
        np.zeros((S, T, K, H, W), np.float32),
        y_dist,
        y_dist.copy(),
        cover,
        np.zeros((S, T), np.float32),
        c["frac"],
        c["area"],
        c["pop_log"],
    )


def lima_reduced(t):
    idx = [t.channels.index(ch) for ch in LIMA_CHANNELS]
    t.X = t.X[:, idx].copy()
    t.channels = list(LIMA_CHANNELS)
    return t


def run_epoch(model, opt, batches):
    model.train()
    opt.zero_grad()
    loss = sum(poisson_nll(model, d, m) for d, m in batches) / len(batches)
    loss.backward()
    opt.step()
    return float(loss)


def train(folds):
    cities = pickle.loads(CACHE.read_bytes())
    pop_mean, pop_std = lima_population_stats()
    for name in folds:
        f, t = load_fold(name)
        t = lima_reduced(t)
        last_cen = max(f["train"]["cenacom"])
        src_years = list(range(2011, last_cen + 1))
        sources = [city_tensors(c, src_years, last_cen, pop_mean, pop_std) for c in cities.values()]
        for arm in ("A", "B"):
            out = OUT / name / arm
            out.mkdir(parents=True, exist_ok=True)
            for seed in SEEDS:
                path = out / f"s{seed}.npz"
                if path.exists():
                    continue
                start = time.perf_counter()
                set_determinism(seed, 8, "cuda")
                model = SpatioTemporalModel(
                    len(LIMA_CHANNELS), len(SUBPERIODS), len(SOURCE_FAMILIES), 32, 0.1, "convlstm"
                ).cuda()
                if arm == "B":
                    src = [
                        (to_torch(c, "cuda"), year_mask(c, {"cenacom": src_years}).cuda())
                        for c in sources
                    ]
                    opt = torch.optim.Adam(model.parameters(), lr=0.003, weight_decay=1e-4)
                    for _ in range(150):
                        run_epoch(model, opt, src)
                    del src
                lima = [(to_torch(t, "cuda"), year_mask(t, f["train"]).cuda())]
                opt = torch.optim.Adam(model.parameters(), lr=0.003, weight_decay=1e-4)
                for _ in range(f["epochs"]):
                    run_epoch(model, opt, lima)
                p = predict(model.cpu().eval(), t)
                np.savez_compressed(
                    path,
                    mu_cell=p["mu_cell"].astype(np.float32),
                    mu_district_total=p["mu_district_total"].astype(np.float32),
                )
                print(name, arm, seed, round(time.perf_counter() - start, 1), flush=True)
                del model
                torch.cuda.empty_cache()


def report(folds):
    rows = {}
    for name in folds:
        f, t = load_fold(name)
        fam, year = f["eval"]
        s, ti = SOURCE_FAMILIES.index(fam), t.years.index(year)
        strata = strata_targets(t, fam, year)
        hc, hd = historical_average(t, s, ti)
        res = {"historical": score_unit(t, strata, s, ti, hc, hd)}
        for arm, folder in (
            ("A_lima_reduced", OUT / name / "A"),
            ("B_transfer_reduced", OUT / name / "B"),
            ("C0_full_inputs", V10_OUT / name / "C0"),
        ):
            zs = [np.load(p) for p in sorted(folder.glob("s*.npz"))]
            if zs:
                mc = np.mean([z["mu_cell"] for z in zs], axis=0)[s, ti]
                md = np.mean([z["mu_district_total"] for z in zs], axis=0)[s, ti]
                res[arm] = score_unit(t, strata, s, ti, mc, md)
        rows[name] = res
        print(f"\n== {name} {f['eval']}")
        for k, r in res.items():
            a = r.get("all_located") or {}
            pr = r.get("precise") or {}
            print(
                f"{k:20s} dMAE {r['district']['mae']:.4f} rho {r['district']['spearman']:.3f} dev {r['district']['deviance']:.3f} | AUC {a.get('auc', float('nan')):.3f} AP {a.get('average_precision', float('nan')):.3f} c20 {a.get('capture_top20', float('nan')):.3f} | precise AP {pr.get('average_precision', float('nan')):.3f}"
            )
    out = Path("evidence/benchmarking/performance-v13")
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("build", "train", "report"))
    ap.add_argument("--folds", default="D2b,D3b")
    a = ap.parse_args()
    if a.action == "build":
        build()
    elif a.action == "train":
        train(a.folds.split(","))
    else:
        report(a.folds.split(","))


assert set(FOLDS) >= {"D2b", "D3b"}

if __name__ == "__main__":
    main()
