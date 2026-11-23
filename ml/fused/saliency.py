"""Grad-CAM maps for the published network (D-09).

Usage::

    python -m ml.fused.saliency --dataset artifacts/datasets/fused-v1.1.0 --run artifacts/runs/<run>

For a target unit (a district, or a cell of high level in the explained year)
the target is the network's total estimated intensity of that unit in the
explained year (all day types and bands). The influence of every grid cell is
|gradient x input| summed over input channels and over the years the
recurrence reads (gradient-weighted attribution in the spirit of Grad-CAM,
Selvaraju et al., 2017, applied to the input grid because the model regresses
intensities rather than classifying). Values are averaged over the ensemble
members and normalised so the strongest cell equals 1; the 40 strongest cells
are stored. Computed offline like every other explanation (RG-02).

Output: ``<run>/explanations/saliency.json`` with ``{"district": {...}, "cell": {...}}``
mapping a unit id to ``[[unit_id, weight], ...]``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from ml.fused.explain import load_members
from ml.fused.tensors import load_dataset

TOP_K = 40
MAX_CELLS = 400


def influence(
    members, x: torch.Tensor, valid: torch.Tensor, ti: int, weight: torch.Tensor
) -> np.ndarray:
    """[H, W] mean |grad x input| over members for target sum(lambda[ti] * weight)."""
    acc = np.zeros(x.shape[2:], dtype=np.float64)
    for m in members:
        xi = x.clone().requires_grad_(True)
        target = (torch.exp(m(xi))[ti] * valid * weight).sum()
        (grad,) = torch.autograd.grad(target, xi)
        acc += (grad * xi).abs().sum(dim=(0, 1)).detach().numpy()
    return acc / len(members)


def hidden_states(m, x: torch.Tensor) -> list[torch.Tensor]:
    """Encoder feature maps of every year with gradients retained.

    ConvLSTM: the hidden state h_t of each step (Shi et al., 2015); the state of
    year t reaches neighbouring cells of later years through the 3x3 gates, so
    the maps of earlier steps carry the spatial propagation. Other variants:
    the encoder output of each year.
    """
    enc = m.encoder
    if m.variant != "convlstm":
        feats = enc(x)
        feats.retain_grad()
        return [feats[t : t + 1] for t in range(x.shape[0])] + [feats]
    T, _, H, W = x.shape
    h = x.new_zeros(1, enc.hidden, H, W)
    c = x.new_zeros(1, enc.hidden, H, W)
    states = []
    for t in range(T):
        i, f, o, g = enc.gates(torch.cat([x[t : t + 1], h], dim=1)).chunk(4, dim=1)
        c = torch.sigmoid(f) * c + torch.sigmoid(i) * torch.tanh(g)
        h = torch.sigmoid(o) * torch.tanh(c)
        h.retain_grad()
        states.append(h)
    return states


def gradcam(
    members, x: torch.Tensor, valid: torch.Tensor, ti: int, weight: torch.Tensor
) -> np.ndarray:
    """[H, W] Grad-CAM map (HiResCAM variant) for the estimate of one unit in year ``ti``.

    Classic Grad-CAM (Selvaraju et al., 2017) averages the gradient over the whole
    map into one weight per channel, which suits a single class score but, for a
    dense regression output, also lights up distant cells that merely share the
    pattern. HiResCAM (Draelos and Carin, 2020) keeps the gradient per cell:
    ReLU(sum over channels and years <= ti of dTarget/dA * A), so every highlighted
    cell lies within the network's receptive field of the unit. Mean over members.
    """
    acc = np.zeros(x.shape[2:], dtype=np.float64)
    for m in members:
        states = hidden_states(m, x)
        if m.variant == "convlstm":
            feats = torch.cat(states, dim=0)
            steps = states[: ti + 1]
        else:
            feats = states[-1]
            steps = [feats]
        target = (torch.exp(m.head(feats))[ti] * valid * weight).sum()
        target.backward()
        cam = sum((s.grad * s).sum(dim=(0, 1)) for s in steps)
        acc += (torch.relu(cam) * valid).detach().numpy()
        m.zero_grad(set_to_none=True)
    return acc / len(members)


def top_cells(sal: np.ndarray, unit_at: dict[tuple[int, int], str]) -> list[list]:
    flat = [(float(sal[r, c]), u) for (r, c), u in unit_at.items() if sal[r, c] > 0]
    flat.sort(reverse=True)
    peak = flat[0][0] if flat else 1.0
    return [[u, round(v / peak, 4)] for v, u in flat[:TOP_K]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    cfg = json.loads((args.run / "run_manifest.json").read_text(encoding="utf-8"))["config"]
    t = load_dataset(args.dataset, cfg["years"])
    members = load_members(args.run, t)
    for m in members:
        m.train(False)
    x = torch.from_numpy(t.X)
    valid = torch.from_numpy(t.valid.astype(np.float32))
    ti = t.years.index(args.year)
    unit_at = {(int(r), int(c)): u for u, r, c in zip(t.unit_ids, t.rows, t.cols, strict=True)}
    out_path = args.run / "explanations" / "saliency.json"
    result = (
        json.loads(out_path.read_text(encoding="utf-8"))
        if out_path.exists()
        else {"district": {}, "cell": {}}
    )
    result.update(
        {
            "year": args.year,
            "method": "Grad-CAM (HiResCAM variant) on ConvLSTM hidden states, mean over members",
        }
    )

    for di, d in enumerate(t.district_ids):
        if d in result["district"]:
            continue
        w = torch.from_numpy((t.frac[di] > 0).astype(np.float32) * t.frac[di])
        result["district"][d] = top_cells(gradcam(members, x, valid, ti, w), unit_at)
        out_path.write_text(json.dumps(result), encoding="utf-8")
        print("district", d, flush=True)

    # Cells with the highest estimated index in the explained year (high-level cells first).
    est = np.load(args.run / "estimates.npz")
    ref = est["reference"]
    value = est["indicator"][ti].mean(axis=0)  # [H, W]
    pct = np.searchsorted(ref, value, side="right") / ref.size * 100
    ranked = sorted(((float(pct[r, c]), u, r, c) for (r, c), u in unit_at.items()), reverse=True)
    for _p, u, r, c in ranked[:MAX_CELLS]:
        if u in result["cell"]:
            continue
        w = torch.zeros_like(valid)
        w[r, c] = 1.0
        result["cell"][u] = top_cells(gradcam(members, x, valid, ti, w), unit_at)
        if len(result["cell"]) % 20 == 0:
            out_path.write_text(json.dumps(result), encoding="utf-8")
            print("cells", len(result["cell"]), flush=True)
    out_path.write_text(json.dumps(result), encoding="utf-8")
    print("saliency written", len(result["district"]), "districts,", len(result["cell"]), "cells")


if __name__ == "__main__":
    main()
