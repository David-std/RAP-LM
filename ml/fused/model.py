"""Spatio-temporal intensity models (HT-07, HT-08; RM-01..RM-03).

Every model maps the input tensor ``x`` [T, C, H, W] (one city, T ordered
years) to ``log_lambda`` [T, K, H, W]: the log expected number of pedestrian
collisions (all severities) of each subperiod K (day type x time band), cell
and year. They differ only in the *encoder*; the output head, the per-source
reporting factors and the loss are shared, so the benchmark compares
architectures under one protocol.

Encoders (``VARIANTS``):

* ``cnn_lstm``  reference architecture of the project plan: a per-year CNN
  (RM-02, 5x5 km receptive field) followed by one LSTM per cell over the years
  (RM-03).
* ``convlstm``  ConvLSTM (Shi et al., NeurIPS 2015), the recurrent cell used by
  Hetero-ConvLSTM for traffic-accident risk on grids (Yuan et al., KDD 2018).
  Literature benchmark: spatial and temporal mixing happen inside the cell.
* ``cnn_only``  ablation without recurrence.
* ``lstm_only`` ablation without spatial context (1x1 kernels).
* ``poisson_glm`` log-linear Poisson regression on the same inputs: the classic
  count model of road-safety studies (no hidden layers).

Causality: the input of year t holds observations of year t-1 only (see
``ml/fused/tensors.py``) and every recurrence runs forward in time, so the
estimate of year t never uses data of year t or later.
"""

from __future__ import annotations

import torch
from torch import nn

VARIANTS = ("cnn_lstm", "convlstm", "cnn_only", "lstm_only", "poisson_glm")


# --------------------------------------------------------------------------- encoders
class ConvEncoder(nn.Module):
    """Two convolutions applied to each year independently."""

    def __init__(self, in_channels: int, hidden: int, kernel: int, dropout: float):
        super().__init__()
        pad = kernel // 2
        self.net = nn.Sequential(
            nn.Conv2d(in_channels, hidden, kernel, padding=pad),
            nn.ReLU(),
            nn.Dropout2d(dropout),
            nn.Conv2d(hidden, hidden, kernel, padding=pad),
            nn.ReLU(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # [T, C, H, W] -> [T, F, H, W]
        return self.net(x)


class CellRecurrence(nn.Module):
    """One LSTM sequence per cell over the ordered years."""

    def __init__(self, hidden: int):
        super().__init__()
        self.lstm = nn.LSTM(hidden, hidden, batch_first=True)

    def forward(self, z: torch.Tensor) -> torch.Tensor:  # [T, F, H, W] -> [T, F, H, W]
        T, F, H, W = z.shape
        seq = z.permute(2, 3, 0, 1).reshape(H * W, T, F)
        seq, _ = self.lstm(seq)
        return seq.reshape(H, W, T, F).permute(2, 3, 0, 1)


class ConvLSTMCell(nn.Module):
    """ConvLSTM cell (Shi et al., 2015): gates computed with convolutions."""

    def __init__(self, in_channels: int, hidden: int, kernel: int = 3):
        super().__init__()
        self.hidden = hidden
        self.gates = nn.Conv2d(in_channels + hidden, 4 * hidden, kernel, padding=kernel // 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # [T, C, H, W] -> [T, F, H, W]
        T, _, H, W = x.shape
        h = x.new_zeros(1, self.hidden, H, W)
        c = x.new_zeros(1, self.hidden, H, W)
        outputs = []
        for t in range(T):
            i, f, o, g = self.gates(torch.cat([x[t : t + 1], h], dim=1)).chunk(4, dim=1)
            c = torch.sigmoid(f) * c + torch.sigmoid(i) * torch.tanh(g)
            h = torch.sigmoid(o) * torch.tanh(c)
            outputs.append(h)
        return torch.cat(outputs, dim=0)


def build_encoder(
    variant: str, in_channels: int, hidden: int, dropout: float
) -> tuple[nn.Module, int]:
    """Return the encoder of a variant and its output feature size."""
    if variant == "cnn_lstm":
        return nn.Sequential(
            ConvEncoder(in_channels, hidden, 3, dropout), CellRecurrence(hidden)
        ), hidden
    if variant == "cnn_only":
        return ConvEncoder(in_channels, hidden, 3, dropout), hidden
    if variant == "lstm_only":
        return nn.Sequential(
            ConvEncoder(in_channels, hidden, 1, dropout), CellRecurrence(hidden)
        ), hidden
    if variant == "convlstm":
        return ConvLSTMCell(in_channels, hidden), hidden
    if variant == "poisson_glm":
        return nn.Identity(), in_channels
    raise ValueError(f"unknown variant {variant}")


# --------------------------------------------------------------------------- model
class SpatioTemporalModel(nn.Module):
    """Encoder + shared linear head + per-source reporting factors."""

    def __init__(
        self,
        in_channels: int,
        subperiods: int,
        families: int,
        hidden: int = 32,
        dropout: float = 0.2,
        variant: str = "cnn_lstm",
    ) -> None:
        super().__init__()
        self.variant = variant
        self.encoder, features = build_encoder(variant, in_channels, hidden, dropout)
        self.head = nn.Conv2d(features, subperiods, kernel_size=1)
        nn.init.constant_(self.head.bias, -4.0)  # start near the sparse observed rate
        # log reporting factor of each family; index 0 (police census) is the
        # reference scale and is held at 0 by ``reporting_factors``.
        self.log_report = nn.Parameter(torch.zeros(families))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.encoder(x))  # [T, K, H, W]

    def reporting_factors(self) -> torch.Tensor:
        """log rho per family with the reference family fixed to 0 (identifiability)."""
        mask = torch.ones_like(self.log_report)
        mask[0] = 0
        return self.log_report * mask


def expected_observations(
    log_lambda: torch.Tensor,
    log_report: torch.Tensor,
    cover: torch.Tensor,
    located: torch.Tensor,
    frac: torch.Tensor,
    valid: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Map the latent intensity to each family's observable counts.

    Returns ``mu_cell`` [S, T, K, H, W] (events located to cells) and
    ``mu_dist`` [S, T, K, D] (events located only to a district), splitting
    each family-year by its located share (Poisson thinning).
    """
    lam = torch.exp(log_lambda) * valid  # [T, K, H, W]
    scale = torch.exp(log_report)[:, None, None] * cover  # [S, T, K]
    mu_cell = lam[None] * (scale * located[:, :, None])[..., None, None]
    district_lam = torch.einsum("tkhw,dhw->tkd", lam, frac)  # [T, K, D]
    mu_dist = district_lam[None] * (scale * (1 - located[:, :, None]))[..., None]
    return mu_cell, mu_dist
