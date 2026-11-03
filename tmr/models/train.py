"""Train everything from the logs: the trade readers, the feature table, examination, rankers, price model."""

from __future__ import annotations

import json
import time
from typing import Any

import numpy as np

from .. import config
from ..features.build import featurize, load_logs, reader_probs, save
from ..features.state import FEATURES
from ..text.reader import scores
from .ranker import LambdaMART, OutcomeModel, PriceModel, TorchRanker, examination


def train() -> dict[str, Any]:
    t0 = time.time()
    lots, firms, imp = load_logs()
    trades = config.trades()
    report: dict[str, Any] = {"readers": {}}
    probs = {}
    for kind in ("tfidf", "hash"):
        p, model, labels = reader_probs(lots, imp, firms, kind)
        probs[kind] = p
        save(model, f"reader_{kind}.pkl")
        test = (lots["split"] == "test").to_numpy()
        report["readers"][kind] = {  # against the corrected labels: what the platform can see
            "test": scores([labels[i] for i in np.where(test)[0]], p[test], trades),
        }
    t_reader = time.time()
    start = json.loads((config.data_dir() / "logs" / "summary.json").read_text()).get("start")
    df = featurize(lots, imp, firms, probs["hash"], start or _start(lots))
    df.to_parquet(config.runs_dir() / "features.parquet", index=False)
    save({"probs": probs["hash"], "lot_ids": lots["lot_id"].to_numpy()}, "lot_trade_probs.pkl")
    k = int(config.load("ranking")["shortlist"])
    exam = examination(df, k)
    save(exam, "examination.pkl")
    tr = df[df["split"] == "train"]
    X, pos = tr[FEATURES].to_numpy(), tr["position"].to_numpy()
    y = (tr["invited"] & tr["bid"]).to_numpy()
    bids = tr[tr["bid"]]
    price = PriceModel(list(config.load("models")["price"]["quantiles"])).fit(
        bids[FEATURES].to_numpy(), bids["price_ratio"].to_numpy()
    )
    save(price, "price.pkl")
    cw = float(config.load("ranking")["utility"]["competitive_weight"])
    models: dict[str, Any] = {
        "torch_naive": TorchRanker("torch_naive", None, price=price, competitive_weight=cw).fit(X, y, pos),
        "torch_pbm": TorchRanker("torch_pbm", exam, price=price, competitive_weight=cw).fit(X, y, pos),
        "lambdamart": LambdaMART("lambdamart", debias=False).fit(tr),
        "lambdamart_debiased": LambdaMART("lambdamart_debiased", debias=True).fit(tr),
    }
    for name, m in models.items():
        save(m, f"ranker_{name}.pkl")
    save(OutcomeModel().fit(tr), "outcome_dm.pkl")
    report.update(
        {
            "rows": {"train": int(len(tr)), "all": int(len(df))},
            "examination": [round(float(v), 4) for v in exam],
            "seconds": {"readers": round(t_reader - t0, 1), "total": round(time.time() - t0, 1)},
        }
    )
    (config.runs_dir() / "train.json").write_text(json.dumps(report, indent=1))
    return report


def _start(lots) -> str:  # noqa: ANN001
    return min(lots["published"])
