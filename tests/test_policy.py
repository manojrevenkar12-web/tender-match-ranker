import datetime as dt

import numpy as np

from tmr.features.state import FEATURES, FeatureState
from tmr.policy.policies import Model, Rules

F = {n: i for i, n in enumerate(FEATURES)}
START = dt.date(2025, 1, 6)


class Const:
    name = "const"

    def __init__(self, s):
        self.s = s

    def score(self, X):
        return self.s[: len(X)]


def _lot():
    return {
        "lot_id": 7,
        "buyer_id": 1,
        "published": "2025-03-03",
        "deadline": "2025-03-20",
        "lat": 52.5,
        "lon": 13.4,
        "trade_label": "maler",
        "title": "",
        "text": "",
        "reference_eur": 50000.0,
    }


def test_fatigue_demotes_a_firm_that_was_asked_too_often():
    m = Model("m", Const(np.array([1.0, 0.9])), None, 0.0, fatigue=True, new_slots=False)
    X = np.zeros((2, len(FEATURES)), dtype=np.float32)
    X[0, F["load_14"]] = 4.0  # the better firm is flooded with invitations
    ranked, _ = m.order(_lot(), np.array([10, 11]), X)
    assert list(ranked) == [11, 10]
    m.fatigue = False
    ranked, _ = m.order(_lot(), np.array([10, 11]), X)
    assert list(ranked) == [10, 11]


def test_new_firms_get_the_last_places_of_the_shortlist():
    n = 30
    m = Model("m", Const(np.linspace(1, 0, n)), None, 0.0, fatigue=False, new_slots=True)
    X = np.zeros((n, len(FEATURES)), dtype=np.float32)
    X[25, F["is_new"]] = 1
    X[28, F["is_new"]] = 1
    ranked, _ = m.order(_lot(), np.arange(n), X)
    assert list(ranked[:18]) == list(range(18)) and set(ranked[18:20]) == {25, 28}


def test_a_shuffled_lot_shows_the_same_firms_in_another_order():
    firms = [
        {
            "firm_id": i,
            "city": "Berlin",
            "lat": 52.5,
            "lon": 13.4 + i * 0.01,
            "trades": ["maler"],
            "radius_km": 100,
            "size": "small",
            "joined": "2024-01-01",
            "left": None,
        }
        for i in range(25)
    ]
    s = FeatureState(firms, START)
    a = Rules(shuffle_share=0.0).serve(_lot(), s)
    b = Rules(shuffle_share=1.0).serve(_lot(), s)
    assert b.randomised and not a.randomised and sorted(a.shortlist) == sorted(b.shortlist)
    assert a.shortlist[:3] == [0, 1, 2]  # nearest first when nobody has history
