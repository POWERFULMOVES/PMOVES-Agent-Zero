# PMOVES-Agent-Zero Developer Context

**Always-on context for Claude Code CLI when working in the PMOVES-Agent-Zero repository.**

## Architecture Overview

PMOVES-Agent-Zero is the **control-plane orchestrator** for the PMOVES.AI multi-agent system. It provides:
- Embedded agent runtime with tool execution
- MCP (Model Context Protocol) API for external agent integration
- NATS JetStream task coordination
- Subordinate agent creation and management
- Web UI for interactive agent sessions

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `agent.py` | Root | Core agent loop, message processing, tool dispatch |
| `run_ui.py` | Root | Web UI entry point (Gradio-based) |
| `python/api/` | `python/api/` | MCP API server (FastAPI) |
| `python/helpers/` | `python/helpers/` | Settings, logging, Docker, tool helpers |
| `python/tools/` | `python/tools/` | Built-in tool implementations |
| `prompts/` | `prompts/` | System prompts and persona definitions |
| `tmp/settings.json` | `tmp/` | Runtime settings (auto-generated) |

## Security Posture

- **P1 FIXED (Phase H 2026-02-17):** USER directive added to all 3 Dockerfiles (no more root containers)
- **P1 FIXED:** NATS auth credentials added (`nats://nats:pmoves@nats:4222`)
- **GREEN:** Secrets masking in agent output
- **GREEN:** CSRF protection enabled
- **GREEN:** `/healthz` health check endpoint
- **GREEN:** Prometheus `/metrics` endpoint

## APIs

### MCP API (Port 8080)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/healthz` | GET | Health check (no auth required) |
| `/metrics` | GET | Prometheus metrics |
| `/mcp/health` | GET | MCP runtime status + NATS connectivity |
| `/mcp/commands` | GET | List available MCP commands |
| `/mcp/agents` | GET | List supervisor + subordinate agents |
| `/mcp/execute` | POST | Submit task for async execution |
| `/mcp/task/<id>` | GET | Query task completion status |
| `/mcp/subordinate/create` | POST | Create specialized subordinate agent |

**Authentication:** Bearer token via `MCP_CLIENT_SECRET` (all endpoints except `/healthz` and `/metrics`).

### Web UI (Port 8081)

Gradio-based interactive agent interface for direct user sessions.

## NATS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `agent.zero.heartbeat.v1` | Publish | Periodic heartbeat (every 30s) |
| `agent.task.request.v1` | Subscribe | Incoming task requests |
| `agent.task.completed.v1` | Publish | Task completion notifications |
| `agent.subordinate.created.v1` | Publish | Subordinate agent lifecycle |
| `agent.zero.status.v1` | Publish | Status change notifications |

## Configuration

### Settings via Environment Variables

Agent Zero uses `A0_SET_<name>` env vars for all settings, processed by `get_default_value()` in helpers:

| Variable | Purpose | Default |
|----------|---------|---------|
| `A0_SET_chat_model` | Primary chat model | `tensorzero::model_name::chat_default` |
| `A0_SET_utility_model` | Utility/tool model | `tensorzero::model_name::util_default` |
| `A0_SET_embedding_model` | Embedding model | `tensorzero::embedding_model_name::embed_default` |
| `A0_SET_mcp_server_token` | MCP authentication token | Auto-generated |
| `MCP_CLIENT_SECRET` | External MCP client auth | Required for MCP API |
| `NATS_URL` | NATS connection URL | `nats://nats:pmoves@nats:4222` |
| `AGENTZERO_JETSTREAM` | Enable JetStream delivery | `true` |

### Important: `normalize_settings()`

The `normalize_settings()` function in helpers always overwrites `mcp_server_token`. Do **not** duplicate `create_auth_token()` calls in `get_default_settings()` — the normalization step handles it.

## Development

### Local Setup

```bash
# Install dependencies
cd PMOVES-Agent-Zero
pip install -r requirements.txt

# Run agent (CLI mode)
python agent.py

# Run with Web UI
python run_ui.py
```

### Docker

```bash
# Standalone
docker compose up -d

# With PMOVES.AI (docked mode)
# Managed by parent docker-compose.agents.images.yml
```

### Testing

```bash
# Health check
curl http://localhost:8080/healthz

# MCP health (requires auth)
curl http://localhost:8080/mcp/health \
  -H "Authorization: Bearer $MCP_CLIENT_SECRET"
```

## PMOVES.AI Integration

### Docked Mode

When running as part of PMOVES.AI:
- **Compose profile:** `agents`
- **Ports:** 8080 (API), 8081 (UI)
- **Networks:** `pmoves-net`, `data-net`
- **Depends on:** NATS (`service_healthy`), Supabase (optional)

### Archon Integration

Archon connects to Agent Zero's MCP API for:
- Task delegation via `/mcp/execute`
- Agent status monitoring via `/mcp/agents`
- Subordinate creation for specialized workloads

### Subordinate Agent Model

On-demand specialized agents with limited scope:
1. Parent submits creation request via `/mcp/subordinate/create`
2. Agent Zero spawns subordinate with specified tools/context
3. Subordinate executes independently, reports results via NATS
4. Parent retrieves results via `/mcp/task/<id>`

## Common Gotchas

1. **Settings file:** `tmp/settings.json` is auto-generated — don't edit manually
2. **MCP token:** Auto-generated on first run; use `A0_SET_mcp_server_token` to override
3. **Model names:** Must use TensorZero format `tensorzero::model_name::name` for gateway routing
4. **NATS auth:** URL must include credentials: `nats://nats:pmoves@nats:4222`
5. **Docker USER:** All Dockerfiles use non-root USER directive (Phase H fix)

<!-- PMOVES.AI-CONTEXT-TAGS -->
## PMOVES.AI Skill Hints

**Primary Skills:** `/agents:status`, `/agents:mcp-query`, `/deploy:up`, `/health:quick`
**Context Files:** `mcp-api.md`, `nats-subjects.md`, `services-catalog.md`
**Domain Tags:** `orchestration`, `agents`
**Context Tier:** 2 (On-Demand (Major Subsystem))
<!-- /PMOVES.AI-CONTEXT-TAGS -->
