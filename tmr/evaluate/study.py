"""The study: every ranking policy, judged three ways on the test months.

1. Offline, from the logs alone: NDCG on logged labels, IPS and doubly-robust estimates.
2. The truth for the same lots and the same market state (the simulator knows it): which estimate is right?
3. A market replay: every buyer uses the policy for three months, so firms that are asked too often stop
   answering. Single-lot estimates cannot see this; the replay can.

Then an A/B test as the platform would run it, with CUPED and sequential looks, against the true effect.
Only this package and tmr.sim read the simulator.
"""

from __future__ import annotations

import json
import pickle
import time
from typing import Any

import numpy as np
import pandas as pd

from .. import config
from ..features.build import load, load_logs
from ..features.state import FEATURES, FeatureState
from ..policy import ope
from ..policy.policies import Model, Policy, Rules
from ..sim.market import Market, truth_dir
from .replay import run


def policies() -> dict[str, Policy]:
    reader = load("reader_hash.pkl")
    out: dict[str, Policy] = {"rules": Rules(shuffle_share=0.0)}
    for name in ("lambdamart", "lambdamart_debiased", "torch_naive", "torch_pbm"):
        out[name] = Model(name, load(f"ranker_{name}.pkl"), reader, 0.0, fatigue=False, new_slots=False)
    from ..text.llm_reader import HybridReader

    out["ranker"] = Model(
        "ranker", load("ranker_torch_pbm.pkl"), HybridReader(reader), 0.0, fatigue=True, new_slots=True
    )
    return out


def _market() -> Market:
    with open(truth_dir() / "market.pkl", "rb") as f:
        return pickle.load(f)


def _state(split: str) -> FeatureState:
    with open(config.data_dir() / "logs" / f"state_at_{split}.pkl", "rb") as f:
        return pickle.load(f)


def offline(split: str = "test") -> dict[str, Any]:
    market = _market()
    lots, _, imp = load_logs()
    pols = policies()
    exam = load("examination.pkl")
    dm = load("outcome_dm.pkl")
    k = int(config.load("ranking")["shortlist"])
    comp = 1.0 + float(config.load("ranking")["competitive_within"])
    state = _state(split)
    test = lots[lots["split"] == split].sort_values(["published", "lot_id"])
    by_lot = {i: g for i, g in imp.groupby("lot_id", sort=False)}
    rows: dict[str, list[dict[str, float]]] = {p: [] for p in pols}
    for lot in test.to_dict("records"):
        g = by_lot.get(lot["lot_id"])
        if g is None:
            continue
        lt = market.lots[lot["lot_id"]]
        day = market.day(lt.published)
        state.advance(state.day(lot["published"]))
        shown = g["firm_id"].to_numpy()
        y = ((g["price_ratio"].fillna(9) <= comp) & g["bid"]).to_numpy().astype(float)
        gains = {
            int(f): float(a) + float(b) + float(c)
            for f, a, b, c in zip(shown, g["invited"], g["bid"], (g["price_ratio"].fillna(9) <= comp) & g["bid"])
        }
        logged = [(int(f), int(p), float(v)) for f, p, v in zip(shown, g["position"], y)]
        for name, pol in pols.items():
            probs = pol.trade_probs(lot, state)
            cands = state.candidates(lot, probs)
            ids = np.union1d(cands, shown)
            X = state.features(lot, ids, probs)
            in_c = np.isin(ids, cands)
            ranked, _ = pol.order(lot, ids[in_c], X[in_c])
            top = [int(f) for f in ranked[:k]]
            new_pos = {f: i for i, f in enumerate(top)}
            row_of = {int(f): i for i, f in enumerate(ids)}
            m_new = dm.predict(X[[row_of[f] for f in top]], np.arange(len(top))) if top else np.array([])
            m_log = dm.predict(X[[row_of[int(f)] for f in shown]], g["position"].to_numpy())
            rows[name].append(
                {
                    "lot_id": lot["lot_id"],
                    "ndcg": ope.ndcg(top, gains, k),
                    "ips": ope.ips(new_pos, logged, exam),
                    "dr": ope.dr(new_pos, logged, exam, dict(zip(top, m_new)), dict(zip(map(int, shown), m_log))),
                    "truth": market.value_static(lt, np.array(top, dtype=np.int64), day),
                    "support": float(np.mean([f in set(map(int, shown)) for f in top])) if top else 0.0,
                    "logged": float(y.sum()),
                }
            )
        state.record(lot, g.to_dict("records"))
    out: dict[str, Any] = {}
    base = pd.DataFrame(rows["rules"])
    for name, r in rows.items():
        d = pd.DataFrame(r)
        lift_dr = ope.paired_ci(d["dr"].to_numpy(), base["dr"].to_numpy())
        lift_truth = ope.paired_ci(d["truth"].to_numpy(), base["truth"].to_numpy())
        out[name] = {
            "lots": len(d),
            "ndcg": round(d["ndcg"].mean(), 4),
            "ips": round(d["ips"].mean(), 4),
            "dr": round(d["dr"].mean(), 4),
            "truth": round(d["truth"].mean(), 4),
            "support": round(d["support"].mean(), 4),
            "dr_lift": [round(v, 4) for v in lift_dr],
            "truth_lift": [round(v, 4) for v in lift_truth],
        }
    out["_logged_mean"] = round(base["logged"].mean(), 4)
    return out


