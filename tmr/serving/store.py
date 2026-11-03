"""Where the serving log goes: PostgreSQL in production, memory for local demos and browser tests."""

from __future__ import annotations

import os
from typing import Any, Protocol

from .. import config


class Store(Protocol):
    def log_shortlist(self, rows: list[dict[str, Any]]) -> None: ...

    def invite(self, lot_id: int, firm_ids: list[int], by: str, key: str) -> int: ...

    def invited_recently(self, firm_ids: list[int], days: int) -> dict[int, int]: ...


class Memory:
    def __init__(self) -> None:
        self.shortlists: list[dict[str, Any]] = []
        self.invitations: dict[tuple[str, int], dict[str, Any]] = {}

    def log_shortlist(self, rows: list[dict[str, Any]]) -> None:
        self.shortlists.extend(rows)

    def invite(self, lot_id: int, firm_ids: list[int], by: str, key: str) -> int:
        new = 0
        for f in firm_ids:
            if (key, f) not in self.invitations:
                self.invitations[(key, f)] = {"lot_id": lot_id, "firm_id": f, "by": by}
                new += 1
        return new

    def invited_recently(self, firm_ids: list[int], days: int) -> dict[int, int]:
        out: dict[int, int] = {}
        for v in self.invitations.values():
            if v["firm_id"] in firm_ids:
                out[v["firm_id"]] = out.get(v["firm_id"], 0) + 1
        return out


class Postgres:
    def __init__(self, url: str) -> None:
        import psycopg

        self.url = url
        self.conn = psycopg.connect(url, autocommit=True)
        self.conn.execute((config.ROOT / "migrations" / "0001_init.sql").read_text())

    def log_shortlist(self, rows: list[dict[str, Any]]) -> None:
        with self.conn.cursor() as cur:
            cur.executemany(
                "insert into shortlist_log (lot_id, policy, model_version, randomised, firm_id, position, score, p_bid,"
                " p_competitive) values (%(lot_id)s, %(policy)s, %(model_version)s, %(randomised)s, %(firm_id)s,"
                " %(position)s, %(score)s, %(p_bid)s, %(p_competitive)s)",
                rows,
            )

    def invite(self, lot_id: int, firm_ids: list[int], by: str, key: str) -> int:
        with self.conn.cursor() as cur:
            n = 0
            for f in firm_ids:
                cur.execute(
                    "insert into invitations (lot_id, firm_id, invited_by, idempotency_key) values (%s, %s, %s, %s)"
                    " on conflict (idempotency_key, firm_id) do nothing",
                    (lot_id, f, by, key),
                )
                n += cur.rowcount
            return n

    def invited_recently(self, firm_ids: list[int], days: int) -> dict[int, int]:
        rows = self.conn.execute(
            "select firm_id, count(*) from invitations"
            " where firm_id = any(%s) and at > now() - make_interval(days => %s) group by firm_id",
            (firm_ids, days),
        ).fetchall()
        return {int(a): int(b) for a, b in rows}


def make() -> Store:
    url = os.environ.get("TMR_DATABASE_URL")
    if url:
        return Postgres(url)
    if os.environ.get("TMR_STORE") == "memory":
        return Memory()
    raise RuntimeError("set TMR_DATABASE_URL (or TMR_STORE=memory for a local demo)")
