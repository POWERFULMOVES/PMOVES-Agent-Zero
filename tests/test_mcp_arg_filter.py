"""filter_declared_args drops schema-undeclared keys before MCP tool calls.

Models following the advertised input schema sometimes emit optional keys the
schema never declared (observed: 'action' into postgrestRequest, 'tags' into
session_recall); strict servers reject the whole call over them.
"""
from __future__ import annotations
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from helpers.mcp_handler import filter_declared_args


TOOLS = [
    {
        "name": "postgrestRequest",
        "description": "query",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "method": {"type": "string"}},
        },
    },
    {"name": "no_schema_tool", "description": "legacy", "input_schema": {}},
]


def test_drops_undeclared_keys():
    args = {"path": "/rest/v1/x", "method": "GET", "action": "select"}
    filtered, dropped = filter_declared_args(TOOLS, "postgrestRequest", args)
    assert filtered == {"path": "/rest/v1/x", "method": "GET"}
    assert dropped == ["action"]


def test_keeps_declared_keys_untouched():
    args = {"path": "/rest/v1/x", "method": "GET"}
    filtered, dropped = filter_declared_args(TOOLS, "postgrestRequest", args)
    assert filtered == args
    assert dropped == []


def test_passthrough_when_schema_has_no_properties():
    args = {"anything": 1, "goes": 2}
    filtered, dropped = filter_declared_args(TOOLS, "no_schema_tool", args)
    assert filtered == args
    assert dropped == []


def test_passthrough_when_tool_not_in_cache():
    args = {"x": 1}
    filtered, dropped = filter_declared_args(TOOLS, "never_cached", args)
    assert filtered == args
    assert dropped == []
