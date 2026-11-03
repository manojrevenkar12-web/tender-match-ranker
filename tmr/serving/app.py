"""The ranking API and the console's backend.

The service loads the models from runs/ and the platform's state from its logs, then serves: open lots, the
shortlist for a lot (with reasons, P(bid), P(competitive), the expected price band and a fatigue flag),
invitations, the experiment results, monitoring and the invite planner. Every shortlist is logged with its
positions (migrations/0001_init.sql) so the next model can be trained and evaluated without bias.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pickle
import time
import uuid
from functools import cache
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import config
from ..features.build import load
from ..features.state import FEATURES, FeatureState
from ..policy.policies import F, Model
from ..text.reader import lot_string
from .store import Store, make

app = FastAPI(title="tender-match-ranker", version="0.1.0")
VERSION = os.environ.get("TMR_MODEL_VERSION", "torch_pbm+fatigue@" + dt.date.today().isoformat())


class Ctx:
    def __init__(self) -> None:
        with open(config.data_dir() / "logs" / "state_at_heldout.pkl", "rb") as f:
            self.state: FeatureState = pickle.load(f)
        from ..text.llm_reader import HybridReader

        self.ranker = Model("ranker", load("ranker_torch_pbm.pkl"), HybridReader(load("reader_hash.pkl")), 0.0)
        self.price = load("price.pkl")
        self.exam = load("examination.pkl")
        lots = pd.read_parquet(config.data_dir() / "logs" / "lots.parquet")
        self.lots = {int(r["lot_id"]): r for r in lots[lots["split"] == "heldout"].to_dict("records")}
        self.store: Store = make()
        self.latency: list[float] = []


@cache
def ctx() -> Ctx:
    return Ctx()


def _lot(lot_id: int) -> dict[str, Any]:
    lot = ctx().lots.get(lot_id)
    if lot is None:
        raise HTTPException(404, "no open lot with this id")
    return lot


@app.get("/health")
def health() -> dict[str, Any]:
    c = ctx()
    return {"ok": True, "model_version": VERSION, "open_lots": len(c.lots)}


@app.get("/v1/lots")
def lots(limit: int = 60, q: str = "") -> list[dict[str, Any]]:
    c = ctx()
    out = []
    for lot in sorted(c.lots.values(), key=lambda r: (r["deadline"], r["lot_id"])):
        if q and q.lower() not in (lot["title"] + " " + lot["text"] + " " + lot["city"]).lower():
            continue
        p = c.ranker.trade_probs(lot, c.state)
        t = int(np.argmax(p))
        out.append(
            {
                k: lot[k]
                for k in (
                    "lot_id",
                    "tender_id",
                    "title",
                    "city",
                    "published",
                    "deadline",
                    "trade_label",
                    "reference_eur",
                )
            }
            | {"trade": c.state.trades[t], "trade_prob": round(float(p[t]), 3)}
        )
        if len(out) >= limit:
            break
    return out


@app.get("/v1/lots/{lot_id}")
def lot_detail(lot_id: int) -> dict[str, Any]:
    lot = _lot(lot_id)
    c = ctx()
    p = c.ranker.trade_probs(lot, c.state)
    top = np.argsort(-p)[:3]
    return lot | {
        "trades": [
            {
                "trade": c.state.trades[i],
                "name": config.load("trades")["trades"][c.state.trades[i]]["name"],
                "prob": round(float(p[i]), 3),
            }
            for i in top
        ]
    }


@app.get("/v1/lots/{lot_id}/shortlist")
def shortlist(lot_id: int) -> dict[str, Any]:
    t0 = time.perf_counter()
    c = ctx()
    lot = _lot(lot_id)
    probs = c.ranker.trade_probs(lot, c.state)
    ids = c.state.candidates(lot, probs)
    if len(ids) == 0:
        return {"lot_id": lot_id, "model_version": VERSION, "firms": [], "expected_competitive": 0.0, "candidates": 0}
    X = c.state.features(lot, ids, probs)
    ranked, s = c.ranker.order(lot, ids, X)
    k = c.ranker.k
    row = {int(f): i for i, f in enumerate(ids)}
    sel = np.array([row[int(f)] for f in ranked[:k]])
    Xs = X[sel]
    scorer: Any = c.ranker.scorer
    rel = scorer.relevance(Xs)
    pc = c.price.p_competitive(Xs)
    q = np.exp(c.price.predict(Xs))
    exam = c.exam[: len(sel)]
    firms = []
    for i, f in enumerate(ranked[:k]):
        x = dict(zip(FEATURES, Xs[i].tolist()))
        firms.append(
            {
                "firm_id": int(f),
                "position": i,
                "score": round(float(s[i]), 4),
                "p_bid": round(float(rel[i]), 4),
                "p_competitive": round(float(pc[i]), 3),
                "price_band": [
                    round(float(q[i, 0]), 3),
                    round(float(q[i, len(q[i]) // 2]), 3),
                    round(float(q[i, -1]), 3),
                ],
                "distance_km": round(x["dist_km"], 1),
                "bids_365": int(x["bids_365"]),
                "bid_rate": round(x["bid_rate"], 3),
                "invites_14": int(x["invites_14"]),
                "busy": bool(x["load_14"] > 1.0),
                "new": bool(x["is_new"] > 0),
                "knows_buyer": bool(x["buyer_bids"] > 0),
                "trades": c.state.firms[int(f)]["trades"],
                "city": c.state.firms[int(f)]["city"],
            }
        )
    expected = float((exam * rel * pc).sum())
    c.store.log_shortlist(
        [
            {
                "lot_id": lot_id,
                "policy": "ranker",
                "model_version": VERSION,
                "randomised": False,
                "firm_id": r["firm_id"],
                "position": r["position"],
                "score": r["score"],
                "p_bid": r["p_bid"],
                "p_competitive": r["p_competitive"],
            }
            for r in firms
        ]
    )
    c.latency.append((time.perf_counter() - t0) * 1000)
    return {
        "lot_id": lot_id,
        "model_version": VERSION,
        "candidates": int(len(ids)),
        "firms": firms,
        "expected_competitive": round(expected, 3),
        "busy_share": round(float(np.mean(X[:, F["load_14"]] > 1)), 3),
    }


class Invite(BaseModel):
    firm_ids: list[int] = Field(min_length=1, max_length=60)
    idempotency_key: str = Field(default_factory=lambda: uuid.uuid4().hex)
    invited_by: str = "buyer"


@app.post("/v1/lots/{lot_id}/invitations")
def invite(lot_id: int, body: Invite) -> dict[str, Any]:
    c = ctx()
    lot = _lot(lot_id)
    n = c.store.invite(lot_id, body.firm_ids, body.invited_by, body.idempotency_key)
    day = c.state.day(lot["published"])
    if n:  # the fatigue features see the new invitations at once
        import bisect

        for f in body.firm_ids:
            bisect.insort(c.state.invites[f], day)
    return {"invited": n, "idempotency_key": body.idempotency_key}


@app.get("/v1/experiments")
def experiments() -> dict[str, Any]:
    p = config.REPORTS / "results.json"
    if not p.exists():
        raise HTTPException(503, "no results yet: run `tmr all`")
    return json.loads(p.read_text())


@app.get("/v1/monitoring")
def monitoring() -> dict[str, Any]:
    p = config.REPORTS / "monitoring.json"
    if not p.exists():
        raise HTTPException(503, "no monitoring run yet: run `tmr heldout month`")
    return json.loads(p.read_text())


class PlanRequest(BaseModel):
    request: str = Field(min_length=10, max_length=6000)


@app.post("/v1/agent/plan")
def agent_plan(body: PlanRequest) -> dict[str, Any]:
    from ..agent.planner import plan

    c = ctx()
    p = plan(body.request, c.state, c.ranker, dt.date(2026, 12, 1), use_model=os.environ.get("TMR_LLM") != "off")
    return {"request": p.request, "lots": p.lots, "violations": p.violations, "model": p.model}


_ = lot_string
web = config.ROOT / "web" / "dist"
if web.exists():
    app.mount("/", StaticFiles(directory=web, html=True), name="web")
