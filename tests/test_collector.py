from dataclasses import replace

import httpx

from latenote import db
from latenote.bvg import BvgClient
from latenote.collector import collect_once


def test_collect_once_survives_a_failing_stop(settings, engine, payload):
    settings = replace(settings, watched_stops={"900100003": "Alex", "900000666": "Broken"})

    def handler(request: httpx.Request) -> httpx.Response:
        if "900000666" in request.url.path:
            return httpx.Response(503)
        return httpx.Response(200, json=payload)

    with BvgClient("https://bvg.test", transport=httpx.MockTransport(handler)) as client:
        result = collect_once(settings, engine, client)

    assert result.stops_ok == 1
    assert result.stops_failed == 1
    assert result.inserted == 3
    assert db.counts(engine)["departures"] == 3
