import os

import pytest

from tmr import config

os.environ.setdefault("TMR_LLM", "off")


def have_runs() -> bool:
    return (config.runs_dir() / "ranker_torch_pbm.pkl").exists() and (
        config.data_dir() / "logs" / "lots.parquet"
    ).exists()


needs_runs = pytest.mark.skipif(not have_runs(), reason="needs `tmr all` (data/ and runs/)")
