"""The whole pipeline on a small market: build, train, the study's parts, and that logs carry no truth."""

import pytest

from tests.conftest import needs_runs

pytestmark = [pytest.mark.slow, needs_runs]


def test_logs_carry_no_truth():
    import pandas as pd

    from tmr import config

    d = config.data_dir() / "logs"
    lots = pd.read_parquet(d / "lots.parquet")
    imp = pd.read_parquet(d / "impressions.parquet")
    firms = pd.read_parquet(d / "firms.parquet")
    assert "trade" not in lots.columns and "volume" not in lots.columns  # the true trade and value stay in truth/
    assert not {"p_bid", "responsiveness", "capacity", "price_level"} & (set(imp.columns) | set(firms.columns))


def test_shuffled_lots_measure_the_position_curve():
    from tmr.features.build import load

    exam = load("examination.pkl")
    assert exam[0] == 1.0 and all(a >= b for a, b in zip(exam, exam[1:]))


def test_the_study_summary_has_every_policy():
    import json

    from tmr import config

    s = json.loads((config.runs_dir() / "study_test.json").read_text())
    assert {"rules", "torch_pbm", "ranker"} <= set(s["offline"]) and "true_effect" in s["ab"]
