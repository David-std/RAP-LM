"""Severity and exposure components of the risk (plan v1.6 §1.2; D-10).

The plan defines pedestrian risk through frequency, severity of consequences
and exposure (Guo et al., 2024; Hu et al., 2024). The CNN-LSTM estimates the
frequency intensity lambda. Two further indicators are derived offline:

* **Expected severity**: lambda x p_fatal(unit), where p_fatal is the share of
  collisions with a fatal outcome among police-census events of known severity
  in the **training years**, shrunk with empirical Bayes towards the district and
  then the city share (prior strength ``PRIOR_EVENTS``). Reads: expected fatal-
  outcome collisions per km2 per year.
* **Exposure-adjusted risk ratio**: lambda / lambda_exposure, where
  lambda_exposure comes from a Poisson log-linear model that sees **only
  exposure proxies** (population, POIs, transit, footways, arterial roads) and
  is fitted on the same training family-years and observation model. Ratio 1 =
  as many collisions as the exposure proxies explain; 2 = twice as many. This
  is the observed/expected logic of standardised incidence ratios. Exposure is
  proxied, not measured (limitation L06).
"""

from __future__ import annotations

import numpy as np
import torch

from ml.fused.model import SpatioTemporalModel
from ml.fused.tensors import Tensors
from pipelines.fusion.events import SOURCE_FAMILIES, SUBPERIODS

PRIOR_EVENTS = 20.0
EXPOSURE_CHANNELS = (
    "population",
    "transit_stops",
    "transit_route_km",
    "poi_commerce",
    "poi_education",
    "poi_health",
    "footway_km",
    "arterial_km",
)


def fatal_share(t: Tensors, train_years: list[int]) -> np.ndarray:
    """[H, W] empirical-Bayes share of fatal outcomes among events of known severity."""
    if t.severity_cell is None:
        return np.zeros(t.valid.shape)
    ti = [t.years.index(y) for y in train_years if y in t.years]
    cell = t.severity_cell[ti].sum(axis=(0, 1))  # [4, H, W]
    fatal, known = cell[0], cell[0] + cell[1] + cell[2]
    dist = t.severity_dist[ti].sum(axis=(0, 1))  # [4, D]
    d_fatal, d_known = dist[0], dist[0] + dist[1] + dist[2]
    city = d_fatal.sum() / max(d_known.sum(), 1)
    p_dist = (d_fatal + PRIOR_EVENTS * city) / (d_known + PRIOR_EVENTS)
    owner = np.argmax(t.frac, axis=0)  # district holding most of each cell
    prior = p_dist[owner]
    return (fatal + PRIOR_EVENTS * prior) / (known + PRIOR_EVENTS) * t.valid


def exposure_lambda(t: Tensors, train_mask: torch.Tensor, cfg: dict) -> np.ndarray:
    """[T, K, H, W] intensity explained by exposure proxies only (Poisson GLM)."""
    from ml.fused.train import poisson_nll, set_determinism

    keep = [t.channels.index(c) for c in EXPOSURE_CHANNELS if c in t.channels]
    keep.append(t.channels.index("valid_cell"))
    set_determinism(cfg["seed"], cfg.get("threads", 1))
    d = {
        "X": torch.from_numpy(t.X[:, keep]),
        "valid": torch.from_numpy(t.valid.astype(np.float32)),
        "y_cell": torch.from_numpy(t.y_cell),
        "y_dist": torch.from_numpy(t.y_dist),
        "cover": torch.from_numpy(t.cover),
        "located": torch.from_numpy(t.located),
        "frac": torch.from_numpy(t.frac),
    }
    model = SpatioTemporalModel(
        len(keep), len(SUBPERIODS), len(SOURCE_FAMILIES), variant="poisson_glm"
    )
    opt = torch.optim.Adam(model.parameters(), lr=0.05)
    for _ in range(400):
        opt.zero_grad()
        loss = poisson_nll(model, d, train_mask)
        loss.backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        return (torch.exp(model(d["X"])) * d["valid"]).numpy()
