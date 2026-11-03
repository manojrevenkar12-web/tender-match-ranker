"""Model calls through the Claude CLI (headless), cached so that CI replays exactly what the model said.

`TMR_LLM=off` replays the cache and treats a miss as "no model": the planner then uses its rules-only path.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from typing import Any

from . import config

CACHE = config.ROOT / "fixtures" / "llm_cache"


def _prompt(step: str) -> str:
    return (config.ROOT / "prompts" / f"{step}.md").read_text(encoding="utf-8")


def structured(step: str, user: str, schema: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any] | None:
    cfg = config.load("agent")
    system = _prompt(step)
    h = hashlib.sha256("\0".join([cfg["model"], system, user, json.dumps(schema, sort_keys=True)]).encode())
    key = h.hexdigest()[:24]
    path = CACHE / f"{key}.json"
    if path.exists():
        raw = json.loads(path.read_text())
        meta["replayed"] = meta.get("replayed", 0) + 1
    else:
        if os.environ.get("TMR_LLM", "on") == "off":
            meta["cache_miss"] = meta.get("cache_miss", 0) + 1
            return None
        with tempfile.TemporaryDirectory(prefix="tmr-claude-") as tmp:
            cmd = [
                "claude",
                "-p",
                user,
                "--model",
                cfg["model"],
                "--output-format",
                "json",
                "--system-prompt",
                system,
                "--tools",
                "",
                "--setting-sources",
                "",
                "--no-session-persistence",
                "--json-schema",
                json.dumps(schema),
                "--max-budget-usd",
                str(cfg["budget_usd"]),
            ]
            p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=300)
        if not p.stdout.strip():
            meta["errors"] = meta.get("errors", 0) + 1
            return None
        raw = json.loads(p.stdout)
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw, ensure_ascii=False))
    meta["calls"] = meta.get("calls", 0) + 1
    meta["cost_usd"] = round(meta.get("cost_usd", 0.0) + float(raw.get("total_cost_usd", 0.0)), 5)
    out = raw.get("structured_output")
    if raw.get("is_error") or not isinstance(out, dict):
        meta["errors"] = meta.get("errors", 0) + 1
        return None
    return out
