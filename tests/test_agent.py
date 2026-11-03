from tmr.agent.planner import de_date, fallback, parse_plain, verify

REQ = """Neubau Kita Leipzig.
Los 1 Trockenbau: Ständerwände CW 75
Los 2 Maler: Dispersionsanstrich
Angebotsfrist 15.12.2026. Mindestens 8 Firmen je Los, max. 60 km, bitte nicht Firma ID 1203."""


def test_the_rules_only_reading_of_a_request():
    r = parse_plain(REQ)
    assert r["city"] == "Leipzig" and r["deadline"] == "2026-12-15"
    assert r["min_invites"] == 8 and r["max_km"] == 60 and r["exclude_firm_ids"] == [1203]
    assert [x["title"] for x in r["lots"]] == ["Los 1 Trockenbau", "Los 2 Maler"]


def test_the_verifier_catches_what_a_model_could_get_wrong():
    req = {"deadline": "2026-12-15", "exclude_firm_ids": [5]}
    lot = {"title": "Los 1 Trockenbau"}
    ok = {"invite": [1, 2, 3], "message": f"Frist {de_date('2026-12-15')}", "escalate": False}
    assert verify(req, lot, ok, [1, 2, 3, 4], 3) == []
    assert verify(req, lot, ok | {"invite": [1, 2, 9]}, [1, 2, 3], 3)  # not offered
    assert verify(req, lot, ok | {"invite": [1, 2, 5]}, [1, 2, 5], 3)  # excluded
    assert verify(req, lot, ok | {"invite": [1]}, [1, 2, 3], 3)  # too few, no reason
    assert verify(req, lot, ok | {"message": "bitte bald"}, [1, 2, 3], 3)  # no deadline
    assert verify(req, lot, ok | {"message": "Frist 15.12.2026, Budget 40.000 €"}, [1, 2, 3], 3)  # an amount


def test_the_fallback_always_passes_the_verifier():
    req = {"deadline": "2027-01-08", "exclude_firm_ids": []}
    lot = {"title": "Los 3"}
    d = fallback(req, lot, [7, 8], 5)
    assert d["escalate"] and verify(req, lot, d, [7, 8], 5) == []
