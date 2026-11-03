"""Held-out runs. Their first run is written once and never rewritten (AGENTS.md).

- `month`: the last month of the market, never used for training or for choosing anything: the rules and the
  shipping ranker each run it as a market replay; the ranker's month also feeds the monitoring checks.
- `blind-<n>`: lots written by someone who never saw the code or data (heldout/WRITING_LOTS.md); the trade
  readers are scored on them.
"""

from __future__ import annotations

import datetime as dt
import json
import pickle
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .. import config
from ..features.build import load
from ..features.state import FEATURES
from ..monitor.checks import run as monitor
from ..text.reader import scores
from .study import _market, _state, policies


def _record(name: str, result: dict[str, Any]) -> dict[str, Any]:
    d = config.REPORTS / "heldout" / name
    d.mkdir(parents=True, exist_ok=True)
    status_file = config.ROOT / "heldout" / name / "STATUS"
    result["status"] = status_file.read_text().strip() if status_file.exists() else "blind"
    result["ran_at"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    first = d / "first_run.json"
    target = d / ("latest_run.json" if first.exists() else "first_run.json")
    target.write_text(json.dumps(result, indent=1, ensure_ascii=False))
    result["recorded_as"] = target.name
    return result


def month() -> dict[str, Any]:
    market = _market()
    with open(config.data_dir() / "truth" / "market_at_heldout.pkl", "rb") as f:
        start = pickle.load(f)
    months = set(json.loads((config.data_dir() / "logs" / "summary.json").read_text())["split_months"]["heldout"])
    lots = [lot for lot in market.lots if market.month_of(lot) in months]
    pols = policies()
    exam = load("examination.pkl")
    comp = 1 + float(config.load("ranking")["competitive_within"])
    out: dict[str, Any] = {"lots": len(lots)}
    live_rows: list[pd.DataFrame] = []
    low_conf = []
    for name in ("rules", "ranker"):
        market.restore_state(start)
        state = _state("heldout")
        pol: Any = pols[name]
        expected, realised, bids = [], 0, 0
        for lot in lots:
            pub = lot.public()
            served = pol.serve(pub, state)
            ids = np.array(served.shortlist, dtype=np.int64)
            expected.append(market.value_static(lot, ids, market.day(lot.published)))
            if name == "ranker" and len(ids):
                probs = pol.trade_probs(pub, state)
                low_conf.append(float(pol.reader.predict_proba([pub["title"] + "\n" + pub["text"]])[0].max() < 0.5))
                X = state.features(pub, ids, probs)
            rows = market.serve(lot, served.shortlist, name, False)
            if name == "ranker" and len(ids):
                b = pd.DataFrame(X, columns=FEATURES)
                b["firm_id"] = ids
                b["position"] = np.arange(len(ids))
                b["pred"] = exam[: len(ids)] * pol.scorer.relevance(X)
                b["y"] = [r["invited"] and r["bid"] for r in rows]
                b["invited"] = [r["invited"] for r in rows]
                b["new"] = b["is_new"] > 0
                live_rows.append(b)
            state.record(pub, rows)
            realised += sum(1 for r in rows if r["bid"] and r["price_ratio"] <= comp)
            bids += sum(1 for r in rows if r["bid"])
        out[name] = {
            "expected_competitive_per_lot": round(float(np.mean(expected)), 4),
            "realised_competitive_per_lot": round(realised / len(lots), 4),
            "bids_per_lot": round(bids / len(lots), 4),
        }
    r, b = out["rules"]["expected_competitive_per_lot"], out["ranker"]["expected_competitive_per_lot"]
    out["lift"] = round(b / r - 1, 4)
    train = pd.read_parquet(config.runs_dir() / "features.parquet")
    train = train[train["split"] == "train"]
    mon = monitor(pd.concat(live_rows, ignore_index=True), train, len(market.firms), float(np.mean(low_conf)))
    (config.REPORTS / "monitoring.json").write_text(json.dumps(mon, indent=1))
    out["monitoring_alerts"] = mon["alerts"]
    return _record("month", out)


def blind(name: str) -> dict[str, Any]:
    lots = yaml.safe_load((config.ROOT / "heldout" / name / "lots.yaml").read_text(encoding="utf-8"))
    texts = [f"{x['title']}\n{x['text']}" for x in lots]
    y = [x["trade"] for x in lots]
    trades = config.trades()
    out: dict[str, Any] = {"lots": len(lots)}
    from ..text.llm_reader import HybridReader

    hybrid = HybridReader(load("reader_hash.pkl"))
    for kind in ("tfidf", "hash", "hybrid"):
        p = (hybrid if kind == "hybrid" else load(f"reader_{kind}.pkl")).predict_proba(texts)
        out[kind] = scores(y, p, trades)
        pred = [trades[i] for i in p.argmax(1)]
        kinds = [str(x.get("note", "")).split(":")[0].split(" ")[0] or "easy" for x in lots]
        out[kind]["by_kind"] = {
            k: round(float(np.mean([a == b for a, b, kk in zip(y, pred, kinds) if kk == k])), 3)
            for k in sorted(set(kinds))
        }
        if kind == "hybrid":
            out["hybrid"]["model"] = dict(hybrid.meta)
            out["misses"] = [{"id": x["id"], "trade": t, "read_as": q} for x, t, q in zip(lots, y, pred) if t != q]
    return _record(name, out)


def run_set(name: str) -> dict[str, Any]:
    return month() if name == "month" else blind(name)
