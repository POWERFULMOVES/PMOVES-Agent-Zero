# Agent Zero NATS Subject Contract

Canonical NATS subjects published and consumed by Agent Zero within PMOVES.AI.
This is the authoritative reference for any service that wants to interact with
Agent Zero events on the NATS message bus.

## Versioning

- All subjects use `.v1` suffix.
- Breaking changes require a new version suffix (`.v2`).
- Deprecated subjects are maintained for 2 release cycles.

## Authentication

All NATS connections MUST use the authenticated URL:

```
nats://nats:pmoves@nats:4222
```

The default is set in `env.shared`:

```
NATS_URL=${NATS_URL:-nats://nats:pmoves@nats:4222}
```

## JetStream

Two env vars reference JetStream but their wiring differs:

| Env var | Defined in | Read by code? |
|---------|------------|---------------|
| `NATS_JETSTREAM` | `env.shared:26` (`NATS_JETSTREAM=${NATS_JETSTREAM:-true}`) | No Python caller found |
| `AGENTZERO_JETSTREAM` | `CLAUDE.md:80` (documented setting) | No Python caller found; **not exported in `env.shared`** |

**Status:** Documented but not implemented. The Agent Zero Python code contains
NO JetStream-specific API calls (`js.subscribe()`, `js.publish()`, stream/consumer
creation). `pmoves_announcer/__init__.py` uses core NATS (`nc.publish()`) regardless
of these env var values. Both vars are forward-looking placeholders for a future
JetStream migration; consuming services should not assume at-least-once delivery
from Agent Zero publishers today.

If you need durable delivery now, the consuming service must create its own
JetStream consumer against the subject.

---

## Subjects

### Published (Agent Zero -> Bus)

#### `services.announce.v1`

- **Source file:** `pmoves_announcer/__init__.py` (line 72)
- **Direction:** Agent Zero -> Bus
- **Frequency:** On startup, then periodically via `BackgroundAnnouncer` (default interval: 60s; PMOVES deployments typically override to 30s)
- **Trigger:** Service startup; periodic re-announcement
- **Publisher class:** `ServiceAnnouncer.announce()`, `BackgroundAnnouncer`
- **Consumer:** Any service using `pmoves_registry` for service discovery; monitoring
- **Implementation status:** Fully implemented with retry logic (`announce_with_retry`, exponential backoff)

**Payload schema:**

```json
{
  "slug": "agent-zero",
  "name": "Agent Zero Orchestrator",
  "url": "http://agent-zero:8080",
  "health_check": "http://agent-zero:8080/healthz",
  "tier": "agent",
  "port": 8080,
  "timestamp": "2026-04-10T12:00:00.000000",
  "metadata": {}
}
```

| Field          | Type   | Required | Description                                      |
|----------------|--------|----------|--------------------------------------------------|
| `slug`         | string | yes      | Unique service identifier                        |
| `name`         | string | yes      | Human-readable service name                      |
| `url`          | string | yes      | Full service URL                                 |
| `health_check` | string | yes      | Health check endpoint URL                        |
| `tier`         | string | yes      | Service tier enum: `data`, `api`, `llm`, `media`, `agent`, `worker`, `app`, `ui` |
| `port`         | int    | yes      | Service port number                              |
| `timestamp`    | string | yes      | ISO 8601 UTC timestamp                           |
| `metadata`     | object | no       | Arbitrary key-value metadata (e.g., `{"gpu_port": 8087}`) |

**Usage from PMOVES.AI_INTEGRATION.md:**

```python
from pmoves_announcer import announce_service

@app.on_event("startup")
async def startup():
    await announce_service(
        slug="agent-zero",
        name="Agent Zero Orchestrator",
        url="http://agent-zero:8080",
        port=8080,
        tier="agent"
    )
```

---

#### `agent.zero.heartbeat.v1`

- **Direction:** Agent Zero -> Bus
- **Frequency:** Every 30s (per CLAUDE.md)
- **Consumer:** mesh-agent, monitoring, Prometheus
- **Implementation status:** Documented in CLAUDE.md but NOT implemented in code

