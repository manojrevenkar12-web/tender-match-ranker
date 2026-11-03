"""Settings live in config/*.yaml; code reads them here."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(os.environ.get("TMR_ROOT", Path(__file__).resolve().parent.parent))


def data_dir() -> Path:
    return Path(os.environ.get("TMR_DATA", ROOT / "data"))


def runs_dir() -> Path:
    return Path(os.environ.get("TMR_RUNS", ROOT / "runs"))


REPORTS = Path(os.environ.get("TMR_REPORTS", ROOT / "reports"))


@cache
def _load(name: str) -> dict[str, Any]:
    with open(ROOT / "config" / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load(name: str) -> dict[str, Any]:
    if name == "world":
        raise PermissionError("config/world.yaml is the simulator's; use tmr.sim.world_config()")
    return _load(name)


def trades() -> list[str]:
    return list(_load("trades")["trades"])
