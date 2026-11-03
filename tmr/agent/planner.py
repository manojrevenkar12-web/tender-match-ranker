"""The invite planner: from a buyer's request in plain words to verified invitations per lot.

The model reads and writes; code decides. Two model calls per request:

1. understand: lots, project city, deadline and the buyer's constraints, as structured output;
2. decide and word: given what the tools returned (the trade reader, the ranked shortlist with reasons,
   shortages), choose whom to invite from the shortlist and word the invitation.

Between them the tools run in code. After them a verifier checks every decision against the constraints and
every message against the facts; anything that fails is replaced by the code's own plan and logged.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .. import config, llm
from ..features.state import FEATURES, FeatureState
from ..geo import km
from ..policy.policies import Model
from ..text.reader import lot_string

UNDERSTAND = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "deadline": {"type": "string", "description": "YYYY-MM-DD"},
        "max_km": {"type": ["number", "null"]},
        "min_invites": {"type": ["integer", "null"]},
        "exclude_firm_ids": {"type": "array", "items": {"type": "integer"}},
        "lots": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "text": {"type": "string"}},
                "required": ["title", "text"],
            },
        },
    },
    "required": ["city", "deadline", "lots", "exclude_firm_ids"],
}
DECIDE = {
    "type": "object",
    "properties": {
        "lots": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "invite": {"type": "array", "items": {"type": "integer"}},
                    "message": {"type": "string"},
                    "escalate": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["title", "invite", "message", "escalate"],
            },
        }
    },
    "required": ["lots"],
}


@dataclass
class Plan:
    request: dict[str, Any]
    lots: list[dict[str, Any]] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    model: dict[str, Any] = field(default_factory=dict)


def places() -> dict[str, list[float]]:
    return config.load("places")["places"]


def resolve_city(name: str) -> str | None:
    """A district or a spelling variant to the gazetteer's city: "München-Riem" -> "München"."""
    if name in places():
        return name
    low = name.lower()
    hits = [c for c in places() if low.startswith(c.lower()) or c.lower() in low]
    return max(hits, key=len) if hits else None


def shortlist(
    state: FeatureState, ranker: Model, req: dict[str, Any], lot: dict[str, Any], on: dt.date, n: int = 12
) -> dict[str, Any]:
    """The ranking tool: the shortlist for one lot under the buyer's constraints, with reasons."""
    lat, lon = places()[req["city"]]
    pub = {
        "lot_id": -1,
        "buyer_id": -1,
        "published": on.isoformat(),
        "deadline": req["deadline"],
        "lat": lat,
        "lon": lon,
        "trade_label": "",
        "title": lot["title"],
        "text": lot["text"],
        "reference_eur": 150000.0,
    }
    assert ranker.reader is not None, "the planner needs a trade reader"
    probs = ranker.reader.predict_proba([lot_string(pub)])[0].astype(np.float32)
    trades = config.trades()
    pub["trade_label"] = trades[int(np.argmax(probs))]
    ids = state.candidates(pub, probs)
    excluded = set(req.get("exclude_firm_ids") or [])
    d = km(lat, lon, state.lat[ids], state.lon[ids])
    keep = np.array(
        [i not in excluded and (req.get("max_km") is None or dd <= req["max_km"]) for i, dd in zip(ids, d)], dtype=bool
    )
    ids = ids[keep] if len(ids) else ids
    out = {"trade": pub["trade_label"], "trade_prob": round(float(probs.max()), 3), "candidates": []}
    if len(ids) == 0:
        out["shortage"] = True
        return out
    X = state.features(pub, ids, probs)
    ranked, s = ranker.order(pub, ids, X)
    row = {int(f): i for i, f in enumerate(ids)}
    for f, sc in zip(ranked[:n], s[:n]):
        x = X[row[int(f)]]
        out["candidates"].append({"firm_id": int(f), "score": round(float(sc), 4), "reasons": reasons(x)})
    out["shortage"] = len(out["candidates"]) < int(req.get("min_invites") or 0)
    return out


def reasons(x: np.ndarray) -> list[str]:
    f = dict(zip(FEATURES, x.tolist()))
    r = [f"{f['dist_km']:.0f} km entfernt"]
    if f["bids_365"] >= 1:
        r.append(f"{int(f['bids_365'])} Angebote in 12 Monaten ({f['bid_rate']:.0%} der Anfragen)")
    else:
        r.append("noch keine Angebote über die Plattform")
    if f["load_14"] > 1:
        r.append(f"ausgelastet: {int(f['invites_14'])} Anfragen in 14 Tagen")
    if f["buyer_bids"] >= 1:
        r.append(f"hat Ihnen schon {int(f['buyer_bids'])}-mal angeboten")
    return r


