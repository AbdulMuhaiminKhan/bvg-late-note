"""Subscribes to bvg/departures/# and writes every message to the database.

    python -m latenote.subscriber
"""

from __future__ import annotations

import logging
import time

from sqlalchemy.engine import Engine

from . import db, mqtt
from .config import get_settings

log = logging.getLogger("latenote.subscriber")


def handle(engine: Engine, payload: bytes) -> tuple[int, int]:
    """Store one MQTT message. Bad messages are logged and skipped."""
    try:
        departure = mqtt.decode(payload)
    except Exception as exc:
        log.warning("skipping bad message: %s", exc)
        return (0, 0)
    return db.upsert_departures(engine, [departure])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    engine = db.make_engine(settings.database_url)
    try:
        db.init_db(engine)
    except Exception:  # another container created the tables at the same moment
        time.sleep(3)
        db.init_db(engine)
    stored = {"n": 0}

    def on_connect(client, userdata, flags, reason_code, properties):
        log.info("connected (%s), subscribing to %s", reason_code, mqtt.TOPIC_ALL)
        client.subscribe(mqtt.TOPIC_ALL, qos=mqtt.QOS)

    def on_message(client, userdata, msg):
        handle(engine, msg.payload)
        stored["n"] += 1
        if stored["n"] % 50 == 0:
            log.info("stored %d messages so far", stored["n"])

    # Persistent session: the broker keeps QoS 1 messages while we are offline.
    client = mqtt.connect("latenote-subscriber", persistent=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.loop_forever()


if __name__ == "__main__":
    main()
