import asyncio

import pytest

from plugins._pin_to_top.api.get_pins import GetPins
from plugins._pin_to_top.api.toggle_pin import TogglePin
from plugins._pin_to_top.helpers import pins


@pytest.fixture()
def persistent_store(monkeypatch):
    values = {}
    monkeypatch.setattr(
        pins.kvp,
        "get_persistent",
        lambda key, default=None: values.get(key, default),
    )
    monkeypatch.setattr(
        pins.kvp,
        "set_persistent",
        lambda key, value: values.__setitem__(key, value),
    )
    return values


def test_pins_are_persistent_and_separated_by_kind(monkeypatch, persistent_store):
    timestamps = iter((100.0, 200.0))
    monkeypatch.setattr(pins.time, "time", lambda: next(timestamps))

    assert pins.toggle_pin("chat", "chat-1") == (True, 100.0)
    assert pins.toggle_pin("task", "task-1") == (True, 200.0)
    assert pins.get_pins() == {
        "chat": {"chat-1": 100.0},
        "task": {"task-1": 200.0},
    }

    assert pins.toggle_pin("chat", "chat-1") == (False, 0.0)
    assert pins.get_pins()["chat"] == {}


@pytest.mark.parametrize(
    ("kind", "item_id"),
    (("unknown", "item-1"), ("chat", ""), ("task", "x" * 513)),
)
def test_invalid_pin_input_is_rejected(kind, item_id, persistent_store):
    with pytest.raises(ValueError):
        pins.toggle_pin(kind, item_id)


def test_toggle_api_returns_a_bad_request_for_invalid_input(persistent_store):
    response = asyncio.run(
        TogglePin(None, None).process({"kind": "unknown", "item_id": "item-1"}, None)
    )

    assert response.status_code == 400


def test_pin_endpoints_keep_default_auth_and_csrf_protection():
    for handler in (GetPins, TogglePin):
        assert handler.requires_auth() is True
        assert handler.requires_csrf() is True