def replay(split: str = "test", names: list[str] | None = None) -> dict[str, Any]:
    """Every buyer on one policy for the whole split, starting from the market as it was."""
    market = _market()
    with open(truth_dir() / f"market_at_{split}.pkl", "rb") as f:
        start_state = pickle.load(f)
    months = set(json.loads((config.data_dir() / "logs" / "summary.json").read_text())["split_months"][split])
    lots = [lot for lot in market.lots if market.month_of(lot) in months]
    pols = policies()
    out: dict[str, Any] = {}
    for name in names or list(pols):
        market.restore_state(start_state)
        state = _state(split)
        pol = pols[name]
        per_lot: list[float] = []
        rows_all = []
        for lot in lots:
            pub = lot.public()
            served = pol.serve(pub, state)
            ids = np.array(served.shortlist, dtype=np.int64)
            per_lot.append(market.value_static(lot, ids, market.day(lot.published)))
            rows = market.serve(lot, served.shortlist, name, False)
            state.record(pub, rows)
            rows_all.extend(rows)
        df = pd.DataFrame(rows_all)
        inv = df[df["invited"]].groupby("firm_id").size().sort_values(ascending=False)
        top = max(1, int(len(market.firms) * 0.01))
        new = _new_share(df, state, lots, market)
        comp = df["bid"] & (df["price_ratio"].fillna(9) <= 1 + config.load("ranking")["competitive_within"])
        out[name] = {
            "expected_competitive_per_lot": round(float(np.mean(per_lot)), 4),
            "realised_competitive_per_lot": round(float(comp.sum() / len(lots)), 4),
            "bids_per_lot": round(float(df["bid"].sum() / len(lots)), 4),
            "invites_per_lot": round(float(df["invited"].sum() / len(lots)), 4),
            "bid_rate": round(float(df["bid"].sum() / max(1, df["invited"].sum())), 4),
            "top1pct_invite_share": round(float(inv.iloc[:top].sum() / max(1, inv.sum())), 4),
            "firms_invited": int(len(inv)),
            "new_firm_slot_share": new,
            "per_lot": per_lot,
        }
    return out


def _new_share(df: pd.DataFrame, state: FeatureState, lots: list, market: Market) -> float:
    joined = {f.idx: f.joined for f in market.firms}
    pub = {lot.idx: lot.published for lot in lots}
    young = [(pub[r.lot_id] - joined[r.firm_id]).days < 180 for r in df.itertuples()]
    return round(float(np.mean(young)), 4) if young else 0.0