The CLAUDE.md NATS table lists this subject with 30s interval. However, no
Python code in the Agent Zero repository publishes to this subject. The
`BackgroundAnnouncer` on `services.announce.v1` serves a similar purpose
(periodic liveness signal) but uses a different subject and payload schema.

**Expected payload (from documentation, not yet in code):**

```json
{
  "service": "agent-zero",
  "status": "healthy",
  "timestamp": "2026-04-10T12:00:00.000000",
  "uptime_seconds": 3600,
  "active_agents": 2,
  "active_tasks": 5
}
```

---

#### `agent.task.completed.v1`

- **Direction:** Agent Zero -> Bus
- **Trigger:** Task execution finished
- **Consumer:** Archon, monitoring, any service that submitted a task
- **Implementation status:** Documented in CLAUDE.md but NOT implemented in code

No Python code publishes to this subject. Task completion is currently handled
via the MCP HTTP API (`GET /mcp/task/<id>` polling) rather than NATS events.

**Expected payload (from documentation, not yet in code):**

```json
{
  "task_id": "uuid",
  "status": "completed",
  "result": {},
  "agent_id": "uuid",
  "duration_ms": 1234,
  "timestamp": "2026-04-10T12:00:00.000000"
}
```

---

#### `agent.subordinate.created.v1`

- **Direction:** Agent Zero -> Bus
- **Trigger:** Subordinate agent spawned
- **Consumer:** Archon, monitoring
- **Implementation status:** Documented in CLAUDE.md but NOT implemented in code

Subordinate agent creation exists in the MCP HTTP API
(`POST /mcp/subordinate/create`) and in the tool `call_subordinate.py`, but
neither publishes to NATS. The lifecycle event is internal only.

**Expected payload (from documentation, not yet in code):**

```json
{
  "subordinate_id": "uuid",
  "parent_agent_id": "uuid",
  "specialization": "code-review",
  "tools": ["mcp", "search"],
  "timestamp": "2026-04-10T12:00:00.000000"
}
```

---

#### `agent.zero.status.v1`

- **Direction:** Agent Zero -> Bus
- **Trigger:** Status change (startup, shutdown, degraded)
- **Consumer:** mesh-agent, monitoring, Grafana
- **Implementation status:** Documented in CLAUDE.md but NOT implemented in code

No Python code publishes to this subject. Agent status is currently available
only via `GET /healthz` and `GET /mcp/health`.

**Expected payload (from documentation, not yet in code):**

```json
{
  "service": "agent-zero",
  "status": "running",
  "previous_status": "starting",
  "active_agents": 1,
  "nats_connected": true,
  "supabase_connected": true,
  "timestamp": "2026-04-10T12:00:00.000000"
}
```

---

#### `persona.agent.created.v1`

- **Source file:** `python/api/persona_agent_create.py` (line 184), `python/helpers/persona_integration.py` (line 680)
- **Direction:** Agent Zero -> Bus
- **Trigger:** Subordinate agent created from persona configuration via `POST /api/persona/agent/create`
- **Consumer:** Archon, monitoring
- **Implementation status:** Partially implemented -- the event payload is constructed and logged but NOT published to NATS (the `publish_persona_event` method only calls `logger.info`, no NATS client)

**Payload (as constructed in code):**

```json
{
  "event": "persona.agent.created.v1",
  "persona_id": "uuid",
  "name": "Developer",
  "version": "1.0",
  "thread_type": "chained",
  "model": "claude-sonnet-4-5",
  "timestamp": "2026-04-10T12:00:00+00:00",
  "agent_id": "uuid",
  "context_allocation": 0.3,
  "parent_agent_id": "uuid"
}
```

---

### Consumed (Bus -> Agent Zero)

#### `agent.task.request.v1`

- **Direction:** Any service -> Agent Zero
- **Purpose:** Submit task for async execution
- **Publisher:** Any service needing agent orchestration
- **Implementation status:** Documented in CLAUDE.md but NOT implemented as a NATS subscriber

Task submission is currently HTTP-only via `POST /mcp/execute`. The NATS
subscription path would allow fire-and-forget task submission from any bus
participant.

**Expected payload (from documentation, not yet in code):**

