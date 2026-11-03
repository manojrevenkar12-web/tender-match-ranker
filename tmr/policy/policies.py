"""Ranking policies: from a lot and the platform's state to the shortlist a buyer sees.

Every policy works from logged data only (FeatureState) and returns the shortlist in order. A share of lots
is served from a shuffled shortlist so that position bias can be measured (`randomised=True` is logged).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from .. import config
from ..features.state import FEATURES, FeatureState

F = {n: i for i, n in enumerate(FEATURES)}


def _u(*keys: Any) -> float:
    return zlib.crc32(":".join(map(str, keys)).encode()) / 2**32


@dataclass
class Served:
    shortlist: list[int]
    randomised: bool
    scores: np.ndarray | None = None
    reasons: list[dict[str, Any]] | None = None


class Scorer(Protocol):
    name: str

    def score(self, X: np.ndarray) -> np.ndarray: ...


class Reader(Protocol):
    def predict_proba(self, texts: list[str]) -> np.ndarray: ...


def one_hot(state: FeatureState, label: str) -> np.ndarray:
    v = np.zeros(len(state.trades), dtype=np.float32)
    v[state.t_index[label]] = 1.0
    return v


class Policy:
    name = "policy"

    def __init__(self, shuffle_share: float, seed: int = 0) -> None:
        self.k = int(config.load("ranking")["shortlist"])
        self.shuffle_share = shuffle_share
        self.seed = seed

    def trade_probs(self, lot: dict[str, Any], state: FeatureState) -> np.ndarray:
        return one_hot(state, lot["trade_label"])

    def order(self, lot: dict[str, Any], ids: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError

    def serve(self, lot: dict[str, Any], state: FeatureState) -> Served:
        probs = self.trade_probs(lot, state)
        ids = state.candidates(lot, probs)
        if len(ids) == 0:
            return Served([], False)
        X = state.features(lot, ids, probs)
        ranked, s = self.order(lot, ids, X)
        short = [int(i) for i in ranked[: self.k]]
        randomised = _u(self.seed, "shuffle", lot["lot_id"]) < self.shuffle_share
        if randomised:  # a uniform shuffle of the same shortlist: positions independent of the firms
            rng = np.random.default_rng(zlib.crc32(f"{self.seed}:{lot['lot_id']}".encode()))
            short = [short[i] for i in rng.permutation(len(short))]
        return Served(short, randomised, s)


class Rules(Policy):
    """How the platform ranked before: the buyer's trade label, then experience, then distance."""

    name = "rules"

    def order(self, lot: dict[str, Any], ids: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        s = (
            2.0 * X[:, F["trade_fit_first"]]
            + X[:, F["label_in_profile"]]
            + np.log1p(X[:, F["bids_365"]])
            - X[:, F["dist_km"]] / 100.0
        )
        o = np.lexsort((ids, -s))
        return ids[o], s[o]


class Model(Policy):
    """A learned scorer, then the fatigue discount and slots for new firms."""

    def __init__(
        self,
        name: str,
        scorer: Scorer,
        reader: Reader | None,
        shuffle_share: float,
        fatigue: bool = True,
        new_slots: bool = True,
        seed: int = 0,
    ) -> None:
        super().__init__(shuffle_share, seed)
        self.name = name
        self.scorer = scorer
        self.reader = reader
        self.fatigue = fatigue
        self.new_slots = new_slots
        cfg = config.load("ranking")
        self.penalty = float(cfg["fatigue"]["penalty"])
        self.n_new = int(cfg["exploration"]["new_firm_slots"])
        self._probs: dict[int, np.ndarray] = {}

    def trade_probs(self, lot: dict[str, Any], state: FeatureState) -> np.ndarray:
        if self.reader is None:
            return one_hot(state, lot["trade_label"])
        if lot["lot_id"] not in self._probs:
            from ..text.reader import lot_string

            p = self.reader.predict_proba([lot_string(lot)])[0].astype(np.float32)
            label = one_hot(state, lot["trade_label"])
            self._probs[lot["lot_id"]] = 0.75 * p + 0.25 * label  # the buyer's label is evidence too
        return self._probs[lot["lot_id"]]

    def order(self, lot: dict[str, Any], ids: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        s = self.scorer.score(X).astype(float)
        if self.fatigue:
            s = s / (1.0 + self.penalty * np.clip(X[:, F["load_14"]] - 0.5, 0, None))
        o = np.lexsort((ids, -s))
        ids, s, new = ids[o], s[o], X[o, F["is_new"]] > 0
        if self.new_slots and self.n_new:
            top = list(range(self.k))
            fresh = [i for i in np.where(new)[0] if i >= self.k][: self.n_new]
            if fresh:  # the best new firms replace the last places of the shortlist
                keep = top[: self.k - len(fresh)]
                idx = keep + fresh + [i for i in range(len(ids)) if i not in keep and i not in fresh]
                ids, s = ids[idx], s[idx]
        return ids, s
