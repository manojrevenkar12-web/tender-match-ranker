"""Build the market's history: every lot served by the current rules, logged as the platform logs it."""

from __future__ import annotations

import json
import pickle
import time
from typing import Any

import pandas as pd

from .. import config
from ..evaluate.replay import run
from ..features.state import FeatureState
from ..policy.policies import Rules
from .market import Market, truth_dir, world_config


def splits(n_months: int) -> dict[str, list[int]]:
    s = world_config()["splits"]
    test_start = n_months + s["train_until"]
    return {
        "train": list(range(0, test_start)),
        "test": list(range(test_start, test_start + s["test_months"])),
        "heldout": list(range(test_start + s["test_months"], n_months)),
    }


def build(profile: str = "full") -> dict[str, Any]:
    t0 = time.time()
    market = Market(profile)
    sp = splits(market.n_months)
    logs = config.data_dir() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    truth_dir().mkdir(parents=True, exist_ok=True)
    state = FeatureState(market.public_firms(), market.start)
    rules = Rules(shuffle_share=world_config()["logging_policy"]["exploration_share"], seed=market.seed)
    rows: list[dict[str, Any]] = []
    for split in ("train", "test", "heldout"):
        months = set(sp[split])
        lots = [lot for lot in market.lots if market.month_of(lot) in months]
        with open(truth_dir() / f"market_at_{split}.pkl", "wb") as f:  # the market as this split begins
            pickle.dump(market.fork_state(), f)
        state.advance(market.day(lots[0].published) if lots else 0)
        with open(logs / f"state_at_{split}.pkl", "wb") as f:  # the platform's own state, rebuilt from its logs
            pickle.dump(state, f)
        rows += run(market, lots, lambda _lot: rules, state)
    lots_df = pd.DataFrame([lot.public() | {"month": market.month_of(lot)} for lot in market.lots])
    lots_df["split"] = lots_df["month"].map({m: s for s, ms in sp.items() for m in ms})
    lots_df.to_parquet(logs / "lots.parquet", index=False)
    pd.DataFrame(market.public_firms()).to_parquet(logs / "firms.parquet", index=False)
    imp = pd.DataFrame(rows)
    imp.to_parquet(logs / "impressions.parquet", index=False)
    with open(truth_dir() / "market.pkl", "wb") as f:
        pickle.dump(market, f)
    pd.DataFrame([{"lot_id": lot.idx, "trade": lot.trade, "volume": lot.volume} for lot in market.lots]).to_parquet(
        truth_dir() / "lots.parquet", index=False
    )
    summary = {
        "profile": profile,
        "start": market.start.isoformat(),
        "months": market.n_months,
        "firms": len(market.firms),
        "buyers": len(market.buyers),
        "lots": len(market.lots),
        "impressions": len(imp),
        "invited": int(imp["invited"].sum()),
        "bids": int(imp["bid"].sum()),
        "randomised_lots": int(imp.groupby("lot_id")["randomised"].first().sum()),
        "seconds": round(time.time() - t0, 1),
        "splits": {k: len(v) for k, v in sp.items()},
        "split_months": sp,
    }
    (logs / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary
