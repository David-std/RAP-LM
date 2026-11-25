"""Train, benchmark and export one run (HT-02, HT-07, HT-08; RM-01..RM-05; WBS 3.1.2-3.2.3, 4.4).

Usage::

    python -m ml.fused.train --dataset artifacts/datasets/fused-v1.0.0 \
        --config ml/configs/run-main.json --out artifacts/runs/<run_id>

The protocol (split, error measure, baseline, thresholds) is read from the
config and frozen in docs/ml/benchmark-protocol.md before evaluation. Test
years are never used for training, early stopping or model selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import time
from pathlib import Path

import numpy as np
import torch

from ml.fused.model import VARIANTS, SpatioTemporalModel, expected_observations
from ml.fused.tensors import Tensors, load_dataset
from pipelines.fusion.events import SOURCE_FAMILIES, SUBPERIODS, days_of_type
from pipelines.lineage import git_sha, tree_is_clean

EPS = 1e-3
# The plan commits a CNN-RNN: only these candidates can become the published model.
CNN_RNN_VARIANTS = ("cnn_lstm", "convlstm")


def set_determinism(seed: int, threads: int, device: str = "cpu") -> None:
    """Seeded, deterministic execution (CPU threads or CUDA), recorded in the manifest.

    On CUDA, cuBLAS needs a fixed workspace and cuDNN its deterministic kernels so
    that a rerun on the same GPU and driver is meant to reproduce the weights. CPU
    and GPU results are not bit-identical to each other.
    """
    if device.startswith("cuda"):
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        torch.cuda.manual_seed_all(seed)
    torch.manual_seed(seed)
    np.random.seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(threads)


def to_torch(t: Tensors, device: str = "cpu") -> dict[str, torch.Tensor]:
    arrays = {
        "X": t.X,
        "valid": t.valid.astype(np.float32),
        "y_cell": t.y_cell,
        "y_dist": t.y_dist,
        "cover": t.cover,
        "located": t.located,
        "frac": t.frac,
    }
    return {k: torch.from_numpy(v).to(device) for k, v in arrays.items()}


def year_mask(t: Tensors, years_by_family: dict[str, list[int]]) -> torch.Tensor:
    """[S, T] mask of family-years in a partition that the family actually observes."""
    m = np.zeros((len(SOURCE_FAMILIES), len(t.years)), dtype=np.float32)
    for s, fam in enumerate(SOURCE_FAMILIES):
        for y in years_by_family.get(fam, []):
            ti = t.years.index(y)
            if t.cover[s, ti].max() > 0:
                m[s, ti] = 1
    return torch.from_numpy(m)


def poisson_nll(model: SpatioTemporalModel, d: dict, mask: torch.Tensor) -> torch.Tensor:
    log_lambda = model(d["X"])
    log_report = model.reporting_factors()
    mu_c, mu_d = expected_observations(
        log_lambda, log_report, d["cover"], d["located"], d["frac"], d["valid"]
    )
    mc = mask[:, :, None, None, None] * d["valid"]
    md = mask[:, :, None, None]
    nll_c = ((mu_c - d["y_cell"] * torch.log(mu_c + 1e-8)) * mc).sum()
    nll_d = ((mu_d - d["y_dist"] * torch.log(mu_d + 1e-8)) * md).sum()
    events = (d["y_cell"] * mc).sum() + (d["y_dist"] * md).sum()
    return (nll_c + nll_d) / events.clamp(min=1)


def fit(t: Tensors, cfg: dict, variant: str) -> tuple[SpatioTemporalModel, dict]:
    device = cfg.get("device", "cpu")
    set_determinism(cfg["seed"], cfg["threads"], device)
    d = to_torch(t, device)
    model = SpatioTemporalModel(
        in_channels=t.X.shape[1],
        subperiods=len(SUBPERIODS),
        families=len(SOURCE_FAMILIES),
        hidden=cfg["hidden"],
        dropout=cfg["dropout"],
        variant=variant,
    ).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    train_mask = year_mask(t, cfg["split"]["train"]).to(device)
    val_mask = year_mask(t, cfg["split"]["validation"]).to(device)
    best = (float("inf"), None, 0)
    history = []
    fixed = cfg.get("fixed_epochs")
    if fixed:
        # Final refit (D-17): every observed year trains the network for a training length
        # fixed beforehand on development folds; no year is held out for early stopping.
        for epoch in range(fixed):
            model.train()
            opt.zero_grad()
            loss = poisson_nll(model, d, train_mask)
            loss.backward()
            opt.step()
            history.append((epoch, round(loss.item(), 6), None))
        model = model.cpu()
        model.eval()
        return model, {
            "variant": variant,
            "best_epoch": fixed - 1,
            "best_validation_nll": None,
            "epochs_run": fixed,
            "history_tail": history[-5:],
            "history": history,
        }
    for epoch in range(cfg["max_epochs"]):
        model.train()
        opt.zero_grad()
        loss = poisson_nll(model, d, train_mask)
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            val = poisson_nll(model, d, val_mask).item()
        history.append((epoch, round(loss.item(), 6), round(val, 6)))
        if epoch % 25 == 0:
            print(f"  {variant} epoch {epoch} train {loss.item():.5f} val {val:.5f}", flush=True)
        if val < best[0] - 1e-5:
            best = (val, {k: v.clone() for k, v in model.state_dict().items()}, epoch)
        elif epoch - best[2] >= cfg["patience"]:
            break
    model.load_state_dict(best[1])
    model = model.cpu()  # prediction, export and explanations run on CPU
    model.eval()
    return model, {
        "variant": variant,
        "best_epoch": best[2],
        "best_validation_nll": round(best[0], 6),
        "epochs_run": len(history),
        "history_tail": history[-5:],
        "history": history,  # (epoch, train NLL, validation NLL) for training curves
    }


def predict(model: SpatioTemporalModel, t: Tensors) -> dict[str, np.ndarray]:
    d = to_torch(t)
    with torch.no_grad():
        log_lambda = model(d["X"])
        log_report = model.reporting_factors()
        mu_c, _ = expected_observations(
            log_lambda, log_report, d["cover"], d["located"], d["frac"], d["valid"]
        )
        lam = (torch.exp(log_lambda) * d["valid"]).numpy()
    rho = np.exp(log_report.detach().numpy())
    district_full = (
        np.einsum("tkhw,dhw->tkd", lam, t.frac)[None] * (rho[:, None, None] * t.cover)[..., None]
    )
    return {"lambda": lam, "mu_cell": mu_c.numpy(), "mu_district_total": district_full, "rho": rho}


def historical_average(t: Tensors, s: int, ti: int) -> tuple[np.ndarray, np.ndarray] | None:
    """Baseline B0: mean of the same family's prior covered years, same cell/district and subperiod.

    Counts are rescaled by coverage (and located share for cells) so that a
    half-observed year contributes a rate, not a fake low count.
    """
    prior = [p for p in range(ti) if t.cover[s, p].max() > 0]
    if not prior:
        return None
    cell_rates = []
    dist_rates = []
    for p in prior:
        cov = t.cover[s, p][:, None, None]
        q = max(float(t.located[s, p]), 1e-6)
        cell_rates.append(t.y_cell[s, p] / (cov * q))
        dist_rates.append(t.events_total[s, p] / t.cover[s, p][:, None])
    cell = np.mean(cell_rates, axis=0) * (t.cover[s, ti][:, None, None] * t.located[s, ti])
    dist = np.mean(dist_rates, axis=0) * t.cover[s, ti][:, None]
    return cell, dist


def deviance(y: np.ndarray, mu: np.ndarray) -> float:
    mu = np.maximum(mu, EPS)
    term = np.where(y > 0, y * np.log(np.maximum(y, EPS) / mu), 0.0) - (y - mu)
    return float(2 * term.mean())


def capture(y: np.ndarray, score: np.ndarray, valid: np.ndarray, share: float = 0.10) -> float:
    """Share of observed located events inside the top ``share`` cells ranked by score."""
    s = score.sum(axis=0)[valid]
    obs = y.sum(axis=0)[valid]
    if obs.sum() <= 0:
        return float("nan")
    k = max(1, int(round(share * s.size)))
    top = np.argsort(-s, kind="stable")[:k]
    return float(obs[top].sum() / obs.sum())


def evaluate(t: Tensors, pred: dict, years_by_family: dict[str, list[int]]) -> list[dict]:
    rows = []
    for s, fam in enumerate(SOURCE_FAMILIES):
        for y in years_by_family.get(fam, []):
            ti = t.years.index(y)
            if t.cover[s, ti].max() <= 0:
                continue
            base = historical_average(t, s, ti)
            obs_cell = t.y_cell[s, ti]
            obs_dist = t.events_total[s, ti]
            model_cell = pred["mu_cell"][s, ti]
            model_dist = pred["mu_district_total"][s, ti]
            row = {
                "family": fam,
                "year": y,
                "observed_events": float(obs_dist.sum()),
                "located_events": float(obs_cell.sum()),
                "model": {
                    "district_mae": float(np.abs(model_dist - obs_dist).mean()),
                    "cell_mae": float(np.abs(model_cell - obs_cell)[:, t.valid].mean()),
                    "cell_deviance": deviance(obs_cell[:, t.valid], model_cell[:, t.valid]),
                    "capture_top10": capture(obs_cell, model_cell, t.valid),
                },
            }
            if base is None:
                row["baseline"] = None
                row["relative_improvement_pct"] = None
                row["note"] = "No prior year of this family: historical average undefined."
            else:
                bc, bd = base
                row["baseline"] = {
                    "district_mae": float(np.abs(bd - obs_dist).mean()),
                    "cell_mae": float(np.abs(bc - obs_cell)[:, t.valid].mean()),
                    "cell_deviance": deviance(obs_cell[:, t.valid], bc[:, t.valid]),
                    "capture_top10": capture(obs_cell, bc, t.valid),
                }
                e_base, e_model = row["baseline"]["district_mae"], row["model"]["district_mae"]
                row["relative_improvement_pct"] = (
                    None if e_base == 0 else round((e_base - e_model) / e_base * 100, 4)
                )
                if e_base == 0:
                    row["note"] = (
                        "Baseline error is zero: M-05 not computable (no division by zero)."
                    )
            rows.append(row)
    return rows


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def indicator(t: Tensors, lam: np.ndarray, area_floor: float) -> np.ndarray:
    """Annualised expected collisions per km2 for each [T, K, H, W]."""
    days = np.array(
        [[days_of_type(y, dt) for (dt, _b) in SUBPERIODS] for y in t.years], dtype=np.float64
    )
    area = np.maximum(t.area_km2, area_floor)
    return lam / days[:, :, None, None] * 365.0 / np.where(t.valid, area, 1.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--variants", default=",".join(VARIANTS))
    args = parser.parse_args()
    # Lineage is captured before any work so later commits cannot change it.
    code_sha, code_clean = git_sha(), tree_is_clean()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()

    t = load_dataset(args.dataset, cfg["years"])
    split = cfg["split"]

    # HT-02: benchmark alternatives on the validation years only.
    candidates = {}
    for variant in args.variants.split(","):
        model, info = fit(t, cfg, variant)
        pred = predict(model, t)
        info["validation"] = evaluate(t, pred, split["validation"])
        candidates[variant] = (model, info, pred)
        print(variant, info["best_epoch"], info["best_validation_nll"])
    eligible = [v for v in candidates if v in CNN_RNN_VARIANTS]
    if not eligible:
        raise SystemExit("No CNN-RNN candidate was trained; the plan requires one.")
    selected = min(eligible, key=lambda v: candidates[v][1]["best_validation_nll"])
    model, info, pred = candidates[selected]

    # Frozen evaluation on the independent test years (RM-05, M-05), once per
    # candidate and after selection; references are reported, never hidden.
    for _variant, (_m, cand_info, cand_pred) in candidates.items():
        cand_info["test"] = evaluate(t, cand_pred, split["test"])
    test = info["test"]
    validation_baseline = info["validation"]

    lam = pred["lambda"]
    value = indicator(t, lam, cfg["area_floor_km2"])
    train_years = sorted({y for ys in split["train"].values() for y in ys})
    ref_t = [t.years.index(y) for y in train_years]
    reference = np.sort(value[ref_t][:, :, t.valid].ravel())

    model_path = out / "model.pt"
    torch.save(model.state_dict(), model_path)
    np.savez_compressed(
        out / "estimates.npz",
        years=np.array(t.years),
        lam=lam.astype(np.float64),
        indicator=value,
        reference=reference,
        rho=pred["rho"],
    )
    metrics = {
        "selected_variant": selected,
        "selection_rule": "CNN-RNN candidate with the lowest validation Poisson NLL",
        "candidates": {v: c[1] for v, c in candidates.items()},
        "validation": validation_baseline,
        "test": test,
        "reporting_factor": dict(zip(SOURCE_FAMILIES, pred["rho"].round(6).tolist(), strict=True)),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    manifest = {
        "run_id": cfg["run_id"],
        "config": cfg,
        "dataset_manifest_sha256": sha256_bytes(
            (args.dataset / "dataset_manifest.json").read_bytes()
        ),
        "model_family": f"pytorch:{selected}",
        "code_commit_sha": code_sha,
        "code_tree_clean": code_clean,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "threads": cfg["threads"],
        "weights_sha256": sha256_bytes(model_path.read_bytes()),
        "estimates_sha256": sha256_bytes((out / "estimates.npz").read_bytes()),
        "tensor_shapes": {"X": list(t.X.shape), "y_cell": list(t.y_cell.shape)},
        "channels": t.channels,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"selected": selected, "test": test}, indent=2))


if __name__ == "__main__":
    main()
