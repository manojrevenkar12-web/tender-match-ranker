import numpy as np

from tmr.monitor.checks import ece, psi


def test_psi_is_small_for_the_same_distribution_and_large_for_a_shift():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, 5000)
    assert psi(a, rng.normal(0, 1, 5000)) < 0.02
    assert psi(a, rng.normal(1.0, 1, 5000)) > 0.2


def test_ece():
    p = np.full(1000, 0.3)
    y = np.r_[np.ones(300), np.zeros(700)]
    assert ece(p, y) < 1e-9
    assert abs(ece(p, np.r_[np.ones(500), np.zeros(500)]) - 0.2) < 1e-9
