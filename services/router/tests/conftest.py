import pytest

from src import main
from src.control_cache import ControlCache


@pytest.fixture(autouse=True)
def isolated_control_cache(monkeypatch):
    monkeypatch.setattr(main.app.state, "control_cache", ControlCache())
