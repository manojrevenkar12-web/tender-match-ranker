"""Record API responses for the console's browser tests (web/e2e/fixtures). Run after `tmr all`."""

import json
import os
from pathlib import Path

os.environ.setdefault("TMR_STORE", "memory")
os.environ.setdefault("TMR_LLM", "off")

from fastapi.testclient import TestClient  # noqa: E402

from tmr.serving.app import app  # noqa: E402

out = Path(__file__).resolve().parent.parent / "web" / "e2e" / "fixtures"
out.mkdir(parents=True, exist_ok=True)
c = TestClient(app)
lots = c.get("/v1/lots", params={"limit": 25}).json()
lot = next(x for x in lots if len(c.get(f"/v1/lots/{x['lot_id']}/shortlist").json()["firms"]) >= 15)
files = {
    "lots.json": lots,
    "lot.json": c.get(f"/v1/lots/{lot['lot_id']}").json(),
    "shortlist.json": c.get(f"/v1/lots/{lot['lot_id']}/shortlist").json(),
    "results.json": c.get("/v1/experiments").json(),
    "monitoring.json": c.get("/v1/monitoring").json(),
    "plan.json": c.post(
        "/v1/agent/plan", json={"request": (Path(__file__).parent / "plan_request.txt").read_text()}
    ).json(),
}
for name, body in files.items():
    (out / name).write_text(json.dumps(body, ensure_ascii=False, indent=1))
print({k: len(json.dumps(v)) for k, v in files.items()})
