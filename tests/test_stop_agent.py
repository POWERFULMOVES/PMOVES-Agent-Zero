import threading
from pathlib import Path

import pytest
from flask import Response

from agent import AgentContext
from api.stop import Stop


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _Log:
    def __init__(self) -> None:
        self.progress_calls = []
        self.entries = []

    def set_progress(self, progress: str, *, active: bool) -> None:
        self.progress_calls.append((progress, active))

    def log(self, **kwargs) -> None:
        self.entries.append(kwargs)


class _Context:
    id = "chat-1"

    def __init__(self) -> None:
        self.paused = True
        self.killed = False
        self.log = _Log()

    def is_running(self) -> bool:
        return True

    def kill_process(self) -> None:
        self.killed = True


@pytest.mark.asyncio
async def test_stop_endpoint_cancels_without_replacing_the_run(monkeypatch) -> None:
    context = _Context()
    handler = Stop(app=None, thread_lock=threading.RLock())  # type: ignore[arg-type]

    def use_context(ctxid: str):
        assert ctxid == context.id
        return context

    monkeypatch.setattr(AgentContext, "use", use_context)

    result = await handler.process(
        {"context": context.id}, request=None  # type: ignore[arg-type]
    )

    assert context.killed is True
    assert context.paused is False
    assert context.log.progress_calls == [("", False)]
    assert context.log.entries == [
        {
            "type": "info",
            "content": "Agent process stopped.",
            "finished": True,
        }
    ]
    assert result == {
        "message": "Agent process stopped.",
        "context": context.id,
        "stopped": True,
    }


@pytest.mark.asyncio
async def test_stop_endpoint_requires_an_explicit_context() -> None:
    handler = Stop(app=None, thread_lock=threading.RLock())  # type: ignore[arg-type]

    result = await handler.process({}, request=None)  # type: ignore[arg-type]

    assert isinstance(result, Response)
    assert result.status_code == 400
    assert Stop.requires_auth() is True
    assert Stop.requires_csrf() is True


def test_composer_stop_button_preserves_queue_keyboard_behavior() -> None:
    input_store = (
        PROJECT_ROOT / "webui/components/chat/input/input-store.js"
    ).read_text(encoding="utf-8")
    chat_bar = (
        PROJECT_ROOT / "webui/components/chat/input/chat-bar-input.html"
    ).read_text(encoding="utf-8")

    assert 'if (running && !hasInput) return "stop";' in input_store
    assert 'if (state === "stop") return "Stop agent";' in input_store
    assert 'await globalThis.sendJsonData("/stop", { context });' in input_store
    assert '$store.chatInput.activateSendButton()' in chat_bar
    assert ':aria-label="$store.chatInput.sendButtonTitle"' in chat_bar
    assert "#send-button.stop" in chat_bar

    # Enter keeps using sendMessage(), whose empty-input path sends the queue.
    assert "$event.preventDefault();\n        this.sendMessage();" in input_store
    assert 'return "Press Enter to send queued messages";' in input_store


def test_terminal_stop_info_closes_the_active_process_group() -> None:
    messages_js = (PROJECT_ROOT / "webui/js/messages.js").read_text(encoding="utf-8")

    assert "delete displayKvps.finished;" in messages_js
    assert "if (kvps?.finished) completeLastProcessGroup();" in messages_js
