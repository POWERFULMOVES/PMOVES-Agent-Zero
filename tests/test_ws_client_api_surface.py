import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _get_named_exports(source: str) -> set[str]:
    exports: set[str] = set()

    exports.update(re.findall(r"^export\s+function\s+([A-Za-z0-9_]+)\s*\(", source, flags=re.M))
    exports.update(re.findall(r"^export\s+const\s+([A-Za-z0-9_]+)\s*=", source, flags=re.M))
    exports.update(re.findall(r"^export\s+class\s+([A-Za-z0-9_]+)\s*[\{:]", source, flags=re.M))

    for m in re.findall(r"^export\s*\{([^}]+)\}\s*;?", source, flags=re.M):
        for item in m.split(","):
            item = item.strip()
            if not item:
                continue
            # Handle: `foo as bar`
            parts = item.split()
            if len(parts) >= 3 and parts[-2] == "as":
                exports.add(parts[-1])
            else:
                exports.add(parts[0])

    return exports


def test_websocket_js_exports_minimal_namespaced_api_surface() -> None:
    source = (PROJECT_ROOT / "webui" / "js" / "websocket.js").read_text(encoding="utf-8")
    exports = _get_named_exports(source)

    assert "createNamespacedClient" in exports
    assert "getNamespacedClient" in exports

    assert "broadcast" not in exports
    assert "requestAll" not in exports


def test_completed_state_push_cannot_overwrite_disconnected_mode() -> None:
    source = (
        PROJECT_ROOT / "webui" / "components" / "sync" / "sync-store.js"
    ).read_text(encoding="utf-8")

    apply_end = source.split("await applySnapshot(data.snapshot", 1)[1].split(
        'this._setMode(SYNC_MODES.HEALTHY, "push applied");', 1
    )[0]
    assert "if (!stateSocket.isConnected()) return;" in apply_end


def test_state_push_handlers_are_serialized() -> None:
    source = (
        PROJECT_ROOT / "webui" / "components" / "sync" / "sync-store.js"
    ).read_text(encoding="utf-8")

    subscription = source.split('stateSocket.on("state_push"', 1)[1].split(
        'debug("[syncStore] subscribed to state_push")', 1
    )[0]
    assert "this._pushQueue = this._pushQueue" in subscription
    assert ".then(() => this._handlePush(envelope))" in subscription


def test_partial_snapshot_retains_sidebar_collections_and_extension_shape() -> None:
    source = (PROJECT_ROOT / "webui" / "index.js").read_text(encoding="utf-8")
    request_builder = source.split(
        "export function buildStateRequestPayload", 1
    )[1].split("export async function applySnapshot", 1)[0]

    assert "collections_delta: true" in request_builder
    assert "const hasCollections =" in source
    assert "Array.isArray(snapshot.contexts) && Array.isArray(snapshot.tasks)" in source
    assert "snapshot: extensionSnapshot" in source
    assert "contexts: chatsStore.contexts" in source
    assert "tasks: tasksStore.tasks" in source
    assert "if (hasCollections)" in source
    assert "snapshot.contexts || []" not in source
