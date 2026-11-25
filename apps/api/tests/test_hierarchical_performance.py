from types import SimpleNamespace

import numpy as np
import torch

from ml.experiments.hierarchical import Hierarchical, predictions
from ml.experiments.quality_aware import history_features, quality_loss
from ml.fused.model import SpatioTemporalModel
from ml.fused.train import poisson_nll, to_torch


def tiny():
    return SimpleNamespace(
        years=[2014, 2015, 2016],
        X=np.zeros((3, 2, 1, 2), np.float32),
        channels=["a", "b"],
        y_cell=np.zeros((2, 3, 2, 1, 2), np.float32),
        y_dist=np.zeros((2, 3, 2, 2), np.float32),
        events_total=np.zeros((2, 3, 2, 2), np.float32),
        frac=np.array([[[1, 0]], [[0, 1]]], np.float32),
        area_km2=np.ones((1, 2), np.float32),
        valid=np.ones((1, 2), bool),
        cover=np.ones((2, 3, 2), np.float32),
        located=np.full((2, 3), 0.5, np.float32),
    )


def test_hierarchical_observations_are_conserved_and_bounded():
    t = tiny()
    m = Hierarchical(t, "H3")
    d = to_torch(t)
    lam, rho, full, cell, district = predictions(m, d)
    assert torch.equal(rho[0], torch.ones_like(rho[0]))
    assert (rho[1] > 0).all() and (rho[1] < 1).all()
    torch.testing.assert_close(cell.sum((-1, -2)) + district.sum(-1), full.sum(-1))
    assert (lam > 0).all()


def test_quality_loss_weight_one_matches_original():
    t = tiny()
    t.y_cell[0, 1, 0, 0, 0] = 1
    t.y_dist[0, 0, 0, 0] = 3
    d = to_torch(t)
    model = SpatioTemporalModel(2, 2, 2, hidden=4, variant="convlstm").eval()
    mask = torch.ones((2, 3))
    flags = torch.tensor([True, False, False])
    torch.testing.assert_close(
        quality_loss(model, d, mask, flags, 1.0), poisson_nll(model, d, mask)
    )


def test_proxy_city_loss_ignores_station_redistribution():
    t = tiny()
    t.y_dist[0, 0, 0, 0] = 4
    d = to_torch(t)
    model = SpatioTemporalModel(2, 2, 2, hidden=4, variant="convlstm").eval()
    mask = torch.ones((2, 3))
    flags = torch.tensor([True, False, False])
    a = quality_loss(model, d, mask, flags, 0.0)
    d["y_dist"][0, 0, 0] = torch.tensor([0.0, 4.0])
    b = quality_loss(model, d, mask, flags, 0.0)
    torch.testing.assert_close(a, b)


def test_history_is_causal_and_ignores_proxy_locations():
    t = tiny()
    flags = np.array([True, False, False])
    t.events_total[0, 0, 0, 0] = 100
    t.events_total[0, 1, 0, 1] = 4
    t.y_cell[0, 1, 0, 0, 1] = 2
    history_features(t, flags)
    assert np.all(t.X[0, 2:] == 0)
    assert np.all(t.X[1, 2:7] == 0)
    assert t.X[2, 2, 0, 1] > 0
    assert t.X[2, 4, 0, 0] == 0
    assert t.X[2, 4, 0, 1] > 0
