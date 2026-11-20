"""The virtual sensor: polls the watched BVG stops and publishes to MQTT.

    python -m latenote.sensor            # one round
    python -m latenote.sensor --loop     # every 2 minutes
"""

from __future__ import annotations

import argparse
import logging
import time

from . import mqtt
from .bvg import BvgClient
from .config import get_settings

log = logging.getLogger("latenote.sensor")


def publish_once(settings, client: BvgClient, publish) -> int:
    """Read every watched stop and publish each departure. Returns messages sent."""
    sent = 0
    for stop_id, name in settings.watched_stops.items():
        try:
            items = client.departures(stop_id, duration_minutes=settings.window_minutes)
        except Exception as exc:  # one bad stop must not stop the others
            log.warning("stop %s (%s) failed: %s", stop_id, name, exc)
            continue
        for d in items:
            publish(mqtt.topic_for(stop_id), mqtt.encode(d))
            sent += 1
    log.info("sensor round: published %d messages", sent)
    return sent


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Publish BVG departures to MQTT")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=120)
    args = parser.parse_args()

    settings = get_settings()
    broker = mqtt.connect("latenote-sensor")
    broker.loop_start()

    def publish(topic: str, payload: bytes) -> None:
        broker.publish(topic, payload, qos=mqtt.QOS)

    with BvgClient(settings.bvg_base_url) as client:
        while True:
            publish_once(settings, client, publish)
            if not args.loop:
                break
            time.sleep(args.interval)
    broker.loop_stop()
    broker.disconnect()


if __name__ == "__main__":
    main()
