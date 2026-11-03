"""Training and evaluation tables from the logs: one chronological pass through FeatureState."""

from __future__ import annotations

import pickle
from typing import Any

import numpy as np
import pandas as pd

from .. import config
from ..text.reader import HashReader, TfidfReader, corrected_labels, lot_string
from .state import FEATURES, FeatureState


def load_logs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    d = config.data_dir() / "logs"
    return (
        pd.read_parquet(d / "lots.parquet"),
        pd.read_parquet(d / "firms.parquet"),
        pd.read_parquet(d / "impressions.parquet"),
    )


def firm_records(firms: pd.DataFrame) -> list[dict[str, Any]]:
    recs = firms.to_dict("records")
    for r in recs:
        r["trades"] = list(r["trades"])
        if not isinstance(r.get("left"), str):
            r["left"] = None
    return recs


def bidder_mains(imp: pd.DataFrame, firms: pd.DataFrame) -> dict[int, list[str]]:
    main = {r.firm_id: list(r.trades)[0] for r in firms.itertuples()}
    out: dict[int, list[str]] = {}
    for lot_id, f in imp.loc[imp["bid"], ["lot_id", "firm_id"]].itertuples(index=False):
        out.setdefault(int(lot_id), []).append(main[int(f)])
    return out


def reader_probs(
    lots: pd.DataFrame, imp: pd.DataFrame, firms: pd.DataFrame, kind: str = "hash", folds: int = 5
) -> tuple[np.ndarray, Any, list[str]]:
    """Out-of-fold probabilities for training lots, the full model's for later ones (no leakage)."""
    trades = config.trades()
    recs = lots.to_dict("records")
    labels = corrected_labels(recs, bidder_mains(imp, firms))
    texts = [lot_string(r) for r in recs]
    train = (lots["split"] == "train").to_numpy()
    make = HashReader if kind == "hash" else TfidfReader
    probs = np.zeros((len(lots), len(trades)), dtype=np.float32)
    tr_idx = np.where(train)[0]
    fold = (lots["tender_id"].to_numpy()[tr_idx] * 2654435761 % 2**32) % folds  # whole tenders per fold
    for k in range(folds):
        fit_i, out_i = tr_idx[fold != k], tr_idx[fold == k]
        m = make(trades).fit([texts[i] for i in fit_i], [labels[i] for i in fit_i])
        probs[out_i] = m.predict_proba([texts[i] for i in out_i])
    full = make(trades).fit([texts[i] for i in tr_idx], [labels[i] for i in tr_idx])
    rest = np.where(~train)[0]
    probs[rest] = full.predict_proba([texts[i] for i in rest])
    return probs, full, labels


def featurize(
    lots: pd.DataFrame, imp: pd.DataFrame, firms: pd.DataFrame, probs: np.ndarray, start: str
) -> pd.DataFrame:
    import datetime as dt

    state = FeatureState(firm_records(firms), dt.date.fromisoformat(start))
    by_lot = {k: g for k, g in imp.groupby("lot_id", sort=False)}
    order = lots.sort_values(["published", "lot_id"]).index
    blocks = []
    for i in order:
        lot = lots.loc[i].to_dict()
        g = by_lot.get(lot["lot_id"])
        if g is None:
            continue
        p = 0.75 * probs[i] + 0.25 * _one_hot(state, lot["trade_label"])
        ids = g["firm_id"].to_numpy()
        X = state.features(lot, ids, p)
        b = pd.DataFrame(X, columns=FEATURES)
        b["lot_id"] = lot["lot_id"]
        b["firm_id"] = ids
        b["split"] = lot["split"]
        b["month"] = lot["month"]
        for c in ("position", "randomised", "invited", "bid", "price_ratio", "awarded"):
            b[c] = g[c].to_numpy()
        blocks.append(b)
        state.record(lot, g.to_dict("records"))
    df = pd.concat(blocks, ignore_index=True)
    comp = 1.0 + float(config.load("ranking")["competitive_within"])
    df["comp"] = df["bid"] & (df["price_ratio"].fillna(9.0) <= comp)
    return df


def _one_hot(state: FeatureState, label: str) -> np.ndarray:
    v = np.zeros(len(state.trades), dtype=np.float32)
    v[state.t_index[label]] = 1.0
    return v


def save(obj: Any, name: str) -> None:
    d = config.runs_dir()
    d.mkdir(parents=True, exist_ok=True)
    with open(d / name, "wb") as f:
        pickle.dump(obj, f)


def load(name: str) -> Any:
    with open(config.runs_dir() / name, "rb") as f:
        return pickle.load(f)
