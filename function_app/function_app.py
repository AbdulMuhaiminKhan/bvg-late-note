"""Azure Function: the collector, on a timer.

Every 2 minutes Azure starts this function, it asks the BVG API about the
watched stops and writes the departures to the managed PostgreSQL database.
Nothing runs (and nothing is billed) between runs.

The shared code in ../latenote is copied next to this file at deploy time
by infra/04-function.sh, so the function and the web app use exactly the
same logic.
"""

import logging

import azure.functions as func

from latenote import db
from latenote.bvg import BvgClient
from latenote.collector import collect_once
from latenote.config import get_settings

app = func.FunctionApp()

# Created once per worker and reused between runs (connection pooling).
_settings = get_settings()
_engine = db.make_engine(_settings.database_url)
db.init_db(_engine)


@app.timer_trigger(schedule="0 */2 * * * *", arg_name="timer", run_on_startup=False, use_monitor=True)
def collect(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("collector is running late")
    with BvgClient(_settings.bvg_base_url) as client:
        result = collect_once(_settings, _engine, client)
    logging.info(
        "stops ok=%d failed=%d inserted=%d updated=%d deleted_old=%d",
        result.stops_ok,
        result.stops_failed,
        result.inserted,
        result.updated,
        result.deleted_old,
    )
    if result.stops_ok == 0:
        # Fail loudly so it shows up as a failed run in Azure Monitor.
        raise RuntimeError("BVG API unreachable for every watched stop")
