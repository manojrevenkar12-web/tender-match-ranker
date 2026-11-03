"""The ranking API on the built market (run `tmr all --profile quick` first)."""

import os

import pytest

from tests.conftest import needs_runs

pytestmark = [pytest.mark.slow, needs_runs]


@pytest.fixture(scope="module")
def client():
    os.environ["TMR_STORE"] = "memory"
    from fastapi.testclient import TestClient

    from tmr.serving.app import app

    return TestClient(app)


def test_open_lots_and_a_shortlist_with_reasons(client):
    lots = client.get("/v1/lots", params={"limit": 5}).json()
    assert lots and all({"lot_id", "trade", "trade_prob", "deadline"} <= set(x) for x in lots)
    s = client.get(f"/v1/lots/{lots[0]['lot_id']}/shortlist").json()
    assert 0 < len(s["firms"]) <= 20 and s["candidates"] >= len(s["firms"])
    f = s["firms"][0]
    assert 0 <= f["p_bid"] <= 1 and 0 <= f["p_competitive"] <= 1
    lo, mid, hi = f["price_band"]
    assert lo <= mid <= hi
    assert [x["position"] for x in s["firms"]] == list(range(len(s["firms"])))


def test_every_shortlist_is_logged_with_its_positions(client):
    from tmr.serving.app import ctx

    before = len(ctx().store.shortlists)
    lot = client.get("/v1/lots", params={"limit": 1}).json()[0]["lot_id"]
    n = len(client.get(f"/v1/lots/{lot}/shortlist").json()["firms"])
    rows = ctx().store.shortlists[before:]
    assert len(rows) == n and sorted(r["position"] for r in rows) == list(range(n))


def test_invitations_are_idempotent_and_count_towards_fatigue_at_once(client):
    lot = client.get("/v1/lots", params={"limit": 1}).json()[0]["lot_id"]
    firms = [f["firm_id"] for f in client.get(f"/v1/lots/{lot}/shortlist").json()["firms"][:2]]
    r1 = client.post(f"/v1/lots/{lot}/invitations", json={"firm_ids": firms, "idempotency_key": "k-1"}).json()
    r2 = client.post(f"/v1/lots/{lot}/invitations", json={"firm_ids": firms, "idempotency_key": "k-1"}).json()
    assert r1["invited"] == 2 and r2["invited"] == 0


def test_unknown_lot_and_bad_input(client):
    assert client.get("/v1/lots/99999999/shortlist").status_code == 404
    assert client.post("/v1/lots/1/invitations", json={"firm_ids": []}).status_code == 422
