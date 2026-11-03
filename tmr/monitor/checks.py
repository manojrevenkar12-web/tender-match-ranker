"""Daily checks on the live ranker. Each metric has a threshold in config/monitoring.yaml; a breach is an alert."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .. import config
from ..features.state import FEATURES


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population stability index of one feature, on the training deciles."""
    qs = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(qs) < 3:
        return 0.0
    e = np.histogram(np.clip(expected, qs[0], qs[-1]), qs)[0] / len(expected)
    a = np.histogram(np.clip(actual, qs[0], qs[-1]), qs)[0] / max(1, len(actual))
    e, a = np.clip(e, 1e-4, None), np.clip(a, 1e-4, None)
    return float(np.sum((a - e) * np.log(a / e)))


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    b = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(p[b == i].mean() - y[b == i].mean()) * (b == i).mean() for i in range(bins) if (b == i).any()))


def run(live: pd.DataFrame, train: pd.DataFrame, n_firms: int, low_conf_share: float) -> dict[str, Any]:
    """live: one row per shown firm with FEATURES, position, pred (P(invited and bid)), y, invited, new."""
    top = max(1, int(n_firms * 0.01))
    inv = live[live["invited"]].groupby("firm_id").size().sort_values(ascending=False)
    psis = {f: round(psi(train[f].to_numpy(), live[f].to_numpy()), 4) for f in FEATURES}
    worst = max(psis, key=lambda k: psis[k])
    metrics: dict[str, Any] = {
        "bid_rate_vs_predicted": round(float(live["y"].mean() - live["pred"].mean()), 4),
        "calibration_ece": round(ece(live["pred"].to_numpy(), live["y"].to_numpy().astype(float)), 4),
        "feature_psi": psis[worst],
        "feature_psi_worst": worst,
        "top1pct_invite_share": round(float(inv.iloc[:top].sum() / max(1, inv.sum())), 4),
        "new_firm_slot_share": round(float(live["new"].mean()), 4),
        "trade_reader_low_confidence_share": round(low_conf_share, 4),
    }
    alerts = []
    for a in config.load("monitoring")["alerts"]:
        v = metrics[a["metric"]]
        bad = (
            ("max_abs_gap" in a and abs(v) > a["max_abs_gap"])
            or ("max" in a and v > a["max"])
            or ("min" in a and v < a["min"])
        )
        if bad:
            alerts.append(
                {
                    "metric": a["metric"],
                    "value": v,
                    "severity": a["severity"],
                    "limit": {k: a[k] for k in ("max_abs_gap", "max", "min") if k in a},
                }
            )
    return {"metrics": metrics, "psi": psis, "alerts": alerts}
