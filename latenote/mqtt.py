"""MQTT stage of the pipeline (course session 6: device -> broker -> cloud).

The "virtual sensor" (latenote.sensor) watches BVG stops and publishes every
departure it sees as one JSON message to the broker (Mosquitto). The subscriber
(latenote.subscriber) receives the messages and writes them to the database.
The broker decouples the two: the sensor does not know where the data goes.

Topic per watched stop: bvg/departures/<stop_id>, QoS 1 (at least once).
Duplicates are harmless because the database upsert is keyed on
trip + stop + planned time.

Connection settings come from the environment only (no secrets in code):
MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime

from .bvg import Departure

TOPIC_PREFIX = "bvg/departures"
TOPIC_ALL = f"{TOPIC_PREFIX}/#"
QOS = 1


def topic_for(stop_id: str) -> str:
    return f"{TOPIC_PREFIX}/{stop_id}"


def encode(d: Departure) -> bytes:
    data = asdict(d)
    for key in ("planned_when", "when"):
        if data[key] is not None:
            data[key] = data[key].isoformat()
    return json.dumps(data, separators=(",", ":")).encode()


def decode(payload: bytes) -> Departure:
    data = json.loads(payload)
    for key in ("planned_when", "when"):
        if data.get(key):
            data[key] = datetime.fromisoformat(data[key])
    return Departure(**data)


def connect(client_id: str, persistent: bool = False):
    """A connected paho client, configured from the environment.

    persistent=True asks the broker to keep the session (and queued QoS 1
    messages) while this client is offline.
    """
    import paho.mqtt.client as mqtt  # imported here so tests need no broker

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, clean_session=not persistent)
    user = os.getenv("MQTT_USERNAME")
    if user:
        client.username_pw_set(user, os.getenv("MQTT_PASSWORD"))
    client.connect(os.getenv("MQTT_HOST", "localhost"), int(os.getenv("MQTT_PORT", "1883")), keepalive=60)
    return client
