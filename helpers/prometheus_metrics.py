# PMOVES: Prometheus metrics for Agent Zero
# Provides metric definitions and the /metrics + /healthz endpoints.
# Imported by helpers/ui_server.py and registered on the Flask webapp.

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from flask import Response

# ─────────────────────────────────────────────────────────────────────────────
# Metric Definitions
# ─────────────────────────────────────────────────────────────────────────────

AGENT_REQUESTS = Counter(
    "agent_zero_requests_total",
    "Total API requests",
    labelnames=("endpoint", "status"),
)

AGENT_REQUEST_LATENCY = Histogram(
    "agent_zero_request_latency_seconds",
    "Request latency",
    labelnames=("endpoint",),
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

AGENT_ACTIVE_SESSIONS = Gauge(
    "agent_zero_active_sessions",
    "Active chat sessions",
)

AGENT_MCP_REQUESTS = Counter(
    "agent_zero_mcp_requests_total",
    "MCP tool requests",
    labelnames=("tool",),
)

# ─────────────────────────────────────────────────────────────────────────────
# Endpoint Handlers
# ─────────────────────────────────────────────────────────────────────────────


def healthz_handler():
    """Health check endpoint for probes and monitoring."""
    from helpers import git

    gitinfo = None
    try:
        gitinfo = git.get_git_info()
    except Exception:
        gitinfo = {"version": "unknown"}
    return {"ok": True, "service": "agent-zero", "version": gitinfo.get("version", "unknown")}


def metrics_handler():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
