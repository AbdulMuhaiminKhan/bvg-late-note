"""Small client for the free BVG timetable API (https://v6.bvg.transport.rest).

The API wraps the official BVG/VBB data. It needs no key, but allows only
about 100 requests per minute. That limit drives the whole design: only the
collector calls this API, on a timer, and users read from our own database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

USER_AGENT = "bvg-late-note (student cloud computing project)"


@dataclass(frozen=True)
class Departure:
    trip_id: str
    watched_stop_id: str  # the stop we asked about
    stop_id: str  # the exact stop/platform area the API reports
    stop_name: str
    line: str
    product: str  # subway, suburban, bus, tram, regional, ...
    direction: str
    planned_when: datetime
    when: datetime | None  # None when cancelled
    delay_s: int | None  # None when there is no real-time data
    cancelled: bool


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _clean_name(name: str) -> str:
    # "S+U Alexanderplatz Bhf (Berlin)" -> "S+U Alexanderplatz Bhf"
    return name.removesuffix(" (Berlin)")


def parse_departures(payload: Any, watched_stop_id: str) -> list[Departure]:
    """Turn the API response into Departure objects.

    v6 returns {"departures": [...], "realtimeDataUpdatedAt": ...}; older
    versions returned a bare list, so both are accepted.
    """
    items = payload.get("departures", []) if isinstance(payload, dict) else payload
    result: list[Departure] = []
    for item in items or []:
        planned = _parse_time(item.get("plannedWhen"))
        trip_id = item.get("tripId")
        if planned is None or not trip_id:
            continue
        stop = item.get("stop") or {}
        line = item.get("line") or {}
        cancelled = bool(item.get("cancelled", False))
        delay = item.get("delay")
        result.append(
            Departure(
                trip_id=trip_id,
                watched_stop_id=watched_stop_id,
                stop_id=str(stop.get("id") or watched_stop_id),
                stop_name=_clean_name(stop.get("name") or watched_stop_id),
                line=line.get("name") or "?",
                product=line.get("product") or "unknown",
                direction=item.get("direction") or "",
                planned_when=planned,
                when=_parse_time(item.get("when")),
                delay_s=int(delay) if delay is not None else None,
                cancelled=cancelled,
            )
        )
    return result


class BvgClient:
    def __init__(self, base_url: str, timeout: float = 15.0, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )

    def departures(self, stop_id: str, duration_minutes: int = 10) -> list[Departure]:
        response = self._client.get(
            f"/stops/{stop_id}/departures",
            params={"duration": duration_minutes, "remarks": "false", "results": 200},
        )
        response.raise_for_status()
        return parse_departures(response.json(), watched_stop_id=stop_id)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BvgClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
