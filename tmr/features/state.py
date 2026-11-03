"""One definition of every feature, used for training, offline evaluation, the market replay and serving.

The state is built only from what the platform logs: firm profiles, lots, shortlists, invitations, and
bids once a lot's deadline has passed. A feature for a lot published on day t uses only events known on
day t (point-in-time); tests/test_features.py checks it against a brute-force recomputation.
"""

from __future__ import annotations

import bisect
import datetime as dt
import heapq
import math
from collections import deque
from typing import Any

import numpy as np

from .. import config
from ..geo import km

FEATURES = [
    "dist_km",
    "dist_over_radius",
    "trade_fit",
    "trade_fit_first",
    "label_in_profile",
    "n_profile_trades",
    "size_fit",
    "log_volume",
    "lead_days",
    "december",
    "invites_365",
    "bids_365",
    "bid_rate",
    "comp_rate",
    "awards_365",
    "trade_bids_365",
    "log_age_days",
    "is_new",
    "load_14",
    "invites_14",
    "buyer_invites",
    "buyer_bids",
    "buyer_awards",
    "price_med_trade",
    "price_n_trade",
]
SIZE_RANGE = {"small": (10_000, 250_000), "medium": (60_000, 1_500_000), "large": (300_000, 12_000_000)}


class FeatureState:
    def __init__(self, firms: list[dict[str, Any]], start: dt.date) -> None:
        cfg = config.load("models")["features"]
        self.window = int(cfg["history_days"])
        self.prior_n, self.prior_rate = float(cfg["prior_bids"]), float(cfg["prior_rate"])
        self.start = start
        self.trades = config.trades()
        self.t_index = {t: i for i, t in enumerate(self.trades)}
        self.firms = firms
        n = len(firms)
        self.lat = np.array([f["lat"] for f in firms])
        self.lon = np.array([f["lon"] for f in firms])
        self.radius = np.array([float(f["radius_km"]) for f in firms])
        self.joined = np.array([(dt.date.fromisoformat(f["joined"]) - start).days for f in firms])
        self.left = np.array([(dt.date.fromisoformat(f["left"]) - start).days if f["left"] else 10**6 for f in firms])
        self.profile = np.zeros((n, len(self.trades)), dtype=np.float32)
        self.first = np.zeros((n, len(self.trades)), dtype=np.float32)
        for i, f in enumerate(firms):
            for k, t in enumerate(f["trades"]):
                self.profile[i, self.t_index[t]] = 1.0
                if k == 0:
                    self.first[i, self.t_index[t]] = 1.0
        self.n_trades = self.profile.sum(1)
        self.size_lo = np.array([SIZE_RANGE[f["size"]][0] for f in firms], dtype=float)
        self.size_hi = np.array([SIZE_RANGE[f["size"]][1] for f in firms], dtype=float)
        # events
        self.invites: list[list[int]] = [[] for _ in range(n)]  # invitation days, sorted
        self.bids: list[deque] = [deque() for _ in range(n)]  # (day known, competitive, awarded, label, ratio)
        self.buyer: dict[tuple[int, int], list[int]] = {}
        self.pending: list[tuple[int, int, list[dict[str, Any]], dict[str, Any]]] = []  # (deadline, seq, rows, lot)
        self._seq = 0
        self.new_max = int(config.load("ranking")["exploration"]["new_firm_max_invites"])
        self.competitive = 1.0 + float(config.load("ranking")["competitive_within"])

    # ---- events ------------------------------------------------------------------------------------------
    def day(self, d: str | dt.date) -> int:
        d = dt.date.fromisoformat(d) if isinstance(d, str) else d
        return (d - self.start).days

    def record(self, lot: dict[str, Any], rows: list[dict[str, Any]]) -> None:
        """A served lot: invitations count now, bids once the deadline has passed."""
        day = self.day(lot["published"])
        for r in rows:
            if r["invited"]:
                bisect.insort(self.invites[r["firm_id"]], day)
                self.buyer.setdefault((lot["buyer_id"], r["firm_id"]), [0, 0, 0])[0] += 1
        self._seq += 1
        heapq.heappush(self.pending, (self.day(lot["deadline"]), self._seq, rows, lot))

    def advance(self, day: int) -> None:
        while self.pending and self.pending[0][0] <= day:
            dday, _, rows, lot = heapq.heappop(self.pending)
            for r in rows:
                if r["bid"]:
                    comp = r["price_ratio"] is not None and r["price_ratio"] <= self.competitive
                    self.bids[r["firm_id"]].append((dday, comp, r["awarded"], lot["trade_label"], r["price_ratio"]))
                    b = self.buyer.setdefault((lot["buyer_id"], r["firm_id"]), [0, 0, 0])
                    b[1] += 1
                    b[2] += int(r["awarded"])

    # ---- queries -----------------------------------------------------------------------------------------
    def active(self, day: int) -> np.ndarray:
        return (self.joined <= day) & (self.left > day)

    def candidates(self, lot: dict[str, Any], trade_probs: np.ndarray) -> np.ndarray:
        cfg = config.load("ranking")["candidates"]
        day = self.day(lot["published"])
        want = trade_probs >= cfg["trade_min_prob"]
        want[self.t_index[lot["trade_label"]]] = True
        has = (self.profile[:, want].sum(1) > 0) & self.active(day)
        d = km(lot["lat"], lot["lon"], self.lat, self.lon)
        ok = np.where(has & (d <= self.radius * cfg["radius_slack"]))[0]
        if len(ok) > cfg["max_candidates"]:
            ok = ok[np.argsort(d[ok], kind="stable")[: cfg["max_candidates"]]]
        return np.sort(ok)

    def features(self, lot: dict[str, Any], ids: np.ndarray, trade_probs: np.ndarray) -> np.ndarray:
        day = self.day(lot["published"])
        self.advance(day)
        n = len(ids)
        X = np.zeros((n, len(FEATURES)), dtype=np.float32)
        d = km(lot["lat"], lot["lon"], self.lat[ids], self.lon[ids])
        label = self.t_index[lot["trade_label"]]
        vol = max(1.0, float(lot["reference_eur"]))
        lead = (dt.date.fromisoformat(lot["deadline"]) - dt.date.fromisoformat(lot["published"])).days
        X[:, 0] = d
        X[:, 1] = d / np.maximum(self.radius[ids], 1)
        X[:, 2] = self.profile[ids] @ trade_probs
        X[:, 3] = self.first[ids] @ trade_probs
        X[:, 4] = self.profile[ids, label]
        X[:, 5] = self.n_trades[ids]
        lo, hi = self.size_lo[ids], self.size_hi[ids]
        X[:, 6] = np.where(vol < lo, np.log(vol / lo), np.where(vol > hi, np.log(hi / vol), 0.0))
        X[:, 7] = math.log(vol)
        X[:, 8] = lead
        X[:, 9] = float(dt.date.fromisoformat(lot["published"]).month == 12)
        lo_day = day - self.window
        for k, f in enumerate(ids):
            inv = self.invites[f]
            a = bisect.bisect_left(inv, lo_day)
            b = bisect.bisect_left(inv, day)
            invites_365 = b - a
            invites_14 = b - bisect.bisect_left(inv, day - 14)
            bq = self.bids[f]
            while bq and bq[0][0] < lo_day:
                bq.popleft()
            nb = len(bq)
            comp = sum(1 for x in bq if x[1])
            awards = sum(1 for x in bq if x[2])
            tb = [x[4] for x in bq if x[3] == lot["trade_label"]]
            X[k, 10] = invites_365
            X[k, 11] = nb
            X[k, 12] = (nb + self.prior_n * self.prior_rate) / (invites_365 + self.prior_n)
            X[k, 13] = (comp + 1.0) / (nb + 2.0)
            X[k, 14] = awards
            X[k, 15] = len(tb)
            age = max(1, day - self.joined[f])
            X[k, 16] = math.log(age)
            X[k, 17] = float(invites_365 < self.new_max)
            monthly_bids = max(1.0, nb / 12.0)
            X[k, 18] = invites_14 / (monthly_bids * 14 / 30 * 2.5)
            X[k, 19] = invites_14
            bb = self.buyer.get((lot["buyer_id"], int(f)))
            if bb:
                X[k, 20:23] = bb
            X[k, 23] = float(np.median(tb)) if tb else 1.0
            X[k, 24] = len(tb)
        return X
