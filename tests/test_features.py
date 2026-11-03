"""Point-in-time features: what a lot published on day t sees is only what was known on day t."""

import datetime as dt

import numpy as np

from tmr.features.state import FEATURES, FeatureState

START = dt.date(2025, 1, 6)
F = {n: i for i, n in enumerate(FEATURES)}


def _firms():
    return [
        {
            "firm_id": i,
            "city": "Berlin",
            "lat": 52.5,
            "lon": 13.4 + i * 0.1,
            "trades": ["maler", "putz"],
            "radius_km": 80,
            "size": "small",
            "joined": "2024-01-01",
            "left": None,
        }
        for i in range(3)
    ]


def _lot(i, day, deadline_days=14, label="maler"):
    d = START + dt.timedelta(days=day)
    return {
        "lot_id": i,
        "buyer_id": 1,
        "published": d.isoformat(),
        "deadline": (d + dt.timedelta(days=deadline_days)).isoformat(),
        "lat": 52.5,
        "lon": 13.4,
        "trade_label": label,
        "title": "Maler",
        "text": "",
        "reference_eur": 50000.0,
    }


def _rows(lot, bid_firm=0):
    return [
        {
            "firm_id": f,
            "position": f,
            "invited": True,
            "bid": f == bid_firm,
            "price_ratio": 1.0 if f == bid_firm else None,
            "awarded": f == bid_firm,
        }
        for f in range(3)
    ]


def test_bids_count_only_after_the_deadline_and_invitations_at_once():
    s = FeatureState(_firms(), START)
    probs = np.zeros(len(s.trades), dtype=np.float32)
    lot = _lot(0, 10)
    s.record(lot, _rows(lot))
    X = s.features(_lot(1, 12), np.array([0, 1, 2]), probs)
    assert X[0, F["invites_14"]] == 1 and X[0, F["bids_365"]] == 0  # deadline (day 24) not reached
    X = s.features(_lot(2, 30), np.array([0, 1, 2]), probs)
    assert X[0, F["bids_365"]] == 1 and X[1, F["bids_365"]] == 0
    assert X[0, F["invites_14"]] == 0  # the invitation on day 10 is older than 14 days


def test_incremental_state_equals_a_rebuild_from_earlier_events_only():
    """The pipelines process lots in time order; at each lot the state must equal one rebuilt from scratch
    from the events before it (a brute-force recomputation)."""
    rng = np.random.default_rng(1)
    lots = [_lot(i, int(d)) for i, d in enumerate(sorted(rng.integers(0, 200, 40)))]
    rows = {lot["lot_id"]: _rows(lot, bid_firm=int(rng.integers(0, 3))) for lot in lots}
    probs = np.zeros(len(FeatureState(_firms(), START).trades), dtype=np.float32)
    s = FeatureState(_firms(), START)
    for lot in lots:
        got = s.features(lot, np.array([0, 1, 2]), probs)
        fresh = FeatureState(_firms(), START)
        for earlier in lots:
            if earlier["published"] < lot["published"]:
                fresh.record(earlier, rows[earlier["lot_id"]])
        want = fresh.features(lot, np.array([0, 1, 2]), probs)
        same_day = [x for x in lots if x["published"] == lot["published"] and x["lot_id"] < lot["lot_id"]]
        if not same_day:  # lots on the same day see each other's invitations in the live order, not in a rebuild
            assert np.allclose(got, want), lot
        s.record(lot, rows[lot["lot_id"]])


def test_trade_fit_uses_the_profile_and_the_reader():
    s = FeatureState(_firms(), START)
    p = np.zeros(len(s.trades), dtype=np.float32)
    p[s.t_index["maler"]] = 0.6
    p[s.t_index["elektro"]] = 0.4
    X = s.features(_lot(0, 3), np.array([0]), p)
    assert abs(X[0, F["trade_fit"]] - 0.6) < 1e-6 and abs(X[0, F["trade_fit_first"]] - 0.6) < 1e-6