def ab_test(split: str = "test", treatment: str = "ranker", seed: int = 5) -> dict[str, Any]:
    """Buyers split 50/50 between the rules and the treatment, as one market (they share the firms)."""
    market = _market()
    with open(truth_dir() / f"market_at_{split}.pkl", "rb") as f:
        start_state = pickle.load(f)
    months = set(json.loads((config.data_dir() / "logs" / "summary.json").read_text())["split_months"][split])
    lots = [lot for lot in market.lots if market.month_of(lot) in months]
    pols = policies()
    rng = np.random.default_rng(seed)
    arm = {b.idx: int(rng.random() < 0.5) for b in market.buyers}
    market.restore_state(start_state)
    state = _state(split)
    per: list[dict[str, Any]] = []

    def choose(lot):  # noqa: ANN001, ANN202
        return pols[treatment] if arm[lot.buyer] else pols["rules"]

    comp_limit = 1 + config.load("ranking")["competitive_within"]

    def on_lot(lot, rows):  # noqa: ANN001, ANN202
        c = sum(1 for r in rows if r["bid"] and r["price_ratio"] <= comp_limit)
        per.append(
            {
                "lot_id": lot.idx,
                "buyer": lot.buyer,
                "arm": arm[lot.buyer],
                "comp": c,
                "week": market.day(lot.published) // 7,
            }
        )

    run(market, lots, choose, state, on_lot)
    df = pd.DataFrame(per)
    pre = _pre_period(market)
    df["pre"] = df["buyer"].map(pre).fillna(np.mean(list(pre.values())) if pre else 0.0)
    return {"lots": len(df), **_analyse(df)}


def _pre_period(market: Market) -> dict[int, float]:
    lots, _, imp = load_logs()
    comp = 1 + config.load("ranking")["competitive_within"]
    tr = imp.merge(lots[["lot_id", "buyer_id", "split"]], on="lot_id")
    tr = tr[tr["split"] == "train"]
    tr = tr.assign(c=tr["bid"] & (tr["price_ratio"].fillna(9) <= comp))
    per_lot = tr.groupby(["buyer_id", "lot_id"])["c"].sum().groupby("buyer_id").mean()
    return per_lot.to_dict()


def _analyse(df: pd.DataFrame) -> dict[str, Any]:
    """Difference in competitive bids per lot, clustered by buyer, plain and with CUPED; sequential looks."""

    def est(d: pd.DataFrame, cuped: bool) -> tuple[float, float]:
        y = d["comp"].to_numpy(float)
        if cuped:
            x = d["pre"].to_numpy(float)
            theta = np.cov(y, x)[0, 1] / max(np.var(x), 1e-9)
            y = y - theta * (x - x.mean())
        d = d.assign(y=y)
        g = d.groupby(["buyer", "arm"])["y"].agg(["sum", "count"]).reset_index()
        means, var = {}, {}
        for a in (0, 1):
            s = g[g["arm"] == a]
            m = s["sum"].sum() / s["count"].sum()
            # cluster-robust variance of a ratio mean (delta method over buyers)
            r = s["sum"] - m * s["count"]
            var[a] = float((r**2).sum() / s["count"].sum() ** 2)
            means[a] = m
        return means[1] - means[0], float(np.sqrt(var[0] + var[1]))

    out: dict[str, Any] = {}
    for name, c in (("plain", False), ("cuped", True)):
        e, se = est(df, c)
        out[name] = {
            "effect": round(e, 4),
            "se": round(se, 4),
            "ci": [round(e - 1.96 * se, 4), round(e + 1.96 * se, 4)],
        }
    weeks = sorted(df["week"].unique())
    looks = [weeks[int(len(weeks) * q) - 1] for q in (0.25, 0.5, 0.75, 1.0)]
    seq = []
    for i, w in enumerate(looks, start=1):
        e, se = est(df[df["week"] <= w], True)
        bound = 1.96 * np.sqrt(len(looks) / i)  # O'Brien-Fleming
        seq.append(
            {
                "look": i,
                "lots": int((df["week"] <= w).sum()),
                "z": round(e / se, 2) if se else 0.0,
                "bound": round(float(bound), 2),
                "stop": bool(se and abs(e / se) > bound),
            }
        )
    out["sequential"] = seq
    return out


