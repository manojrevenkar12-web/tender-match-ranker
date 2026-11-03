"""The release gate: the shipping ranker against config/release.yaml, from the study on the test months."""

from __future__ import annotations

import json
from typing import Any

from .. import config


def checks() -> list[dict[str, Any]]:
    s = json.loads((config.runs_dir() / "study_test.json").read_text())
    g = config.load("release")["gates"]
    bench_p = config.runs_dir() / "bench.json"
    bench = json.loads(bench_p.read_text()) if bench_p.exists() else {"p95_ms": None}
    off, rep = s["offline"]["ranker"], s["replay"]["ranker"]
    drop = 1 - rep["expected_competitive_per_lot"] / off["truth"] if off["truth"] else 0.0
    rows = [
        ("doubly-robust lift over the rules, 95 % lower bound", off["dr_lift"][1], ">", g["ope_lift_lower_ci"]),
        ("P(invited and bid) calibration error", s["calibration"]["ece"], "<=", g["calibration_ece_max"]),
        (
            "trade reader macro F1, simulated test lots",
            s["reader"]["hash"]["macro_f1"],
            ">=",
            g["trade_reader_macro_f1_min"],
        ),
        (
            "shortlist places for firms under 6 months on the platform (replay)",
            rep["new_firm_slot_share"],
            ">=",
            g["new_firm_exposure_min"],
        ),
        ("invitations to the busiest 1 % of firms (replay)", rep["top1pct_invite_share"], "<=", g["top1pct_share_max"]),
        ("value lost to fatigue, replay vs single-lot", round(drop, 4), "<=", g["replay_value_drop_max"]),
        ("serving p95 latency, ms", bench["p95_ms"], "<=", g["serving_p95_ms_max"]),
    ]
    out = []
    for name, v, op, lim in rows:
        ok = v is not None and {">": v > lim, ">=": v >= lim, "<=": v <= lim}[op]
        out.append({"gate": name, "value": v, "limit": f"{op} {lim}", "pass": bool(ok)})
    return out


def gate() -> bool:
    rows = checks()
    ok = all(r["pass"] for r in rows)
    (config.REPORTS).mkdir(exist_ok=True)
    (config.REPORTS / "release.json").write_text(json.dumps({"ships": ok, "gates": rows}, indent=1))
    lines = [
        "# Release decision: the shipping ranker on the test months",
        "",
        "**Ships.**" if ok else "**Does not ship.**",
        "",
        "| Gate | Value | Limit | Result |",
        "|---|---:|---|---|",
    ]
    lines += [f"| {r['gate']} | {r['value']} | {r['limit']} | {'pass' if r['pass'] else 'FAIL'} |" for r in rows]
    (config.REPORTS / "release.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return ok
