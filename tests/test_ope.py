"""Off-policy estimators on a small position-based world where the truth is known exactly."""

import numpy as np

from tmr.policy import ope


def _world(seed=0, n_lots=4000, n=12):
    rng = np.random.default_rng(seed)
    exam = 1 / (1 + np.arange(n)) ** 0.5
    rel = rng.beta(1, 4, (n_lots, n))  # relevance of firm j on lot i
    log_score = rel + rng.normal(0, 0.15, rel.shape)  # the logging policy is good but noisy
    return rng, exam, rel, log_score


def test_ips_is_unbiased_with_full_support():
    rng, exam, rel, log_score = _world()
    k = rel.shape[1]
    ips, dr, truth = [], [], []
    for i in range(len(rel)):
        log_order = np.argsort(-log_score[i])
        new_order = np.argsort(-rel[i])  # the new policy ranks by true relevance
        y = rng.random(k) < exam[np.argsort(log_order)] * rel[i]  # outcome at the logged position
        logged = [(int(f), int(p), float(y[f])) for p, f in enumerate(log_order)]
        new_pos = {int(f): p for p, f in enumerate(new_order)}
        ips.append(ope.ips(new_pos, logged, exam))
        m_new = {int(f): exam[p] * rel[i, f] for p, f in enumerate(new_order)}
        m_log = {int(f): exam[p] * rel[i, f] for p, f in enumerate(log_order)}
        dr.append(ope.dr(new_pos, logged, exam, m_new, m_log))
        truth.append(sum(exam[p] * rel[i, f] for p, f in enumerate(new_order)))
    t = np.mean(truth)
    assert abs(np.mean(ips) - t) / t < 0.03
    # with every firm logged at some position, DR's model terms cancel and it equals IPS exactly;
    # it differs only where the log has no support (next test)
    assert np.allclose(ips, dr)


def test_ips_misses_firms_the_log_never_showed():
    exam = np.array([1.0, 0.7, 0.5])
    logged = [(1, 0, 1.0), (2, 1, 0.0), (3, 2, 0.0)]
    # the new policy puts an unseen firm first: IPS cannot credit it, DR can through the model
    new_pos = {9: 0, 1: 1, 2: 2}
    assert ope.ips(new_pos, logged, exam) == 0.7
    assert ope.dr(new_pos, logged, exam, {9: 0.4, 1: 0.35, 2: 0.1}, {1: 0.5, 2: 0.1, 3: 0.1}) > 0.7


def test_ndcg_and_paired_interval():
    assert ope.ndcg([1, 2, 3], {1: 3.0, 2: 1.0}, 3) == 1.0
    assert ope.ndcg([3, 2, 1], {1: 3.0, 2: 1.0}, 3) < 1.0
    mean, lo, hi = ope.paired_ci(np.ones(200) * 2, np.ones(200))
    assert mean == 1.0 and lo == 1.0 and hi == 1.0