def reader_truth(split: str = "test") -> dict[str, Any]:
    from ..text.reader import lot_string, scores

    lots, _, _ = load_logs()
    truth = pd.read_parquet(truth_dir() / "lots.parquet").set_index("lot_id")["trade"]
    t = lots[lots["split"] == split]
    trades = config.trades()
    right = (t["trade_label"].to_numpy() == truth[t["lot_id"]].to_numpy()).mean()
    out: dict[str, Any] = {"buyer_label_right": round(float(right), 4)}
    for kind in ("tfidf", "hash"):
        r = load(f"reader_{kind}.pkl")
        out[kind] = scores(
            list(truth[t["lot_id"]]), r.predict_proba([lot_string(x) for x in t.to_dict("records")]), trades
        )
    return out


def price_quality(split: str = "test") -> dict[str, Any]:
    df = pd.read_parquet(config.runs_dir() / "features.parquet")
    b = df[(df["split"] == split) & df["bid"]]
    price = load("price.pkl")
    Q = price.predict(b[FEATURES].to_numpy())
    y = np.log(b["price_ratio"].to_numpy())
    qs = price.quantiles
    pin = {
        str(q): round(float(np.mean(np.maximum(q * (y - Q[:, j]), (q - 1) * (y - Q[:, j])))), 5)
        for j, q in enumerate(qs)
    }
    inside = float(np.mean((y >= Q[:, 0]) & (y <= Q[:, -1])))
    pc = price.p_competitive(b[FEATURES].to_numpy())
    comp = b["comp"].to_numpy().astype(float)
    return {
        "bids": int(len(b)),
        "pinball": pin,
        f"inside_q{qs[0]}_q{qs[-1]}": round(inside, 4),
        "brier_competitive": round(float(np.mean((pc - comp) ** 2)), 4),
        "brier_base_rate": round(float(np.mean((comp.mean() - comp) ** 2)), 4),
    }


def calibration(split: str = "test", name: str = "torch_pbm") -> dict[str, Any]:
    df = pd.read_parquet(config.runs_dir() / "features.parquet")
    d = df[df["split"] == split]
    exam = load("examination.pkl")
    m = load(f"ranker_{name}.pkl")
    p = exam[d["position"].to_numpy()] * m.relevance(d[FEATURES].to_numpy())
    y = (d["invited"] & d["bid"]).to_numpy().astype(float)
    bins = np.minimum((p * 10).astype(int), 9)
    ece = sum(
        abs(p[bins == b].mean() - y[bins == b].mean()) * (bins == b).mean() for b in range(10) if (bins == b).any()
    )
    return {
        "ece": round(float(ece), 4),
        "mean_predicted": round(float(p.mean()), 4),
        "mean_observed": round(float(y.mean()), 4),
    }


def examination_truth() -> dict[str, Any]:
    market = _market()
    est = load("examination.pkl")
    tru = market.exam(np.arange(len(est)))
    return {
        "estimated": [round(float(v), 3) for v in est],
        "true": [round(float(v), 3) for v in tru],
        "max_abs_error": round(float(np.max(np.abs(est - tru))), 3),
    }


def study(split: str = "test") -> dict[str, Any]:
    t0 = time.time()
    res: dict[str, Any] = {"split": split}
    res["reader"] = reader_truth(split)
    res["examination"] = examination_truth()
    res["calibration"] = calibration(split)
    res["price"] = price_quality(split)
    res["offline"] = offline(split)
    rep = replay(split)
    for v in rep.values():
        v.pop("per_lot", None)
    res["replay"] = rep
    res["ab"] = ab_test(split)
    res["ab"]["true_effect"] = round(
        rep["ranker"]["realised_competitive_per_lot"] - rep["rules"]["realised_competitive_per_lot"], 4
    )
    res["seconds"] = round(time.time() - t0, 1)
    return res
