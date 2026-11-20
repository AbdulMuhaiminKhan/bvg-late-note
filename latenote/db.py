"""Database layer (SQLAlchemy Core).

The same code runs on PostgreSQL (Azure Database for PostgreSQL in the cloud,
a Postgres container with a named volume locally) and on SQLite (tests).
All times are stored in UTC.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    and_,
    create_engine,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from .bvg import Departure

metadata = MetaData()

departures = Table(
    "departures",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trip_id", String(200), nullable=False),
    Column("stop_id", String(40), nullable=False),
    Column("watched_stop_id", String(40), nullable=False, index=True),
    Column("stop_name", String(200), nullable=False),
    Column("line", String(40), nullable=False, index=True),
    Column("product", String(40), nullable=False),
    Column("direction", String(200), nullable=False),
    Column("planned_when", DateTime(timezone=True), nullable=False, index=True),
    Column("actual_when", DateTime(timezone=True)),
    Column("delay_s", Integer),
    Column("max_delay_s", Integer),
    Column("cancelled", Boolean, nullable=False, default=False),
    Column("first_seen", DateTime(timezone=True), nullable=False),
    Column("last_seen", DateTime(timezone=True), nullable=False),
    UniqueConstraint("trip_id", "stop_id", "planned_when", name="uq_departure"),
)

notes = Table(
    "notes",
    metadata,
    Column("id", String(16), primary_key=True),
    Column("departure_id", Integer, ForeignKey("departures.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def utc(dt: datetime | None) -> datetime | None:
    """Return an aware UTC datetime. SQLite gives back naive values."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def make_engine(url: str) -> Engine:
    # Azure's PostgreSQL URLs often start with postgres://; SQLAlchemy wants
    # an explicit driver.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return create_engine(url, pool_pre_ping=True, future=True)


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)


def upsert_departures(engine: Engine, items: list[Departure], now: datetime | None = None) -> tuple[int, int]:
    """Insert new departures and update known ones. Returns (inserted, updated).

    The collector sees each departure several times while it waits at the
    stop. Every time we keep the newest delay, and remember the largest one.
    """
    now = utc(now) or datetime.now(timezone.utc)
    inserted = updated = 0
    with engine.begin() as conn:
        for d in items:
            planned = utc(d.planned_when)
            row = conn.execute(
                select(departures.c.id, departures.c.max_delay_s).where(
                    and_(
                        departures.c.trip_id == d.trip_id,
                        departures.c.stop_id == d.stop_id,
                        departures.c.planned_when == planned,
                    )
                )
            ).first()
            values = {
                "actual_when": utc(d.when),
                "delay_s": d.delay_s,
                "cancelled": d.cancelled,
                "last_seen": now,
            }
            if row is None:
                conn.execute(
                    insert(departures).values(
                        trip_id=d.trip_id,
                        stop_id=d.stop_id,
                        watched_stop_id=d.watched_stop_id,
                        stop_name=d.stop_name,
                        line=d.line,
                        product=d.product,
                        direction=d.direction,
                        planned_when=planned,
                        max_delay_s=d.delay_s,
                        first_seen=now,
                        **values,
                    )
                )
                inserted += 1
            else:
                old_max = row.max_delay_s
                if d.delay_s is not None and (old_max is None or d.delay_s > old_max):
                    values["max_delay_s"] = d.delay_s
                conn.execute(update(departures).where(departures.c.id == row.id).values(**values))
                updated += 1
    return inserted, updated


def find_departures(
    engine: Engine,
    line: str,
    watched_stop_id: str,
    around: datetime,
    window_minutes: int = 30,
) -> list[dict]:
    around = utc(around)
    start, end = around - timedelta(minutes=window_minutes), around + timedelta(minutes=window_minutes)
    with engine.connect() as conn:
        rows = conn.execute(
            select(departures)
            .where(
                and_(
                    func.lower(departures.c.line) == line.strip().lower(),
                    departures.c.watched_stop_id == watched_stop_id,
                    departures.c.planned_when >= start,
                    departures.c.planned_when <= end,
                )
            )
            .order_by(departures.c.planned_when)
        ).mappings()
        return [_row(r) for r in rows]


