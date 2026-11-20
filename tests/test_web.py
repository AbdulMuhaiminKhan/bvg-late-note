from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from latenote import db
from latenote.bvg import parse_departures
from latenote.web import create_app


@pytest.fixture
def client(settings, engine, payload):
    db.upsert_departures(engine, parse_departures(payload, "900100003"), now=datetime(2026, 11, 20, 8, tzinfo=timezone.utc))
    return TestClient(create_app(settings))


def test_home_shows_form_and_stops(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Which train made you late?" in r.text
    assert "S+U Alexanderplatz" in r.text
    assert r.headers["x-frame-options"] == "DENY"


def test_find_then_make_note_then_view(client):
    r = client.get("/find", params={"line": "U8", "stop": "900100003", "date": "2026-11-20", "time": "09:00"})
    assert r.status_code == 200
    assert "+12 min" in r.text

    dep_id = r.text.split('name="departure_id" value="')[1].split('"')[0]
    r = client.post("/notes", data={"departure_id": dep_id}, follow_redirects=False)
    assert r.status_code == 303
    note_url = r.headers["location"]

    r = client.get(note_url)
    assert r.status_code == 200
    assert "+12" in r.text
    assert "09:04" in r.text and "09:16" in r.text  # Berlin time, not UTC
    assert "https://latenote.example" + note_url in r.text


def test_cancelled_trip_is_shown(client):
    r = client.get("/find", params={"line": "m4", "stop": "900100003", "date": "2026-11-20", "time": "09:10"})
    assert "Cancelled" in r.text


def test_bad_input_gives_clear_errors(client):
    assert client.get("/find", params={"line": "U8", "stop": "123", "date": "2026-11-20", "time": "09:00"}).status_code == 400
    assert client.get("/find", params={"line": "U8", "stop": "900100003", "date": "20.11.", "time": "9"}).status_code == 400
    assert client.post("/notes", data={"departure_id": "999999"}).status_code == 404
    r = client.get("/n/doesnotexist")
    assert r.status_code == 404 and "No note with this code" in r.text


def test_board_and_health(client):
    assert client.get("/board/900100003").status_code == 200
    assert client.get("/board/1").status_code == 404
    h = client.get("/healthz").json()
    assert h["status"] == "ok" and h["departures"] == 3


def test_line_name_is_validated_and_escaped(client):
    assert client.get("/find", params={"line": "x" * 50, "stop": "900100003", "date": "2026-11-20", "time": "09:00"}).status_code == 400
    r = client.get("/find", params={"line": "<b>U8", "stop": "900100003", "date": "2026-11-20", "time": "09:00"})
    assert "<b>U8" not in r.text and "&lt;B&gt;U8" in r.text


def test_note_has_a_ready_to_send_message(client):
    r = client.get("/find", params={"line": "U8", "stop": "900100003", "date": "2026-11-20", "time": "09:00"})
    dep_id = r.text.split('name="departure_id" value="')[1].split('"')[0]
    note_url = client.post("/notes", data={"departure_id": dep_id}, follow_redirects=False).headers["location"]

    r = client.get(note_url)
    link = "https://latenote.example" + note_url
    assert "Sorry, I&#39;m running late: my U-Bahn U8" in r.text
    assert "was 12 minutes late (planned 09:04, left 09:16" in r.text
    assert "Here is the BVG record: " + link in r.text
    assert "https://wa.me/?text=Sorry%2C%20I%27m%20running%20late" in r.text
    assert '<script src="/static/share.js" defer></script>' in r.text
    assert client.get("/static/share.js").status_code == 200


def test_cancelled_note_message_says_cancelled(client):
    r = client.get("/find", params={"line": "m4", "stop": "900100003", "date": "2026-11-20", "time": "09:10"})
    dep_id = r.text.split('name="departure_id" value="')[1].split('"')[0]
    note_url = client.post("/notes", data={"departure_id": dep_id}, follow_redirects=False).headers["location"]
    r = client.get(note_url)
    assert "was cancelled. Here is the BVG record:" in r.text


def test_late_message_wording():
    from datetime import datetime, timezone
    from latenote.web import late_message

    base = {
        "product": "bus", "line": "M41", "direction": "Sonnenallee/Baumschulenstr.",
        "stop_name": "S Sonnenallee", "cancelled": False,
        "planned_when": datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc),
        "actual_when": datetime(2026, 11, 20, 8, 1, tzinfo=timezone.utc),
    }
    on_time = late_message({**base, "delay_s": 0, "max_delay_s": 0}, "L")
    assert on_time.startswith("For the record: my Bus M41") and "left on time at 09:00" in on_time
    assert "0 minutes" not in on_time
    one = late_message({**base, "delay_s": 60, "max_delay_s": 60}, "L")
    assert "was 1 minute late" in one


def test_note_stamp_matches_planned_and_left_times():
    from datetime import datetime, timezone
    from latenote.web import late_message

    # The worst reading was 3 minutes, but the train finally left 2 minutes late.
    note = {
        "product": "bus", "line": "M41", "direction": "Sonnenallee/Baumschulenstr.",
        "stop_name": "S Sonnenallee", "cancelled": False,
        "planned_when": datetime(2026, 11, 20, 4, 19, tzinfo=timezone.utc),
        "actual_when": datetime(2026, 11, 20, 4, 21, tzinfo=timezone.utc),
        "delay_s": 120, "max_delay_s": 180,
    }
    assert "was 2 minutes late (planned 05:19, left 05:21" in late_message(note, "L")
