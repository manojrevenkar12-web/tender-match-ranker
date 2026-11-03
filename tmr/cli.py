"""tmr: build the market, train, study, report, gate, serve."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tmr")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="simulate the market's history under the current rules")
    b.add_argument("--profile", default="full")
    sub.add_parser("train", help="trade readers, features, examination, rankers, price model")
    s = sub.add_parser("study", help="offline estimates vs truth, market replay, A/B test")
    s.add_argument("--split", default="test")
    sub.add_parser("report", help="write reports/results.json and docs/REPORT.md from runs/study_*.json")
    sub.add_parser("gate", help="the release gate on the test months")
    h = sub.add_parser("heldout", help="the held-out month and blind lot sets; first runs are kept")
    h.add_argument("set", nargs="?", default="month")
    sub.add_parser("agent-eval", help="the invite-planning agent on its eval cases")
    sv = sub.add_parser("serve", help="the ranking API")
    sv.add_argument("--port", type=int, default=8097)
    a = sub.add_parser("all", help="build, train, study, report, gate")
    a.add_argument("--profile", default="full")
    args = ap.parse_args(argv)

    if args.cmd in ("build", "all"):
        from .sim.build import build

        print(json.dumps(build(args.profile)))
    if args.cmd in ("train", "all"):
        from .models.train import train

        print(json.dumps(train()["readers"]))
    if args.cmd in ("study", "all"):
        from . import config
        from .evaluate.study import study

        split = getattr(args, "split", "test")
        r = study(split)
        (config.runs_dir() / f"study_{split}.json").write_text(json.dumps(r, indent=1))
        print(json.dumps({k: r[k] for k in ("reader", "calibration")}))
    if args.cmd in ("report", "all"):
        from .evaluate.report import report

        report()
    if args.cmd in ("gate", "all"):
        from .evaluate.gate import gate

        ok = gate()
        return 0 if ok else 1
    if args.cmd == "heldout":
        from .evaluate.heldout import run_set

        print(json.dumps(run_set(args.set), indent=1))
    if args.cmd == "agent-eval":
        from .agent.evals import run_evals

        print(json.dumps(run_evals(), indent=1))
    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("tmr.serving.app:app", host="127.0.0.1", port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
