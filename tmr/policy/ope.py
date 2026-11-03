"""Off-policy evaluation of a ranking from logs alone (position-based model).

A logged lot has a shortlist in some order and outcomes y (competitive bids). A new policy would show a
different order. Under the position-based model a firm's outcome is examination(position) x relevance, so:

- IPS: reweight each logged firm by exam(new position) / exam(logged position); firms the new policy shows
  but the log never showed count zero (the estimate is biased low when support is missing);
- DR: a direct model m(x, position) for every firm the new policy shows, plus the IPS-weighted residual of
  the model on the firms that were logged;
- naive: NDCG of the new order against the logged labels, the number a team would look at first.
"""

from __future__ import annotations

import numpy as np


def ips(new_pos: dict[int, int], logged: list[tuple[int, int, float]], exam: np.ndarray) -> float:
    return float(sum(exam[new_pos[f]] / exam[p] * y for f, p, y in logged if f in new_pos))


def dr(
    new_pos: dict[int, int],
    logged: list[tuple[int, int, float]],
    exam: np.ndarray,
    m_new: dict[int, float],
    m_logged: dict[int, float],
) -> float:
    v = sum(m_new.values())
    for f, p, y in logged:
        if f in new_pos:
            v += exam[new_pos[f]] / exam[p] * (y - m_logged[f])
    return float(v)


def ndcg(order: list[int], gains: dict[int, float], k: int) -> float:
    dcg = sum(gains.get(f, 0.0) / np.log2(i + 2) for i, f in enumerate(order[:k]))
    ideal = sorted(gains.values(), reverse=True)[:k]
    idcg = sum(g / np.log2(i + 2) for i, g in enumerate(ideal))
    return float(dcg / idcg) if idcg > 0 else 0.0


def paired_ci(a: np.ndarray, b: np.ndarray, n_boot: int = 2000, seed: int = 3) -> tuple[float, float, float]:
    """Mean of a - b per lot, with a 95 % bootstrap interval over lots."""
    d = np.asarray(a) - np.asarray(b)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), (n_boot, len(d)))
    boots = d[idx].mean(1)
    return float(d.mean()), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))
