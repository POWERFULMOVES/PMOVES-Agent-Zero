import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ui_controls_have_independent_mobile_and_desktop_visibility() -> None:
    preferences = read("webui/components/sidebar/bottom/preferences/preferences-store.js")
    settings_store = read("webui/components/settings/settings-store.js")
    settings = read("webui/components/settings/agent/agent-settings.html")
    interface = read("webui/components/settings/agent/interface.html")
    chat_top = read("webui/components/chat/top-section/chat-top.html")
    canvas = read("webui/components/canvas/right-canvas.html")
    context_usage = read(
        "plugins/_context_window/extensions/webui/model-context-strip-end/context-window.html"
    )
    context_settings = read(
        "plugins/_context_window/extensions/webui/interface-controls-end/context-window.html"
    )
    context_store = read("plugins/_context_window/webui/context-window-store.js")
    index = read("webui/index.html")
    ui_server = read("helpers/ui_server.py")

    for control in ("projectSelector", "time", "connectionStatus", "rightCanvasRail"):
        assert control in preferences
        assert control in settings_store

    assert "registerUiControlVisibility" in preferences
    assert "contextWindowUsage" in context_store
    assert "contextWindowUsage" in context_settings
    assert 'id="interface-controls-end"' in interface

    assert "section-interface" in settings_store
    assert 'settings/agent/interface.html' in settings
    assert "smartphone" in interface
    assert "desktop_windows" in interface
    assert 'globalThis.addEventListener("resize"' in preferences
    assert "uiControlVisibility" in index
    assert "user_ui_control_visibility" in ui_server
    assert "ui_control_visibility" in settings_store
    assert "Shown everywhere" in settings_store
    assert "Mobile only" in settings_store
    assert "Desktop only" in settings_store
    assert "Hidden everywhere" in settings_store
    assert "isUiControlVisible('time')" in chat_top
    assert "isUiControlVisible('connectionStatus')" in chat_top
    assert "isUiControlVisible('projectSelector')" in chat_top
    assert "isUiControlVisible('contextWindowUsage')" in context_usage
    assert "isUiControlVisible('rightCanvasRail')" in canvas


def test_mobile_canvas_rail_respects_visibility_preference() -> None:
    canvas = read("webui/components/canvas/right-canvas.html")
    canvas_css = read("webui/components/canvas/right-canvas.css")
    mobile_rail_rule = re.search(
        r"body\.right-canvas-mobile-mode \.right-canvas-rail \{([^}]*)\}",
        canvas_css,
        re.S,
    )

    assert 'x-show="$store.preferences.isUiControlVisible(\'rightCanvasRail\')"' in canvas
    assert mobile_rail_rule is not None
    assert re.search(r"^\s*display:\s*flex;\s*$", mobile_rail_rule.group(1), re.M)
    assert "!important" not in mobile_rail_rule.group(1)


def test_ui_control_visibility_settings_are_normalized() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
from helpers import settings

defaults = settings.get_default_settings()["ui_control_visibility"]
normalized = settings.normalize_settings({
    **settings.get_default_settings(),
    "ui_control_visibility": {
        "time": {"mobile": True, "desktop": False},
        "contextWindowUsage": {"mobile": False, "desktop": True},
        "projectSelector": "invalid",
        "unknown": {"mobile": False},
    },
})["ui_control_visibility"]
print(json.dumps({"defaults": defaults, "normalized": normalized}))
""",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    defaults = data["defaults"]
    normalized = data["normalized"]

    assert defaults["time"] == {"mobile": False, "desktop": True}
    assert normalized["time"] == {"mobile": True, "desktop": False}
    assert normalized["contextWindowUsage"] == {"mobile": False, "desktop": True}
    assert normalized["projectSelector"] == {"mobile": True, "desktop": True}
    assert "unknown" not in normalized
