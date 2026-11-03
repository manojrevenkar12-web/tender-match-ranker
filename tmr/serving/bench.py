"""Shortlist latency through the API, in process: p50 and p95 over the open lots."""

from __future__ import annotations

import json
import os

import numpy as np

from .. import config


def bench(n: int = 300) -> dict[str, float]:
    os.environ.setdefault("TMR_STORE", "memory")
    from fastapi.testclient import TestClient

    from .app import app, ctx

    c = TestClient(app)
    ids = [x["lot_id"] for x in c.get("/v1/lots", params={"limit": n}).json()]
    c.get(f"/v1/lots/{ids[0]}/shortlist")  # warm up
    ctx().latency.clear()
    for i in ids:
        assert c.get(f"/v1/lots/{i}/shortlist").status_code == 200
    lat = np.array(ctx().latency)
    out = {
        "lots": len(ids),
        "p50_ms": round(float(np.percentile(lat, 50)), 1),
        "p95_ms": round(float(np.percentile(lat, 95)), 1),
    }
    (config.runs_dir() / "bench.json").write_text(json.dumps(out))
    return out
