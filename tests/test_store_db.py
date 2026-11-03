"""The serving log in PostgreSQL: append-only, idempotent invitations."""

import os
import uuid

import pytest

pytestmark = pytest.mark.db
URL = os.environ.get("TMR_TEST_DATABASE_URL")


@pytest.mark.skipif(not URL, reason="needs TMR_TEST_DATABASE_URL")
def test_log_is_append_only_and_invitations_idempotent():
    import psycopg

    from tmr.serving.store import Postgres

    s = Postgres(URL)
    lot = int(uuid.uuid4().int % 10**9)
    s.log_shortlist(
        [
            {
                "lot_id": lot,
                "policy": "ranker",
                "model_version": "t",
                "randomised": False,
                "firm_id": 1,
                "position": 0,
                "score": 0.5,
                "p_bid": 0.4,
                "p_competitive": 0.6,
            }
        ]
    )
    with pytest.raises(psycopg.errors.RaiseException):
        s.conn.execute("update shortlist_log set score = 1 where lot_id = %s", (lot,))
    with pytest.raises(psycopg.errors.RaiseException):
        s.conn.execute("delete from shortlist_log where lot_id = %s", (lot,))
    key = uuid.uuid4().hex
    assert s.invite(lot, [1, 2], "buyer", key) == 2
    assert s.invite(lot, [1, 2, 3], "buyer", key) == 1
    assert s.invited_recently([1, 2, 3], 14)[1] >= 1
