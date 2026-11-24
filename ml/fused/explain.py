"""Batch explanations of a trained run (HT-07/HT-08 interpretability; RNF-01).

Usage::

    python -m ml.fused.explain --dataset artifacts/datasets/fused-v1.0.0 \
        --run artifacts/runs/<run_id> --year 2024

Everything is computed **offline** and published like the risk results; the
API never runs the network (RG-02). Outputs in ``<run>/explanations/``:

* ``series.json``  per unit (cells and districts) and published year: events
  the network expects the observing source to record vs. events recorded.
  This shows the recurrent part at work year by year, in comparable units.
* ``attribution.json`` occlusion attribution for the explained year: for each
  input group, the % change of the unit's estimated intensity when that group
  is replaced by its neutral baseline (standardised mean for context, no prior
  events for history). Because the CNN reads a 5x5 km neighbourhood, the effect
  includes neighbouring cells.
* ``whatif.json``  district partial dependence: each context variable of the
  district's cells is multiplied by a factor (0 to 2x) and the district's
  estimated intensity for the explained year is recomputed (cf. Wexler et al.,
  What-If Tool, 2019). Factors are fixed below; the UI only reads them.
* ``card.json``  architecture, parameter count, training curves and search.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from ml.fused.model import SpatioTemporalModel
from ml.fused.tensors import Tensors, load_dataset
from pipelines.fusion.events import SOURCE_FAMILIES, SUBPERIODS

WHATIF_FACTORS = (0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
# Variables an analyst would vary; v1.0 datasets fall back to the ones they have.
WHATIF_VARIABLES = (
    "population",
    "poi_commerce",
    "transit_stops",
    "footway_km",
    "arterial_km",
    "osm_crossings",
    "transit_route_km",
    "pedestrian_crossings",
)
GROUPS = {
    "population": ["population"],
    "transit": ["transit_stops", "transit_route_km"],
    "street_network": ["street_km", "special_road_km", "collector_km"],
    "crossings_signals": ["traffic_lights", "pedestrian_crossings", "osm_signals"],
    "activity": ["poi_commerce", "poi_education", "poi_health"],
    "walkability": ["footway_km", "osm_crossings"],
    "traffic": ["arterial_km"],
    "prior_collisions": [
        "cenacom_prev_cell_rate",
        "cenacom_prev_district_density",
        "onsv_prev_cell_rate",
        "onsv_prev_district_density",
    ],
}


def _optional_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_members(run: Path, t: Tensors) -> list[SpatioTemporalModel]:
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    cfg = manifest["config"]
    blob = torch.load(run / "model.pt", weights_only=False)
    variant = metrics["selected_variant"]
    states = blob["members"] if isinstance(blob, dict) and "members" in blob else [blob]
    members = []
    for state in states:
        m = SpatioTemporalModel(
            t.X.shape[1],
            len(SUBPERIODS),
            len(SOURCE_FAMILIES),
            cfg["hidden"],
            cfg["dropout"],
            variant,
        )
        m.load_state_dict(state)
        m.eval()
        members.append(m)
    return members


def ensemble_lambda(members, x: torch.Tensor, valid: torch.Tensor) -> np.ndarray:
    with torch.no_grad():
        return np.mean([(torch.exp(m(x)) * valid).cpu().numpy() for m in members], axis=0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--device", default="cpu", help="cpu or cuda (forward passes only)")
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    manifest = json.loads((args.run / "run_manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((args.run / "metrics.json").read_text(encoding="utf-8"))
    cfg = manifest["config"]
    t = load_dataset(args.dataset, cfg["years"])
    members = [m.to(args.device) for m in load_members(args.run, t)]
    out = args.run / "explanations"
    out.mkdir(exist_ok=True)
    x = torch.from_numpy(t.X).to(args.device)
    valid = torch.from_numpy(t.valid.astype(np.float32)).to(args.device)
    ti = t.years.index(args.year)
    groups = {g: [c for c in chs if c in t.channels] for g, chs in GROUPS.items()}
    groups = {g: chs for g, chs in groups.items() if chs}
    rows, cols = t.rows, t.cols
    lam = ensemble_lambda(members, x, valid)  # [T, K, H, W]
    rho = np.mean(
        [torch.exp(m.reporting_factors()).detach().cpu().numpy() for m in members], axis=0
    )
    split = cfg["split"]
    published = [
        (i, y)
        for i, y in enumerate(t.years)
        if t.cover[:, i].max() > 0
        and any(y in ys for part in split.values() for ys in part.values())
    ]

    # ---------------------------------------------------------------- series
    series = {"years": [y for _, y in published], "cell": {}, "district": {}}
    frac = t.frac
    for unit_id, r, c in zip(t.unit_ids, rows, cols, strict=True):
        exp, obs = [], []
        for i, _y in published:
            s = int(np.argmax(t.cover[:, i].max(axis=1)))  # observing family
            scale = rho[s] * t.cover[s, i] * t.located[s, i]
            exp.append(round(float((lam[i, :, r, c] * scale).sum()), 4))
            obs.append(round(float(t.y_cell[s, i, :, r, c].sum()), 4))
        series["cell"][unit_id] = {"expected": exp, "observed": obs}
    lam_d = np.einsum("tkhw,dhw->tkd", lam, frac)
    for di, d in enumerate(t.district_ids):
        exp, obs = [], []
        for i, _y in published:
            s = int(np.argmax(t.cover[:, i].max(axis=1)))
            exp.append(round(float((lam_d[i, :, di] * rho[s] * t.cover[s, i]).sum()), 4))
            obs.append(round(float(t.events_total[s, i, :, di].sum()), 4))
        series["district"][d] = {"expected": exp, "observed": obs}
    series["observing_family"] = [
        SOURCE_FAMILIES[int(np.argmax(t.cover[:, i].max(axis=1)))] for i, _ in published
    ]
    (out / "series.json").write_text(json.dumps(series), encoding="utf-8")

    # ---------------------------------------------------------------- attribution (occlusion)
    base_cell = lam[ti].sum(axis=0)  # [H, W]
    base_dist = lam_d[ti].sum(axis=0)
    attribution = {"year": args.year, "groups": list(groups), "cell": {}, "district": {}}
    effects_cell, effects_dist = {}, {}
    for group, channels in groups.items():
        xo = x.clone()
        for ch in channels:
            xo[:, t.channels.index(ch)] = 0.0  # standardised mean (context) / no prior events
        lam_o = ensemble_lambda(members, xo, valid)
        effects_cell[group] = (
            (base_cell - lam_o[ti].sum(axis=0)) / np.maximum(base_cell, 1e-9) * 100
        )
        lo_d = np.einsum("khw,dhw->d", lam_o[ti], frac)
        effects_dist[group] = (base_dist - lo_d) / np.maximum(base_dist, 1e-9) * 100
    for unit_id, r, c in zip(t.unit_ids, rows, cols, strict=True):
        attribution["cell"][unit_id] = [round(float(effects_cell[g][r, c]), 2) for g in groups]
    for di, d in enumerate(t.district_ids):
        attribution["district"][d] = [round(float(effects_dist[g][di]), 2) for g in groups]
    (out / "attribution.json").write_text(json.dumps(attribution), encoding="utf-8")

    # ---------------------------------------------------------------- what-if (district PDP)
    raw = np.load(args.dataset / "context.npz")
    stats = {}
    for name in t.context_order:
        vals = np.log1p(raw[name])
        stats[name] = (vals.mean(), vals.std() + 1e-6)
    whatif_vars = [v for v in WHATIF_VARIABLES if v in t.context_order][:6]
    whatif = {
        "year": args.year,
        "factors": list(WHATIF_FACTORS),
        "variables": whatif_vars,
        "district": {},
    }
    # Resumable: each finished district is checkpointed, so an interrupted run continues.
    partial = out / "whatif.partial.json"
    if partial.exists():
        saved = json.loads(partial.read_text(encoding="utf-8"))
        if saved["factors"] == whatif["factors"] and saved["variables"] == whatif["variables"]:
            whatif["district"] = saved["district"]
    raw_grid = {}
    for name in t.context_order:
        g = np.zeros(t.valid.shape, dtype=np.float64)
        g[rows, cols] = raw[name]
        raw_grid[name] = g
    for di, d in enumerate(t.district_ids):
        if d in whatif["district"]:
            continue
        mask = frac[di] > 0.5  # cells owned mostly by the district
        curves = {}
        for name in whatif_vars:
            ch = t.channels.index(name)
            mean, std = stats[name]
            curve = []
            for f in WHATIF_FACTORS:
                if f == 1.0:
                    curve.append(0.0)
                    continue
                xo = x.clone()
                scaled = (np.log1p(raw_grid[name] * f) - mean) / std
                layer = xo[:, ch].cpu().numpy()
                layer[:, mask] = scaled[mask].astype(np.float32)
                xo[:, ch] = torch.from_numpy(layer).to(xo.device)
                lo = ensemble_lambda(members, xo, valid)
                ld = float(np.einsum("khw,hw->", lo[ti], frac[di]))
                curve.append(round(float((ld - base_dist[di]) / max(base_dist[di], 1e-9) * 100), 2))
            curves[name] = curve
        whatif["district"][d] = curves
        partial.write_text(json.dumps(whatif), encoding="utf-8")
        print("whatif", d, flush=True)
    (out / "whatif.json").write_text(json.dumps(whatif), encoding="utf-8")
    partial.unlink(missing_ok=True)

    # ---------------------------------------------------------------- model card
    m0 = members[0]
    card = {
        "run_id": manifest["run_id"],
        "model_family": manifest["model_family"],
        "variant": metrics["selected_variant"],
        "members": len(members),
        "parameters": int(sum(p.numel() for p in m0.parameters())),
        "layers": [f"{name}: {tuple(p.shape)}" for name, p in m0.named_parameters()],
        "input_channels": t.channels,
        "tensor_shapes": manifest["tensor_shapes"],
        "config": {
            k: cfg[k]
            for k in (
                "hidden",
                "dropout",
                "lr",
                "weight_decay",
                "max_epochs",
                "patience",
                "seed",
                "threads",
            )
        }
        | {"device": cfg.get("device", "cpu")},
        "split": split,
        "weights_sha256": manifest["weights_sha256"],
        "code_commit_sha": manifest["code_commit_sha"],
        "torch": manifest["torch"],
        "elapsed_seconds": manifest["elapsed_seconds"],
        "training_curves": {v: c.get("history") for v, c in metrics.get("candidates", {}).items()}
        | {f"ensemble_seed_{h['seed']}": h["history"] for h in metrics.get("ensemble_members", [])},
        "search": metrics.get("search"),
        "reporting_factor": metrics["reporting_factor"],
        "selection_rule": metrics.get("selection_rule"),
        "high_level": _optional_json(args.run / "high_level.json"),
        "reproducibility": _optional_json(args.run / "reproducibility.json"),
        # Scale-free prioritisation and noise ceiling of the test years (optional).
        "prioritisation": _optional_json(args.run / "prioritisation.json"),
        "noise_ceiling": _optional_json(args.run / "noise_ceiling.json"),
    }
    (out / "card.json").write_text(json.dumps(card), encoding="utf-8")
    print("explanations written to", out)


if __name__ == "__main__":
    main()
