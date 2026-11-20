import httpx

from latenote.bvg import BvgClient, parse_departures


def test_parses_real_shape_and_skips_broken_items(payload):
    deps = parse_departures(payload, watched_stop_id="900100003")
    assert [d.line for d in deps] == ["N60", "U8", "M4"]

    night_bus, u8, m4 = deps
    assert night_bus.stop_id == "900100031"  # the API can report a sub-stop
    assert night_bus.watched_stop_id == "900100003"
    assert night_bus.stop_name == "S+U Alexanderplatz Bhf/Memhardstr."
    assert night_bus.delay_s is None

    assert u8.delay_s == 720
    assert u8.product == "subway"
    assert u8.direction == "S+U Hermannstr."
    assert (u8.when - u8.planned_when).total_seconds() == 720

    assert m4.cancelled is True
    assert m4.when is None


def test_accepts_bare_list(payload):
    assert len(parse_departures(payload["departures"], "900100003")) == 3


def test_client_calls_departures_endpoint(payload):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["duration"] = request.url.params["duration"]
        seen["ua"] = request.headers["user-agent"]
        return httpx.Response(200, json=payload)

    with BvgClient("https://bvg.test", transport=httpx.MockTransport(handler)) as client:
        deps = client.departures("900100003", duration_minutes=10)

    assert seen == {"path": "/stops/900100003/departures", "duration": "10", "ua": seen["ua"]}
    assert "bvg-late-note" in seen["ua"]
    assert len(deps) == 3
