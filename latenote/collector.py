"""The collector: asks the BVG API about every watched stop and stores the result.

In Azure this runs inside an Azure Function with a timer trigger
(function_app/function_app.py). Locally, `python -m latenote.collector --loop`
does the same job in a container, so docker compose mirrors the cloud setup.
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.engine import Engine

from . import db
from .bvg import BvgClient
from .config import Settings, get_settings

log = logging.getLogger("latenote.collector")


@dataclass
class RunResult:
    stops_ok: int = 0
    stops_failed: int = 0
    inserted: int = 0
    updated: int = 0
    deleted_old: int = 0


def collect_once(settings: Settings, engine: Engine, client: BvgClient, now: datetime | None = None) -> RunResult:
    now = now or datetime.now(timezone.utc)
    result = RunResult()
    for stop_id, name in settings.watched_stops.items():
        try:
            items = client.departures(stop_id, duration_minutes=settings.window_minutes)
        except Exception as exc:  # one bad stop must not stop the others
            log.warning("stop %s (%s) failed: %s", stop_id, name, exc)
            result.stops_failed += 1
            continue
        ins, upd = db.upsert_departures(engine, items, now=now)
        result.inserted += ins
        result.updated += upd
        result.stops_ok += 1
    result.deleted_old = db.delete_old(engine, now - timedelta(days=settings.retention_days))
    log.info("collector run: %s", result)
    return result


def run(loop: bool, interval_s: int) -> None:
    settings = get_settings()
    engine = db.make_engine(settings.database_url)
    db.init_db(engine)
    with BvgClient(settings.bvg_base_url) as client:
        while True:
            collect_once(settings, engine, client)
            if not loop:
                return
            time.sleep(interval_s)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Collect BVG departures into the database")
    parser.add_argument("--loop", action="store_true", help="keep running (local stand-in for the timer function)")
    parser.add_argument("--interval", type=int, default=120, help="seconds between runs when looping")
    args = parser.parse_args()
    run(args.loop, args.interval)


if __name__ == "__main__":
    main()
