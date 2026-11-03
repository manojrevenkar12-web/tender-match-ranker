"""A model reads the lots the trade reader is unsure about.

The hash reader is fast and right on wording it has seen; on wording it has not seen it says so (its top
probability is low). Only those lots go to the model, in batches, with the trade list as the only allowed
answers. The answer is cached; with no model available the hash reader's answer stands.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from .. import config, llm


class HybridReader:
    def __init__(self, base: Any, threshold: float | None = None, batch: int = 12) -> None:
        self.base = base
        self.trades = base.trades
        cfg = config.load("models")["trade_reader"]
        self.threshold = float(threshold if threshold is not None else cfg["model_below"])
        self.weight = float(cfg["model_weight"])
        self.batch = batch
        self.meta: dict[str, Any] = {"calls": 0, "cost_usd": 0.0}

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        p = self.base.predict_proba(texts)
        unsure = [i for i in range(len(texts)) if p[i].max() < self.threshold]
        for s in range(0, len(unsure), self.batch):
            idx = unsure[s : s + self.batch]
            got = self._ask([texts[i] for i in idx])
            for i, t in zip(idx, got):
                if t in self.trades:
                    one = np.zeros(len(self.trades))
                    one[self.trades.index(t)] = 1.0
                    p[i] = self.weight * one + (1 - self.weight) * p[i]
        return p

    def _ask(self, texts: list[str]) -> list[str | None]:
        names = config.load("trades")["trades"]
        trades = {k: f"{v['name']} ({v['norm']})" for k, v in names.items()}
        schema = {
            "type": "object",
            "properties": {
                "lots": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"n": {"type": "integer"}, "trade": {"type": "string", "enum": list(trades)}},
                        "required": ["n", "trade"],
                    },
                }
            },
            "required": ["lots"],
        }
        user = json.dumps(
            {"trades": trades, "lots": [{"n": i, "text": t} for i, t in enumerate(texts)]}, ensure_ascii=False
        )
        out = llm.structured("trade_reader", user, schema, self.meta)
        by_n = {x["n"]: x["trade"] for x in (out or {}).get("lots", []) if isinstance(x, dict)}
        return [by_n.get(i) for i in range(len(texts))]

    def __getstate__(self) -> dict[str, Any]:
        return dict(self.__dict__)
