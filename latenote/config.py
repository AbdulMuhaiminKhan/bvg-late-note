"""Settings come from environment variables only.

Nothing secret is ever hard-coded here. Locally the values come from `.env`
(which is git-ignored); in Azure they come from app settings / Container Apps
secrets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Default stops to watch. IDs come from the BVG API (/locations?query=...),
# checked on 20 Nov 2026. The first two are next to SRH Campus Berlin
# (Sonnenallee 221). Format: "id:Name,id:Name". Override with WATCHED_STOPS.
DEFAULT_WATCHED_STOPS = ",".join(
    [
        "900077106:S Sonnenallee",
        "900077110:S Sonnenallee/Saalestr.",
        "900078101:U Hermannplatz",
        "900100003:S+U Alexanderplatz",
        "900100001:S+U Friedrichstr.",
        "900023201:S+U Zoologischer Garten",
        "900003201:S+U Hauptbahnhof",
    ]
)


def _parse_stops(raw: str) -> dict[str, str]:
    stops: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        stop_id, _, name = part.partition(":")
        stops[stop_id.strip()] = (name or stop_id).strip()
    return stops


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./latenote.db")
    )
    bvg_base_url: str = field(
        default_factory=lambda: os.getenv("BVG_BASE_URL", "https://v6.bvg.transport.rest")
    )
    watched_stops: dict[str, str] = field(
        default_factory=lambda: _parse_stops(os.getenv("WATCHED_STOPS") or DEFAULT_WATCHED_STOPS)
    )
    # How far ahead each collector run looks, in minutes. The collector runs
    # every 2 minutes, so a 10 minute window sees every departure several
    # times and keeps updating its delay until the train leaves.
    window_minutes: int = field(default_factory=lambda: int(os.getenv("WINDOW_MINUTES", "10")))
    # Delete departures older than this many days (cost control).
    retention_days: int = field(default_factory=lambda: int(os.getenv("RETENTION_DAYS", "30")))
    # Public base URL, used in the "check this note" link.
    public_url: str = field(default_factory=lambda: os.getenv("PUBLIC_URL", "http://localhost:8000"))


def get_settings() -> Settings:
    return Settings()
