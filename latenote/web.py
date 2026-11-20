"""The web app users see. It only reads from our own database; it never calls
the BVG API, so 10,000 users cost the BVG API nothing extra."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from . import __version__, db
from .config import Settings, get_settings

BERLIN = ZoneInfo("Europe/Berlin")
HERE = Path(__file__).parent

PRODUCT_NAMES = {
    "subway": "U-Bahn",
    "suburban": "S-Bahn",
    "tram": "Tram",
    "bus": "Bus",
    "regional": "Regional train",
    "express": "Long-distance train",
    "ferry": "Ferry",
}


def berlin(dt: datetime | None) -> datetime | None:
    return db.utc(dt).astimezone(BERLIN) if dt else None


def hhmm(dt: datetime | None) -> str:
    return berlin(dt).strftime("%H:%M") if dt else "–"


def day(dt: datetime | None) -> str:
    return berlin(dt).strftime("%a %d %b %Y") if dt else "–"


def late_message(note: dict, link: str) -> str:
    """The text a user copies and sends: what happened, plus the link that proves it."""
    train = f"{PRODUCT_NAMES.get(note['product'], '').strip()} {note['line']}".strip()
    when = f"{day(note['planned_when'])}, {hhmm(note['planned_when'])}"
    if note["cancelled"]:
        what = f"my {train} to {note['direction']} from {note['stop_name']} ({when}) was cancelled"
    else:
        m = minutes(note["delay_s"] if note["delay_s"] is not None else note["max_delay_s"]) or 0
        trip = f"my {train} to {note['direction']} from {note['stop_name']}"
        if m <= 0:
            # Honest even when the train was on time: the note records it, it does not excuse it.
            return (
                f"For the record: {trip} left on time at {hhmm(note['planned_when'])} "
                f"({day(note['planned_when'])}). Here is the BVG record: {link}"
            )
        unit = "minute" if m == 1 else "minutes"
        what = (
            f"{trip} was {m} {unit} late "
            f"(planned {hhmm(note['planned_when'])}, left {hhmm(note['actual_when'])}, {day(note['planned_when'])})"
        )
    return f"Sorry, I'm running late: {what}. Here is the BVG record: {link}"


def minutes(delay_s: int | None) -> int | None:
    return None if delay_s is None else round(delay_s / 60)


def ago(dt: datetime | None, now: datetime | None = None) -> str:
    if dt is None:
        return "never"
    secs = int(((now or datetime.now(timezone.utc)) - db.utc(dt)).total_seconds())
    if secs < 90:
        return "just now"
    if secs < 3600:
        return f"{secs // 60} minutes ago"
    if secs < 172800:
        return f"{secs // 3600} hours ago"
    return f"{secs // 86400} days ago"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = db.make_engine(settings.database_url)
    db.init_db(engine)

    app = FastAPI(title="BVG Late Note", version=__version__, docs_url=None, redoc_url=None)
    app.state.engine = engine
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.globals.update(
        hhmm=hhmm,
        day=day,
        minutes=minutes,
        ago=ago,
        product_name=lambda p: PRODUCT_NAMES.get(p, p),
        stops=settings.watched_stops,
        version=__version__,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data:"
        )
        return response

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        now = datetime.now(timezone.utc)
        shame = db.hall_of_shame(engine, since=now - timedelta(days=7))
        local_now = now.astimezone(BERLIN)
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "shame": shame,
                "stats": db.counts(engine),
                "today": local_now.strftime("%Y-%m-%d"),
                "time_now": local_now.strftime("%H:%M"),
            },
        )

    @app.get("/find", response_class=HTMLResponse)
    def find(request: Request, line: str, stop: str, date: str, time: str):
        if stop not in settings.watched_stops:
            raise HTTPException(400, "Pick one of the stops in the list.")
        if not line.strip() or len(line) > 10:
            raise HTTPException(400, "Enter a line name like U8, M41 or S42.")
        try:
            local = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=BERLIN)
        except ValueError:
            raise HTTPException(400, "Use a date like 2026-11-20 and a time like 08:45.")
        found = db.find_departures(engine, line=line, watched_stop_id=stop, around=local)
        return templates.TemplateResponse(
            request,
            "find.html",
            {"found": found, "line": line.strip(), "stop_name": settings.watched_stops[stop], "when": local},
        )

    @app.post("/notes")
    def make_note(departure_id: int = Form(...)):
        if db.get_departure(engine, departure_id) is None:
            raise HTTPException(404, "That departure is not in our records.")
        note_id = db.create_note(engine, departure_id)
        return RedirectResponse(f"/n/{note_id}", status_code=303)

    @app.get("/n/{note_id}", response_class=HTMLResponse)
    def show_note(request: Request, note_id: str):
        note = db.get_note(engine, note_id)
        if note is None:
            raise HTTPException(404, "No note with this code. Check the link.")
        link = f"{settings.public_url.rstrip('/')}/n/{note_id}"
        message = late_message(note, link)
        return templates.TemplateResponse(
            request,
            "note.html",
            {"n": note, "link": link, "message": message, "message_q": quote(message)},
        )

    @app.get("/board/{stop_id}", response_class=HTMLResponse)
    def board(request: Request, stop_id: str):
        """Departures we collected for one stop, around now."""
        if stop_id not in settings.watched_stops:
            raise HTTPException(404, "We don't watch this stop.")
        now = datetime.now(timezone.utc)
        rows = [
            r
            for r in db.find_departures_at(engine, stop_id, now - timedelta(minutes=10), now + timedelta(minutes=20))
        ]
        return templates.TemplateResponse(
            request,
            "board.html",
            {"rows": rows, "stop_id": stop_id, "stop_name": settings.watched_stops[stop_id]},
        )

    @app.get("/healthz")
    def health():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            stats = db.counts(engine)
        except Exception as exc:  # pragma: no cover - only when the DB is down
            return JSONResponse({"status": "db-error", "detail": type(exc).__name__}, status_code=503)
        last = stats["last_collected"]
        return {
            "status": "ok",
            "version": __version__,
            "departures": stats["departures"],
            "notes": stats["notes"],
            "last_collected": last.isoformat() if last else None,
        }

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return templates.TemplateResponse(
            request, "error.html", {"message": exc.detail, "code": exc.status_code}, status_code=exc.status_code
        )

    return app
