"""Run a policy through the simulated market, lot by lot, as the live platform would."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..features.state import FeatureState
from ..policy.policies import Policy
from ..sim.market import Lot, Market


def run(
    market: Market,
    lots: list[Lot],
    choose: Callable[[Lot], Policy],
    state: FeatureState,
    on_lot: Callable[[Lot, list[dict[str, Any]]], None] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for lot in lots:
        pub = lot.public()
        policy = choose(lot)
        served = policy.serve(pub, state)
        rows = market.serve(lot, served.shortlist, policy.name, served.randomised)
        state.record(pub, rows)
        out.extend(rows)
        if on_lot:
            on_lot(lot, rows)
    return out
