"""Ranking models, trained on the logged shortlists.

The label is "the buyer invited the firm and the firm bid". A buyer only looks at so much of a shortlist, so a
firm at position 0 is invited far more often than the same firm at position 15. Three ways to learn from that:

- naive: fit the label as it is (the position bias is baked into the model);
- PBM: P(label) = examination(position) x relevance(firm); examination is measured on the shuffled lots and
  fixed, the network learns relevance (a position-bias model, fitted by maximum likelihood);
- LambdaMART, plain and with LightGBM's own position debiasing, as the strong tabular baseline.

Price: quantiles of a bid's price relative to the reference, from which P(competitive | bid) follows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn

from .. import config
from ..features.state import FEATURES

COUNTS = {
    "invites_365",
    "bids_365",
    "awards_365",
    "trade_bids_365",
    "invites_14",
    "buyer_invites",
    "buyer_bids",
    "buyer_awards",
    "price_n_trade",
    "dist_km",
    "lead_days",
}


def examination(df: pd.DataFrame, k: int) -> np.ndarray:
    """P(the buyer looks at position p), relative to position 0, from the shuffled lots: there the firm at a
    position is independent of the position, so the invitation rate by position is the examination curve."""
    r = df[df["randomised"] & (df["split"] == "train")]
    rate = r.groupby("position")["invited"].mean().reindex(range(k))
    rate = rate.interpolate().bfill().ffill().to_numpy()
    # smooth: a monotone fit in log-log, which is what the raw curve looks like
    pos = np.arange(k)
    ok = rate > 0
    b, a = np.polyfit(np.log1p(pos[ok]), np.log(rate[ok]), 1)
    fit = np.exp(a + b * np.log1p(pos))
    return np.clip(fit / fit[0], 1e-3, 1.0)


@dataclass
class Prep:
    mean: np.ndarray
    std: np.ndarray

    @staticmethod
    def fit(X: np.ndarray) -> Prep:
        Z = _transform(X)
        return Prep(Z.mean(0), Z.std(0) + 1e-6)

    def __call__(self, X: np.ndarray) -> np.ndarray:
        return ((_transform(X) - self.mean) / self.std).astype(np.float32)


def _transform(X: np.ndarray) -> np.ndarray:
    Z = X.astype(np.float64).copy()
    for j, n in enumerate(FEATURES):
        if n in COUNTS:
            Z[:, j] = np.log1p(np.clip(Z[:, j], 0, None))
    return Z


class Net(nn.Module):
    def __init__(self, d: int, hidden: list[int]) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        for h in hidden:
            layers += [nn.Linear(d, h), nn.ReLU()]
            d = h
        layers.append(nn.Linear(d, 1))
        self.f = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.f(x).squeeze(-1)


@dataclass
class TorchRanker:
    name: str
    exam: np.ndarray | None  # None: naive
    prep: Prep | None = None
    state: dict[str, Any] = field(default_factory=dict)
    price: Any = None
    competitive_weight: float = 0.7

    def fit(self, X: np.ndarray, y: np.ndarray, pos: np.ndarray, seed: int = 7) -> TorchRanker:
        cfg = config.load("models")["ranker"]
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        self.prep = Prep.fit(X)
        Z = torch.tensor(self.prep(X))
        Y = torch.tensor(y.astype(np.float32))
        e = torch.tensor((self.exam[pos] if self.exam is not None else np.ones(len(pos))).astype(np.float32))
        net = Net(Z.shape[1], list(cfg["hidden"]))
        opt = torch.optim.Adam(net.parameters(), lr=float(cfg["lr"]), weight_decay=float(cfg["weight_decay"]))
        bs = int(cfg["batch"])
        for _ in range(int(cfg["epochs"])):
            order = torch.tensor(rng.permutation(len(Y)))
            for s in range(0, len(order), bs):
                i = order[s : s + bs]
                p = e[i] * torch.sigmoid(net(Z[i]))  # PBM: examined x relevant (e = 1 for the naive model)
                loss = nn.functional.binary_cross_entropy(p.clamp(1e-6, 1 - 1e-6), Y[i])
                opt.zero_grad()
                loss.backward()
                opt.step()
        self.state = {k: v.detach().clone() for k, v in net.state_dict().items()}
        self.__dict__["_net"] = None
        return self

    def net(self) -> Net:
        n_: Net | None = getattr(self, "_net", None)
        if n_ is None:
            n = Net(len(FEATURES), list(config.load("models")["ranker"]["hidden"]))
            n.load_state_dict(self.state)
            n.eval()
            self.__dict__["_net"] = n
            n_ = n
        return n_

    @torch.no_grad()
    def relevance(self, X: np.ndarray) -> np.ndarray:
        assert self.prep is not None
        return torch.sigmoid(self.net()(torch.tensor(self.prep(X)))).numpy()

    def score(self, X: np.ndarray) -> np.ndarray:
        r = self.relevance(X)
        if self.price is None:
            return r
        w = self.competitive_weight
        return r * (w * self.price.p_competitive(X) + (1 - w))

    def __getstate__(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d.pop("_net", None)
        return d


@dataclass
class LambdaMART:
    name: str
    debias: bool
    model: Any = None
    price: Any = None
    competitive_weight: float = 0.7

    def fit(self, df: pd.DataFrame, seed: int = 7) -> LambdaMART:
        import lightgbm as lgb

        cfg = config.load("models")["lambdamart"]
        d = df.sort_values(["lot_id", "position"])
        label = d["invited"].astype(int) + d["bid"].astype(int) + d["comp"].astype(int)  # 0..3
        groups = d.groupby("lot_id", sort=False).size().to_numpy()
        ds = lgb.Dataset(
            d[FEATURES].to_numpy(),
            label=label.to_numpy(),
            group=groups,
            position=d["position"].to_numpy() if self.debias else None,
        )
        params = {
            "objective": "lambdarank",
            "num_leaves": cfg["num_leaves"],
            "learning_rate": cfg["learning_rate"],
            "min_data_in_leaf": cfg["min_data_in_leaf"],
            "verbose": -1,
            "seed": seed,
            "deterministic": True,
            "num_threads": 2,
            "lambdarank_truncation_level": 20,
            "label_gain": [0, 1, 3, 7],
        }
        self.model = lgb.train(params, ds, num_boost_round=int(cfg["n_estimators"]))
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        s = self.model.predict(X, num_threads=1)
        return 1.0 / (1.0 + np.exp(-s))  # a monotone map; LambdaMART scores only order


@dataclass
class PriceModel:
    """Quantiles of log(price / reference) for a firm bidding on a lot; P(competitive) from them."""

    quantiles: list[float]
    models: list[Any] = field(default_factory=list)
    limit: float = 0.05

    def fit(self, X: np.ndarray, ratio: np.ndarray, seed: int = 7) -> PriceModel:
        import lightgbm as lgb

        cfg = config.load("models")["price"]
        self.limit = float(config.load("ranking")["competitive_within"])
        y = np.log(ratio)
        self.models = []
        for q in self.quantiles:
            m = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                n_estimators=cfg["n_estimators"],
                learning_rate=cfg["learning_rate"],
                num_leaves=15,
                min_child_samples=40,
                random_state=seed,
                deterministic=True,
                n_jobs=2,
                verbose=-1,
            )
            m.fit(X, y)
            self.models.append(m)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        Q = np.column_stack([m.predict(X, num_threads=1) for m in self.models])
        return np.sort(Q, axis=1)  # no crossing

    def p_competitive(self, X: np.ndarray) -> np.ndarray:
        Q = self.predict(X)
        t = math.log(1 + self.limit)
        qs = np.array(self.quantiles)
        out = np.empty(len(Q))
        for i, row in enumerate(Q):  # piecewise-linear CDF through the quantiles, flat tails
            out[i] = np.interp(t, row, qs, left=0.02, right=0.98)
        return out


@dataclass
class OutcomeModel:
    """Direct-method model for doubly-robust evaluation: P(competitive bid | firm, position)."""

    model: Any = None

    def fit(self, df: pd.DataFrame, seed: int = 11) -> OutcomeModel:
        import lightgbm as lgb

        X = np.column_stack([df[FEATURES].to_numpy(), df["position"].to_numpy()])
        self.model = lgb.LGBMClassifier(
            n_estimators=250,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=60,
            random_state=seed,
            deterministic=True,
            n_jobs=2,
            verbose=-1,
        )
        self.model.fit(X, df["comp"].astype(int).to_numpy())
        return self

    def predict(self, X: np.ndarray, pos: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(np.column_stack([X, pos]), num_threads=1)[:, 1]
