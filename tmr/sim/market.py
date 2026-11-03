"""The simulated market: firms, buyers, lots, and how buyers invite and firms bid.

Only tmr.sim and tmr.evaluate may import this. The platform sees what a real platform sees: public firm
profiles (what firms *say* about their trades and radius), lots as buyers file them, and the logged
shortlist, invitations, bids and awards.
"""

from __future__ import annotations

import bisect
import datetime as dt
import math
import random
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .. import config
from ..geo import km
from .text import lot_text

UINT64 = np.uint64


@cache
def world_config() -> dict[str, Any]:
    with open(config.ROOT / "config" / "world.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _mix(*keys: Any) -> np.ndarray:
    """splitmix64 over integer keys (arrays broadcast): reproducible uniforms in [0, 1)."""
    x = np.zeros(np.broadcast(*[np.asarray(k) for k in keys]).shape, dtype=UINT64)
    with np.errstate(over="ignore"):
        for k in keys:
            x = x ^ (np.asarray(k).astype(UINT64) + UINT64(0x9E3779B97F4A7C15))
            x = (x ^ (x >> UINT64(30))) * UINT64(0xBF58476D1CE4E5B9)
            x = (x ^ (x >> UINT64(27))) * UINT64(0x94D049BB133111EB)
            x = x ^ (x >> UINT64(31))
    return (x >> UINT64(11)).astype(np.float64) / float(1 << 53)


def _normal(u: np.ndarray) -> np.ndarray:
    from scipy.special import ndtri

    return ndtri(np.clip(u, 1e-12, 1 - 1e-12))


def sigmoid(x):  # noqa: ANN001, ANN201
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class Firm:
    idx: int
    city: str
    lat: float
    lon: float
    primary: str
    secondary: list[str]
    radius: float  # true
    size: str
    vol_lo: float
    vol_hi: float
    capacity: float  # bids a month it can produce
    price_level: float
    responsiveness: float
    joined: dt.date
    left: dt.date | None
    # what the firm says in its profile
    stated_trades: list[str]
    stated_radius: float


@dataclass
class Buyer:
    idx: int
    city: str
    lat: float
    lon: float
    style: str
    known: set[int] = field(default_factory=set)
    mislabels: bool = False


@dataclass
class Lot:
    idx: int
    tender: int
    buyer: int
    published: dt.date
    deadline: dt.date
    city: str
    lat: float
    lon: float
    trade: str  # true
    label: str  # as the buyer filed it
    title: str
    text: str
    volume: float  # true market value
    reference: float  # the platform's own estimate of it

    def public(self) -> dict[str, Any]:
        return {
            "lot_id": self.idx,
            "tender_id": self.tender,
            "buyer_id": self.buyer,
            "published": self.published.isoformat(),
            "deadline": self.deadline.isoformat(),
            "city": self.city,
            "lat": self.lat,
            "lon": self.lon,
            "trade_label": self.label,
            "title": self.title,
            "text": self.text,
            "reference_eur": round(self.reference, 2),
        }


class Market:
    """A world of firms, buyers and the lot stream, plus the market state (who was asked when)."""

    def __init__(self, profile: str = "full", seed: int | None = None) -> None:
        cfg = world_config()
        self.cfg = cfg
        self.profile = cfg["profiles"][profile]
        self.seed = seed if seed is not None else cfg["seed"]
        self.rng = random.Random(self.seed)
        self.start = dt.date.fromisoformat(cfg["start"])
        self.cities = cfg["cities"]
        self.trades = config.trades()
        self._firms()
        self._buyers()
        self._lots()
        # state
        self.invite_times: list[list[int]] = [[] for _ in self.firms]  # day numbers
        self.log: list[dict[str, Any]] = []

    # ---- world --------------------------------------------------------------------------------------------
    def _city(self) -> str:
        names = list(self.cities)
        return self.rng.choices(names, weights=[self.cities[c][2] for c in names])[0]

    def _firms(self) -> None:
        c, r = self.cfg["subcontractor"], self.rng
        months = self.profile["months"]
        tw = self.cfg["trade_weights"]
        self.firms: list[Firm] = []
        for i in range(self.profile["subcontractors"]):
            city = self._city()
            lat, lon = self.cities[city][0] + r.gauss(0, 0.12), self.cities[city][1] + r.gauss(0, 0.18)
            primary = r.choices(self.trades, weights=[tw[t] for t in self.trades])[0]
            sec: list[str] = []
            nb = self.cfg["neighbours"].get(primary, [])
            u = r.random()
            if nb and u < c["secondary_trades"][0] + c["secondary_trades"][1]:
                sec = r.sample(nb, min(len(nb), 2 if u < c["secondary_trades"][1] else 1))
            size = r.choices(list(c["size_mix"]), weights=list(c["size_mix"].values()))[0]
            lo, hi = c["size_volume_eur"][size]
            bl, bh = c["bids_per_month"][size]
            radius = r.uniform(*c["radius_km"]) * {"small": 0.7, "medium": 1.0, "large": 1.5}[size]
            new = r.random() < c["new_firms_share"]
            joined = (
                self.start + dt.timedelta(days=r.randint(30, 30 * months - 20))
                if new
                else self.start - dt.timedelta(days=r.randint(60, 3000))
            )
            left = None
            if r.random() < c["churn_per_month"] * months:
                left = max(joined, self.start) + dt.timedelta(days=r.randint(30, 30 * months))
            stated = [primary, *sec]
            if r.random() < 0.3:  # profiles overstate
                stated.append(r.choice([t for t in self.trades if t not in stated]))
            self.firms.append(
                Firm(
                    i,
                    city,
                    lat,
                    lon,
                    primary,
                    sec,
                    radius,
                    size,
                    lo * r.uniform(0.6, 1.4),
                    hi * r.uniform(0.6, 1.4),
                    r.uniform(bl, bh),
                    math.exp(r.gauss(0, c["price_level_sigma"])),
                    r.gauss(*c["responsiveness"]),
                    joined,
                    left,
                    stated,
                    round(radius * r.uniform(0.8, 1.6) / 5) * 5,
                )
            )
        self.f_lat = np.array([f.lat for f in self.firms])
        self.f_lon = np.array([f.lon for f in self.firms])

    def _buyers(self) -> None:
        r, g = self.rng, self.cfg["gc"]
        self.buyers = []
        for i in range(self.profile["gcs"]):
            city = self._city()
            self.buyers.append(
                Buyer(
                    i,
                    city,
                    self.cities[city][0],
                    self.cities[city][1],
                    r.choice(["terse", "normal", "normal", "long"]),
                    mislabels=r.random() < g["wrong_trade_label"] * 4,
                )
            )
        d = km(
            self.f_lat[:, None],
            self.f_lon[:, None],
            np.array([b.lat for b in self.buyers])[None, :],
            np.array([b.lon for b in self.buyers])[None, :],
        )
        for j, b in enumerate(self.buyers):
            near = np.where(d[:, j] < 120)[0]
            k = int(len(near) * g["relationship_share"])
            b.known = set(r.sample(list(near), k)) if k else set()

    def _lots(self) -> None:
        r, cfg = self.rng, self.cfg
        self.lots: list[Lot] = []
        tw = cfg["trade_weights"]
        n_months = self.profile["months"]
        tender = 0
        for m in range(n_months):
            for _ in range(self.profile["tenders_per_month"]):
                b = r.choice(self.buyers)
                day = self.start + dt.timedelta(days=30 * m + r.randint(0, 29))
                if day.weekday() >= 5:
                    day -= dt.timedelta(days=day.weekday() - 4)
                city = b.city if r.random() < 0.6 else self._city()
                lat, lon = self.cities[city][0] + r.gauss(0, 0.08), self.cities[city][1] + r.gauss(0, 0.1)
                n = r.choices([1, 2, 3, 4, 6], weights=[30, 25, 20, 15, 10])[0]
                trades = (
                    r.sample(self.trades, k=n)
                    if n > 1
                    else r.choices(self.trades, weights=[tw[t] for t in self.trades])
                )
                for k, t in enumerate(trades, start=1):
                    med, sig = cfg["lot_volume_eur"].get(t, cfg["lot_volume_eur"]["default"])
                    vol = med * math.exp(r.gauss(0, sig))
                    label = t
                    if b.mislabels and r.random() < 0.25:
                        label = r.choice(cfg["neighbours"].get(t) or self.trades)
                    title, text = lot_text(t, r, b.style, k)
                    lead = r.randint(7, 35)
                    self.lots.append(
                        Lot(
                            len(self.lots),
                            tender,
                            b.idx,
                            day,
                            day + dt.timedelta(days=lead),
                            city,
                            lat,
                            lon,
                            t,
                            label,
                            title,
                            text,
                            vol,
                            vol * math.exp(r.gauss(0, cfg["price"]["reference_error_sigma"])),
                        )
                    )
                tender += 1
        self.lots.sort(key=lambda lot: (lot.published, lot.idx))
        for i, lot in enumerate(self.lots):
            lot.idx = i
        self.n_months = n_months

    def day(self, d: dt.date) -> int:
        return (d - self.start).days

    def month_of(self, lot: Lot) -> int:
        return self.day(lot.published) // 30

    def active(self, d: dt.date) -> np.ndarray:
        return np.array([f.joined <= d and (f.left is None or f.left > d) for f in self.firms])

    def public_firms(self) -> list[dict[str, Any]]:
        return [
            {
                "firm_id": f.idx,
                "city": f.city,
                "lat": round(f.lat, 4),
                "lon": round(f.lon, 4),
                "trades": f.stated_trades,
                "radius_km": f.stated_radius,
                "size": f.size,
                "joined": f.joined.isoformat(),
                "left": f.left.isoformat() if f.left else None,
            }
            for f in self.firms
        ]

    # ---- the market's response ----------------------------------------------------------------------------
    def load(self, firm_ids: np.ndarray, day: int) -> np.ndarray:
        """Invitations in the 14 days before `day`, relative to what the firm can bid on."""
        out = np.empty(len(firm_ids))
        for k, f in enumerate(firm_ids):
            t = self.invite_times[f]
            recent = bisect.bisect_left(t, day) - bisect.bisect_left(t, day - 14)
            out[k] = recent / max(1.0, self.firms[f].capacity * (14 / 30) * 2.5)
        return out

    def p_bid(self, lot: Lot, firm_ids: np.ndarray, day: int | None = None) -> np.ndarray:
        """Truth: P(the firm bids | invited), given the market state now."""
        w = self.cfg["response"]
        fs = [self.firms[i] for i in firm_ids]
        d = km(lot.lat, lot.lon, self.f_lat[firm_ids], self.f_lon[firm_ids])
        radius = np.array([f.radius for f in fs])
        trade = np.array(
            [
                w["primary_trade"]
                if f.primary == lot.trade
                else w["secondary_trade"]
                if lot.trade in f.secondary
                else w["other_trade"]
                for f in fs
            ]
        )
        misfit = np.array([lot.volume < f.vol_lo * 0.5 or lot.volume > f.vol_hi * 1.5 for f in fs])
        day = self.day(lot.published) if day is None else day
        load = self.load(firm_ids, day)
        new = np.array([(lot.published - f.joined).days < 180 for f in fs])
        known = np.array([i in self.buyers[lot.buyer].known for i in firm_ids])
        lead = (lot.deadline - lot.published).days
        x = (
            w["intercept"]
            + np.array([f.responsiveness for f in fs])
            + trade
            + w["distance_per_100km"] * d / 100
            + w["beyond_radius"] * np.clip(d / radius - 1, 0, 3)
            + w["size_misfit"] * misfit
            + w["load_slope"] * np.clip(load - 0.5, 0, None)
            + (w["short_lead_penalty"] if lead < w["short_lead_days"] else 0.0)
            + (w["december"] if lot.published.month == 12 else 0.0)
            + self.cfg["gc"]["relationship_boost"] * known
            + 0.4 * new
        )
        return sigmoid(x)

    def p_attract(self, lot: Lot, firm_ids: np.ndarray) -> np.ndarray:
        """Truth: P(the buyer invites the firm | it looked at it)."""
        b = self.cfg["buyer"]
        known = np.array([i in self.buyers[lot.buyer].known for i in firm_ids], dtype=float)
        noise = _normal(_mix(self.seed, 11, lot.buyer, firm_ids)) * b["attractiveness_noise"]
        return sigmoid(b["attractiveness_base"] + b["relationship_pull"] * known + noise)

    def exam(self, positions: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.asarray(positions, dtype=float)) ** self.cfg["buyer"]["exam_decay"]

    def price_ratio(self, lot: Lot, firm_ids: np.ndarray, load: np.ndarray) -> np.ndarray:
        """Truth: a bid's price relative to the platform's reference price for the lot."""
        p = self.cfg["price"]
        fs = [self.firms[i] for i in firm_ids]
        d = km(lot.lat, lot.lon, self.f_lat[firm_ids], self.f_lon[firm_ids])
        noise = _normal(_mix(self.seed, 13, lot.idx, firm_ids)) * p["noise_sigma"]
        ratio = (
            np.array([f.price_level for f in fs])
            * np.exp(noise)
            * (1 + p["distance_markup_per_100km"] * d / 100)
            * (1 + p["busy_markup"] * np.clip(load - 1, 0, None))
        )
        return ratio * lot.volume / lot.reference

    def value_static(self, lot: Lot, ranking: np.ndarray, day: int | None = None) -> float:
        """Truth: expected competitive bids for this shortlist order, market state as it is now."""
        if len(ranking) == 0:
            return 0.0
        pos = np.arange(len(ranking))
        pb = self.p_bid(lot, ranking, day) * self.p_attract(lot, ranking) * self.exam(pos)
        load = self.load(ranking, self.day(lot.published) if day is None else day)
        comp = self.p_competitive(lot, ranking, load)
        return float((pb * comp).sum())

    def p_competitive(self, lot: Lot, firm_ids: np.ndarray, load: np.ndarray) -> np.ndarray:
        """Truth: P(bid price <= reference * (1 + within)) over the price noise."""
        from scipy.stats import norm

        p = self.cfg["price"]
        fs = [self.firms[i] for i in firm_ids]
        d = km(lot.lat, lot.lon, self.f_lat[firm_ids], self.f_lon[firm_ids])
        mean_log = (
            np.log([f.price_level for f in fs])
            + np.log1p(p["distance_markup_per_100km"] * d / 100)
            + np.log1p(p["busy_markup"] * np.clip(load - 1, 0, None))
            + math.log(lot.volume / lot.reference)
        )
        return norm.cdf((math.log(1 + self.cfg["competitive_within"]) - mean_log) / p["noise_sigma"])

    def serve(self, lot: Lot, shortlist: list[int], policy: str, randomised: bool) -> list[dict[str, Any]]:
        """The buyer sees the shortlist in this order, invites some, firms bid. Returns the logged rows."""
        ids = np.asarray(shortlist, dtype=np.int64)
        if len(ids) == 0:
            return []
        day = self.day(lot.published)
        pos = np.arange(len(ids))
        examined = _mix(self.seed, 21, lot.idx, ids) < self.exam(pos)
        invited = examined & (_mix(self.seed, 22, lot.idx, ids) < self.p_attract(lot, ids))
        pbid = self.p_bid(lot, ids, day)
        load = self.load(ids, day)
        bid = invited & (_mix(self.seed, 23, lot.idx, ids) < pbid)
        ratio = self.price_ratio(lot, ids, load)
        bid_day = [
            lot.published + dt.timedelta(days=int(1 + u * max(1, (lot.deadline - lot.published).days - 1)))
            for u in _mix(self.seed, 24, lot.idx, ids)
        ]
        for f in ids[invited]:
            bisect.insort(self.invite_times[int(f)], day)
        prices = np.where(bid, ratio, np.inf)
        winner = int(np.argmin(prices)) if bid.any() else -1
        rows = []
        for k in range(len(ids)):
            rows.append(
                {
                    "lot_id": lot.idx,
                    "firm_id": int(ids[k]),
                    "position": k,
                    "policy": policy,
                    "randomised": randomised,
                    "invited": bool(invited[k]),
                    "bid": bool(bid[k]),
                    "price_ratio": round(float(ratio[k]), 5) if bid[k] else None,
                    "bid_date": bid_day[k].isoformat() if bid[k] else None,
                    "awarded": k == winner,
                }
            )
        return rows

    # ---- persistence ---------------------------------------------------------------------------------------
    def fork_state(self) -> list[list[int]]:
        return [list(t) for t in self.invite_times]

    def restore_state(self, s: list[list[int]]) -> None:
        self.invite_times = [list(t) for t in s]


def truth_dir() -> Path:
    return config.data_dir() / "truth"