def get_departure(engine: Engine, departure_id: int) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(select(departures).where(departures.c.id == departure_id)).mappings().first()
        return _row(row) if row else None


def create_note(engine: Engine, departure_id: int, now: datetime | None = None) -> str:
    note_id = secrets.token_urlsafe(6)  # 8 characters, hard to guess
    with engine.begin() as conn:
        conn.execute(
            insert(notes).values(
                id=note_id,
                departure_id=departure_id,
                created_at=utc(now) or datetime.now(timezone.utc),
            )
        )
    return note_id


def get_note(engine: Engine, note_id: str) -> dict | None:
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(notes.c.id.label("note_id"), notes.c.created_at, departures)
                .join(departures, departures.c.id == notes.c.departure_id)
                .where(notes.c.id == note_id)
            )
            .mappings()
            .first()
        )
        return _row(row) if row else None


def hall_of_shame(
    engine: Engine,
    since: datetime,
    late_threshold_s: int = 180,
    min_departures: int = 5,
    limit: int = 15,
    until: datetime | None = None,
) -> list[dict]:
    """Lines ranked by the share of departures that were late (or cancelled).

    Only departures that are already in the past count, so a train that is
    still waiting at the platform does not change the numbers.
    """
    until = utc(until) or datetime.now(timezone.utc)
    is_late = (departures.c.delay_s >= late_threshold_s).cast(Integer)
    is_cancelled = departures.c.cancelled.cast(Integer)
    with engine.connect() as conn:
        rows = conn.execute(
            select(
                departures.c.line,
                departures.c.product,
                func.count().label("total"),
                func.coalesce(func.sum(is_late), 0).label("late"),
                func.coalesce(func.sum(is_cancelled), 0).label("cancelled"),
                func.avg(departures.c.delay_s).label("avg_delay_s"),
                func.max(departures.c.max_delay_s).label("worst_delay_s"),
            )
            .where(and_(departures.c.planned_when >= utc(since), departures.c.planned_when <= until))
            .group_by(departures.c.line, departures.c.product)
        ).mappings()
        result = []
        for r in rows:
            if r["total"] < min_departures:
                continue
            d = dict(r)
            d["late_share"] = (d["late"] + d["cancelled"]) / d["total"]
            d["avg_delay_s"] = float(d["avg_delay_s"] or 0)
            result.append(d)
    result.sort(key=lambda d: (d["late_share"], d["avg_delay_s"]), reverse=True)
    return result[:limit]


def counts(engine: Engine) -> dict:
    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(departures)).scalar_one()
        last = conn.execute(select(func.max(departures.c.last_seen))).scalar_one()
        n_notes = conn.execute(select(func.count()).select_from(notes)).scalar_one()
    return {"departures": total, "last_collected": utc(last), "notes": n_notes}


def delete_old(engine: Engine, older_than: datetime) -> int:
    """Remove old departures that no note points to (keeps the DB small and cheap)."""
    with engine.begin() as conn:
        has_note = select(notes.c.departure_id)
        result = conn.execute(
            delete(departures).where(
                and_(departures.c.planned_when < utc(older_than), departures.c.id.not_in(has_note))
            )
        )
        return result.rowcount or 0


def _row(row) -> dict:
    d = dict(row)
    for key in ("planned_when", "actual_when", "first_seen", "last_seen", "created_at"):
        if key in d:
            d[key] = utc(d[key])
    return d


def find_departures_at(engine: Engine, watched_stop_id: str, start: datetime, end: datetime) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(departures)
            .where(
                and_(
                    departures.c.watched_stop_id == watched_stop_id,
                    departures.c.planned_when >= utc(start),
                    departures.c.planned_when <= utc(end),
                )
            )
            .order_by(departures.c.planned_when)
        ).mappings()
        return [_row(r) for r in rows]
