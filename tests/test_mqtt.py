from dataclasses import replace

import httpx

from latenote import db, mqtt
from latenote.bvg import BvgClient, parse_departures
from latenote.sensor import publish_once
from latenote.subscriber import handle


def test_json_round_trip(payload):
    for d in parse_departures(payload, "900100003"):
        assert mqtt.decode(mqtt.encode(d)) == d


def test_topic_per_stop():
    assert mqtt.topic_for("900100003") == "bvg/departures/900100003"
    assert mqtt.TOPIC_ALL == "bvg/departures/#"


def test_sensor_publishes_one_message_per_departure(settings, payload):
    sent = []
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    with BvgClient("https://bvg.test", transport=transport) as client:
        n = publish_once(settings, client, lambda topic, body: sent.append((topic, body)))
    assert n == len(sent) == len(parse_departures(payload, "900100003"))
    assert all(topic == "bvg/departures/900100003" for topic, _ in sent)


def test_subscriber_stores_messages_and_ignores_duplicates(engine, payload):
    messages = [mqtt.encode(d) for d in parse_departures(payload, "900100003")]
    for body in messages + messages:  # QoS 1 may deliver twice
        handle(engine, body)
    assert db.counts(engine)["departures"] == len(messages)


def test_subscriber_skips_bad_messages(engine):
    assert handle(engine, b"not json") == (0, 0)
    assert db.counts(engine)["departures"] == 0