```json
{
  "task_id": "uuid",
  "requester": "service-name",
  "command": "Research this topic",
  "context": {},
  "priority": "normal",
  "timeout_ms": 300000,
  "callback_subject": "requester.task.result.v1"
}
```

---

#### Dynamic persona NATS subjects

Personas loaded from Supabase can declare arbitrary NATS subjects in their
`nats_subjects` field. These are stored in the `PersonaConfig.nats_subjects`
list and surfaced in the `AgentConfig.nats_subscriptions` list when an agent
is created from a persona.

- **Source:** `python/helpers/persona_integration.py` (line 108, 189)
- **Implementation status:** The data model carries the subjects but no code
  subscribes to them yet. They are passed through to the agent config for
  future use.

---

## Implementation Gap Summary

| Subject | Documented | Code Exists | Publishes/Subscribes to NATS |
|---------|-----------|-------------|------------------------------|
| `services.announce.v1` | Yes | Yes (`pmoves_announcer`) | Yes -- fully functional |
| `agent.zero.heartbeat.v1` | Yes (CLAUDE.md) | No | No |
| `agent.task.completed.v1` | Yes (CLAUDE.md) | No | No |
| `agent.subordinate.created.v1` | Yes (CLAUDE.md) | No | No |
| `agent.zero.status.v1` | Yes (CLAUDE.md) | No | No |
| `persona.agent.created.v1` | Yes (code) | Yes (persona API) | No -- logger only, no NATS publish |
| `agent.task.request.v1` | Yes (CLAUDE.md) | No | No |

**Only `services.announce.v1` is fully wired to the NATS bus today.**
All other subjects are documented as contracts but await implementation.

---

## Integration Examples

### Subscribe to service announcements

```bash
# Using nats CLI
nats sub "services.announce.v1"
```

### Publish a test service announcement

```bash
nats pub "services.announce.v1" '{
  "slug": "test-service",
  "name": "Test Service",
  "url": "http://localhost:9999",
  "health_check": "http://localhost:9999/healthz",
  "tier": "api",
  "port": 9999,
  "timestamp": "2026-04-10T00:00:00",
  "metadata": {}
}'
```

### Publish a test task request (future -- not yet consumed)

```bash
nats pub "agent.task.request.v1" '{
  "task_id": "test-001",
  "requester": "manual-test",
  "command": "Summarize the latest research findings",
  "context": {},
  "priority": "normal",
  "timeout_ms": 60000
}'
```

### Python: announce Agent Zero on startup

```python
from pmoves_announcer import announce_service, BackgroundAnnouncer, ServiceAnnouncer

# One-shot announcement
await announce_service(
    slug="agent-zero",
    name="Agent Zero Orchestrator",
    url="http://agent-zero:8080",
    port=8080,
    tier="agent"
)

# Periodic re-announcement (recommended)
announcer = ServiceAnnouncer(
    slug="agent-zero",
    name="Agent Zero Orchestrator",
    url="http://agent-zero:8080",
    port=8080,
    tier="agent"
)
bg = BackgroundAnnouncer(announcer, interval=30)
await bg.start()
```

### Python: health check with NATS connectivity

```python
from pmoves_health import HealthChecker

checker = HealthChecker("agent-zero")
checker.nats("nats://nats:pmoves@nats:4222")
status = await checker.check_all()
# Returns: {"status": "healthy", "service": "agent-zero", "nats_connected": true, ...}
```

---

## Related Documentation

- PMOVES NATS subject catalog: `.claude/context/nats-subjects.md`
- GEOMETRY BUS subjects: `.claude/context/geometry-nats-subjects.md`
- Agent Zero MCP API: `.claude/context/mcp-api.md`
- Agent Zero CLAUDE.md: `PMOVES-Agent-Zero/CLAUDE.md`
- Service announcer: `PMOVES-Agent-Zero/pmoves_announcer/__init__.py`
- Health checker: `PMOVES-Agent-Zero/pmoves_health/__init__.py`
- Service registry: `PMOVES-Agent-Zero/pmoves_registry/__init__.py`
- Persona integration: `PMOVES-Agent-Zero/python/helpers/persona_integration.py`
- Persona API: `PMOVES-Agent-Zero/python/api/persona_agent_create.py`
