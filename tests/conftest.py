import json
from pathlib import Path

import pytest

from latenote import db
from latenote.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def payload():
    return json.loads((FIXTURES / "departures_alexanderplatz.json").read_text())


@pytest.fixture
def settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        bvg_base_url="https://bvg.test",
        watched_stops={"900100003": "S+U Alexanderplatz"},
        public_url="https://latenote.example",
    )


@pytest.fixture
def engine(settings):
    e = db.make_engine(settings.database_url)
    db.init_db(e)
    return e
