"""Causality and source-boundary checks for the isolated performance experiment."""

from types import SimpleNamespace

import numpy as np
import torch

from ml.experiments.performance import Candidate, add_band_history, historical_prior


def tiny():
    return SimpleNamespace(
        X=np.zeros((3, 2, 1, 2), np.float32),
        channels=["a", "b"],
        y_cell=np.zeros((2, 3, 2, 1, 2), np.float32),
        y_dist=np.zeros((2, 3, 2, 1), np.float32),
        events_total=np.zeros((2, 3, 2, 1), np.float32),
        frac=np.ones((1, 1, 2), np.float32),
        area_km2=np.ones((1, 2), np.float32),
        valid=np.ones((1, 2), bool),
        cover=np.ones((2, 3, 2), np.float32),
        located=np.ones((2, 3), np.float32),
    )


def test_prior_uses_only_past_all_severity():
    t = tiny()
    before = historical_prior(t)
    t.y_cell[1] += 100
    t.y_dist[1] += 100
    np.testing.assert_array_equal(historical_prior(t), before)
    t.y_cell[0, 2] += 100
    np.testing.assert_array_equal(historical_prior(t), before)
    t.y_cell[0, 0, 0, 0, 0] = 2
    t.y_dist[0, 0, 0, 0] = 4
    after = historical_prior(t)
    np.testing.assert_array_equal(after[0], before[0])
    np.testing.assert_allclose(after[1, 0].sum(), 6.004, rtol=1e-6)


def test_band_history_causal_and_source_separated():
    t = tiny()
    t.y_cell[0, 0, 0, 0, 0] = 2
    t.y_cell[1, 1, 1, 0, 1] = 3
    t.cover[1, 0] = 0
    add_band_history(t)
    assert t.X.shape == (3, 10, 1, 2)
    assert np.all(t.X[0, 2:] == 0)
    assert t.X[1, 2, 0, 0] == np.log1p(np.float32(2))
    assert np.all(t.X[1, 6:] == 0)
    assert t.X[2, 7, 0, 1] == np.log1p(np.float32(3))


def test_candidate_residual_positive_and_gradient():
    t = tiny()
    model = Candidate(t, True).eval()
    x = torch.from_numpy(t.X)
    expected = historical_prior(t)
    np.testing.assert_allclose(model(x).detach().exp().numpy(), expected, rtol=1e-5)
    model.train()
    loss = model(x).square().mean()
    loss.backward()
    assert torch.isfinite(model.head.weight.grad).all()


def test_negative_binomial_matches_torch_distribution():
    from ml.experiments.negative_binomial import nb_nll

    y = torch.tensor([0.0, 1.0, 4.0, 12.0])
    mu = torch.tensor([0.01, 0.4, 3.0, 8.0], requires_grad=True)
    alpha = 0.3
    r = 1 / alpha
    reference = torch.distributions.NegativeBinomial(total_count=r, probs=mu / (mu + r))
    actual = nb_nll(y, mu, alpha)
    torch.testing.assert_close(actual + torch.lgamma(y + 1), -reference.log_prob(y))
    actual.sum().backward()
    assert torch.isfinite(mu.grad).all()


def test_negative_binomial_poisson_limit():
    from ml.experiments.negative_binomial import nb_nll

    y = torch.tensor([0.0, 2.0, 7.0])
    mu = torch.tensor([0.01, 1.5, 6.0])
    torch.testing.assert_close(nb_nll(y, mu, 0.0), mu - y * torch.log(mu + 1e-8))
