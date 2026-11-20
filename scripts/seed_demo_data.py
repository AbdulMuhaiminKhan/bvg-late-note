"""Fill a LOCAL database with made-up departures so the pages can be tried
without waiting for the collector. Never run this against the cloud database:
the whole point of the app is that delays are real.

    DATABASE_URL=sqlite:///./demo.db python scripts/seed_demo_data.py
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from latenote import db  # noqa: E402
from latenote.bvg import Departure  # noqa: E402
from latenote.config import get_settings  # noqa: E402

LINES = [("U8", "subway", "S+U Hermannstr.", 0.30), ("U7", "subway", "Rudow", 0.18), ("S41", "suburban", "Ring", 0.35),
         ("M41", "bus", "Sonnenallee/Baumschulenstr.", 0.42), ("M4", "tram", "Zingster Str.", 0.22), ("U2", "subway", "Pankow", 0.12),
         ("S5", "suburban", "Strausberg Nord", 0.26), ("RE1", "regional", "Frankfurt (Oder)", 0.33)]


def main() -> None:
    settings = get_settings()
    if not settings.database_url.startswith("sqlite"):
        sys.exit("Refusing to seed a non-SQLite database. Demo data is for local use only.")
    engine = db.make_engine(settings.database_url)
    db.init_db(engine)
    rng = random.Random(7)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    stops = list(settings.watched_stops.items())
    items = []
    for minutes_ago in range(-20, 7 * 24 * 60, 5):
        for stop_id, stop_name in stops:
            planned = now - timedelta(minutes=minutes_ago)
            line, product, direction, p_late = rng.choice(LINES)
            cancelled = rng.random() < 0.03
            late = rng.random() < p_late
            delay = None if cancelled else (rng.randint(180, 1200) if late else rng.randint(0, 150))
            items.append(Departure(trip_id=f"demo-{stop_id}-{minutes_ago}", watched_stop_id=stop_id, stop_id=stop_id,
                                   stop_name=stop_name, line=line, product=product, direction=direction,
                                   planned_when=planned, when=None if cancelled else planned + timedelta(seconds=delay or 0),
                                   delay_s=delay, cancelled=cancelled))
    print("inserted, updated:", db.upsert_departures(engine, items, now=now))


if __name__ == "__main__":
    main()