def plan(request_text: str, state: FeatureState, ranker: Model, on: dt.date, use_model: bool = True) -> Plan:
    meta: dict[str, Any] = {"calls": 0, "cost_usd": 0.0}
    req = understand(request_text, meta, use_model)
    p = Plan(request=req, model=meta)
    req["city"] = resolve_city(req.get("city") or "") or req.get("city")
    if req.get("city") not in places():
        p.violations.append(f"unknown city {req.get('city')!r}")
        return p
    tools = [shortlist(state, ranker, req, lot, on) for lot in req["lots"]]
    decided = decide(request_text, req, tools, meta, use_model)
    for lot, tool, dec in zip(req["lots"], tools, decided):
        offered = [c["firm_id"] for c in tool["candidates"]]
        want = int(req.get("min_invites") or min(8, len(offered)))
        v = verify(req, lot, dec, offered, want)
        if v:
            p.violations += v
            dec = fallback(req, lot, offered, want)
        p.lots.append(
            {
                "title": lot["title"],
                "trade": tool["trade"],
                "trade_prob": tool["trade_prob"],
                "offered": tool["candidates"],
                "invite": dec["invite"],
                "message": dec["message"],
                "escalate": dec.get("escalate", False) or tool["shortage"],
                "reason": dec.get("reason", ""),
                "verified": not v,
            }
        )
    return p


def understand(text: str, meta: dict[str, Any], use_model: bool) -> dict[str, Any]:
    if use_model:
        got = llm.structured("agent_understand", text, UNDERSTAND, meta)
        if got is not None:
            return got
    return parse_plain(text)


def decide(
    text: str, req: dict[str, Any], tools: list[dict[str, Any]], meta: dict[str, Any], use_model: bool
) -> list[dict[str, Any]]:
    if use_model:
        ask = json.dumps(
            {
                "request": text,
                "constraints": {k: req.get(k) for k in ("deadline", "max_km", "min_invites", "exclude_firm_ids")},
                "lots": [{"title": lot["title"], **t} for lot, t in zip(req["lots"], tools)],
            },
            ensure_ascii=False,
        )
        got = llm.structured("agent_decide", ask, DECIDE, meta)
        if got is not None and len(got.get("lots", [])) == len(tools):
            return got["lots"]
    return [
        fallback(
            req,
            lot,
            [c["firm_id"] for c in t["candidates"]],
            int(req.get("min_invites") or min(8, len(t["candidates"]))),
        )
        for lot, t in zip(req["lots"], tools)
    ]


def de_date(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def verify(req: dict[str, Any], lot: dict[str, Any], dec: dict[str, Any], offered: list[int], want: int) -> list[str]:
    v = []
    inv = dec.get("invite", [])
    if any(f not in offered for f in inv):
        v.append(f"{lot['title']}: invites a firm the ranking did not offer")
    if set(inv) & set(req.get("exclude_firm_ids") or []):
        v.append(f"{lot['title']}: invites an excluded firm")
    if len(set(inv)) < min(want, len(offered)) and not dec.get("escalate"):
        v.append(f"{lot['title']}: fewer invitations than asked for, without saying why")
    msg = dec.get("message", "")
    if de_date(req["deadline"]) not in msg:
        v.append(f"{lot['title']}: the message does not state the deadline {de_date(req['deadline'])}")
    if re.search(r"\d[\d.,]*\s?(?:€|eur\b|euro\b)", msg, re.I):
        v.append(f"{lot['title']}: the message names an amount")
    return v


def fallback(req: dict[str, Any], lot: dict[str, Any], offered: list[int], want: int) -> dict[str, Any]:
    return {
        "invite": offered[:want],
        "escalate": len(offered) < want,
        "reason": "zu wenige passende Firmen" if len(offered) < want else "",
        "message": (
            f"Guten Tag,\n\nwir laden Sie ein, ein Angebot für „{lot['title']}“ abzugeben. Die Unterlagen "
            f"finden Sie im Projektraum. Angebotsfrist: {de_date(req['deadline'])}.\n\nMit freundlichen Grüßen"
        ),
    }


MONTHS = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}


def parse_plain(text: str) -> dict[str, Any]:
    """The rules-only reading of a request, used when no model is available."""
    low = text.lower()
    city = next((c for c in sorted(places(), key=len, reverse=True) if c.lower() in low), "")
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    deadline = f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}" if m else ""
    km_m = re.search(r"(\d+)\s?km", low)
    inv = re.search(r"(?:mindestens|min\.|at least)\s*(\d+)", low)
    excl = [int(x) for x in re.findall(r"(?:id|nr\.?)\s*(\d+)", low) if "nicht" in low or "ohne" in low or "not" in low]
    lots = []
    for line in text.splitlines():
        lm = re.match(r"\s*(?:-|\*|•|\d+[.)])?\s*(Los\s*\d+[^:]*|[A-ZÄÖÜ][\wäöüß\- ]+?):\s*(.+)", line)
        if lm and not re.match(r"(?i)(frist|angebotsfrist|bitte|hinweis|ort|projekt)", lm[1]):
            lots.append({"title": lm[1].strip(), "text": lm[2].strip()})
    return {
        "city": city,
        "deadline": deadline,
        "max_km": float(km_m[1]) if km_m else None,
        "min_invites": int(inv[1]) if inv else None,
        "exclude_firm_ids": excl,
        "lots": lots,
    }
