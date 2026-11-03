"""The invite planner on its cases: extraction, trades, the invariants, verified messages and cost."""

from __future__ import annotations

import datetime as dt
import json
import pickle
from typing import Any

import yaml

from .. import config
from ..features.build import load
from ..policy.policies import Model
from .planner import plan


def run_evals(use_model: bool = True, write: bool = True) -> dict[str, Any]:
    cases = yaml.safe_load((config.ROOT / "tmr" / "agent" / "cases.yaml").read_text())
    with open(config.data_dir() / "logs" / "state_at_heldout.pkl", "rb") as f:
        state = pickle.load(f)
    ranker = Model("ranker", load("ranker_torch_pbm.pkl"), load("reader_hash.pkl"), 0.0)
    on = dt.date(2026, 12, 1)
    rows, cost, calls = [], 0.0, 0
    for c in cases:
        p = plan(c["request"], state, ranker, on, use_model)
        e, r = c["expect"], p.request
        ext = {
            "city": r.get("city") == e["city"],
            "deadline": r.get("deadline") == e["deadline"],
            "max_km": (r.get("max_km") or None) == e["max_km"],
            "min_invites": (r.get("min_invites") or None) == e["min_invites"],
            "exclude": sorted(r.get("exclude_firm_ids") or []) == sorted(e["exclude"]),
            "lots": len(r.get("lots", [])) == len(e["trades"]),
        }
        trades_ok = [lot["trade"] == t for lot, t in zip(p.lots, e["trades"])]
        broken = []  # invariants on the final plan, after the verifier
        for lot in p.lots:
            if set(lot["invite"]) & set(e["exclude"]):
                broken.append("excluded firm invited")
            if any(f not in [o["firm_id"] for o in lot["offered"]] for f in lot["invite"]):
                broken.append("firm outside the shortlist")
        rows.append(
            {
                "id": c["id"],
                "extraction": ext,
                "trades_right": sum(trades_ok),
                "trades": len(e["trades"]),
                "verifier_replaced": len(p.violations),
                "broken": broken,
                "messages_verified": sum(lot["verified"] for lot in p.lots),
                "lots": len(p.lots),
            }
        )
        cost += p.model.get("cost_usd", 0.0)
        calls += p.model.get("calls", 0)
    n = len(rows)
    out = {
        "cases": n,
        "model": use_model,
        "extraction_exact": round(sum(all(r["extraction"].values()) for r in rows) / n, 3),
        "field_accuracy": {k: round(sum(r["extraction"][k] for r in rows) / n, 3) for k in rows[0]["extraction"]},
        "trade_accuracy": round(sum(r["trades_right"] for r in rows) / max(1, sum(r["trades"] for r in rows)), 3),
        "invariants_broken": sum(len(r["broken"]) for r in rows),
        "decisions_replaced_by_verifier": sum(r["verifier_replaced"] for r in rows),
        "model_messages_verified": f"{sum(r['messages_verified'] for r in rows)}/{sum(r['lots'] for r in rows)}",
        "calls": calls,
        "cost_usd": round(cost, 4),
        "rows": rows,
    }
    if write:
        name = "agent.json" if use_model else "agent-no-model.json"
        (config.runs_dir() / name).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out
