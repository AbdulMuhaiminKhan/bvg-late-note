from dataclasses import replace
from datetime import datetime, timedelta, timezone

from latenote import db
from latenote.bvg import parse_departures

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)


def test_upsert_is_idempotent_and_keeps_latest_and_max_delay(engine, payload):
    deps = parse_departures(payload, "900100003")
    assert db.upsert_departures(engine, deps, now=NOW) == (3, 0)
    assert db.upsert_departures(engine, deps, now=NOW) == (0, 3)

    u8 = deps[1]
    # The train makes up 2 minutes before it leaves: latest delay 600, max stays 720.
    db.upsert_departures(engine, [replace(u8, delay_s=600)], now=NOW + timedelta(minutes=2))
    found = db.find_departures(engine, "u8", "900100003", around=u8.planned_when)
    assert len(found) == 1
    assert found[0]["delay_s"] == 600
    assert found[0]["max_delay_s"] == 720
    assert db.counts(engine)["departures"] == 3


def test_find_matches_line_case_insensitive_within_window(engine, payload):
    deps = parse_departures(payload, "900100003")
    db.upsert_departures(engine, deps, now=NOW)
    planned = deps[1].planned_when
    assert len(db.find_departures(engine, " U8 ", "900100003", planned + timedelta(minutes=25))) == 1
    assert db.find_departures(engine, "U8", "900100003", planned + timedelta(minutes=45)) == []
    assert db.find_departures(engine, "U8", "900000000", planned) == []


def test_notes_round_trip(engine, payload):
    deps = parse_departures(payload, "900100003")
    db.upsert_departures(engine, deps, now=NOW)
    dep_id = db.find_departures(engine, "U8", "900100003", deps[1].planned_when)[0]["id"]
    note_id = db.create_note(engine, dep_id)
    assert len(note_id) == 8
    note = db.get_note(engine, note_id)
    assert note["line"] == "U8" and note["max_delay_s"] == 720
    assert note["planned_when"].tzinfo is not None
    assert db.get_note(engine, "nope") is None


def test_hall_of_shame_ranks_by_late_share(engine, payload):
    base = parse_departures(payload, "900100003")[1]  # U8
    start = datetime(2026, 11, 19, 6, 0, tzinfo=timezone.utc)
    items = []
    for i in range(10):  # U8: 4 of 10 late
        items.append(replace(base, trip_id=f"u8-{i}", planned_when=start + timedelta(minutes=10 * i),
                             delay_s=600 if i < 4 else 30))
    for i in range(6):  # U2: 1 of 6 late
        items.append(replace(base, trip_id=f"u2-{i}", line="U2", planned_when=start + timedelta(minutes=7 * i),
                             delay_s=240 if i == 0 else 0))
    for i in range(3):  # too few to rank
        items.append(replace(base, trip_id=f"u6-{i}", line="U6", planned_when=start, delay_s=900))
    db.upsert_departures(engine, items, now=start)

    shame = db.hall_of_shame(engine, since=start - timedelta(days=1), until=start + timedelta(days=1))
    assert [r["line"] for r in shame] == ["U8", "U2"]
    assert shame[0]["late"] == 4 and shame[0]["total"] == 10
    assert abs(shame[0]["late_share"] - 0.4) < 1e-9


def test_delete_old_keeps_departures_with_notes(engine, payload):
    deps = parse_departures(payload, "900100003")
    db.upsert_departures(engine, deps, now=NOW)
    keep_id = db.find_departures(engine, "U8", "900100003", deps[1].planned_when)[0]["id"]
    db.create_note(engine, keep_id)
    removed = db.delete_old(engine, older_than=datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert removed == 2
    assert db.counts(engine)["departures"] == 1


def test_reading_without_realtime_keeps_known_delay(engine, payload):
    u8 = parse_departures(payload, "900100003")[1]
    db.upsert_departures(engine, [u8], now=NOW)
    db.upsert_departures(engine, [replace(u8, delay_s=None, when=u8.planned_when)], now=NOW + timedelta(minutes=2))
    row = db.find_departures(engine, "U8", "900100003", u8.planned_when)[0]
    assert row["delay_s"] == 720
    assert row["actual_when"] == u8.when
