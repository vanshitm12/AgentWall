# AgentWall — Progress Log

## Phase 0: Discovery & Design

**Status:** Complete

### Completed
- Repository initialized
- Architecture decisions made (7 ADRs)
- Product spec written
- Architecture document written
- Threat model written
- MVP scope defined
- Project structure scaffolded
- Docker Compose skeleton created

### Decisions Made
1. **MCP Proxy:** Full reverse proxy (ADR-001)
2. **MCP Transport:** Streamable HTTP agent-facing + both downstream (ADR-002)
3. **Policy Engine:** Cedar (AWS) (ADR-003)
4. **Agent Identity:** API Key + Session Token (ADR-004)
5. **Storage:** PostgreSQL durable + Redis ephemeral (ADR-005)
6. **App Architecture:** Single FastAPI service + Next.js dashboard (ADR-006)
7. **Audit Sensitivity:** Configurable levels, ARGS_ONLY default (ADR-007)

### Next
- Complete ADR documents
- Set up Python project (pyproject.toml, dependencies)
- Set up Next.js project
- Configure Docker Compose
- Begin Phase 1: MCP Proxy

---

## Phase 1: MCP Proxy

**Status:** Complete

### Completed
- MCP proxy endpoint (POST /mcp, DELETE /mcp)
- Streamable HTTP protocol handling (JSON-RPC messages)
- Agent authentication (API key → SHA-256 hash → session in Redis)
- Session management (create, validate, destroy, TTL refresh)
- Downstream MCP server connection manager (persistent connections)
- Tool discovery from downstream servers (aggregated, namespaced by server)
- Tool call forwarding (route to correct downstream server)
- Initial Alembic migration (all 6 database tables)
- Discovery endpoint (POST /api/v1/discovery/scan)
- E2E test script
- Mode: ALLOW EVERYTHING (no policy enforcement yet)

### Files Created/Modified
- `app/mcp/session.py` — Session manager (Redis)
- `app/mcp/downstream.py` — Downstream MCP connection manager
- `app/mcp/proxy.py` — MCP proxy endpoint (the core security boundary)
- `app/api/discovery.py` — Tool discovery API
- `alembic/versions/001_initial_schema.py` — Database migration
- `tests/test_proxy_e2e.py` — End-to-end test

### Security Boundary
- Agent → AgentWall (authenticated via API key + session)
- AgentWall → Downstream MCP servers (internal network only)
- Agent cannot bypass proxy (Docker network isolation)
- Killed/suspended agents are rejected immediately

### Limitations
- No policy evaluation (ALLOW EVERYTHING)
- No risk scoring
- No DLP
- No audit logging
- No approval workflow
- Reconnection to downstream servers not yet handled

## Phase 2: Registries
**Status:** Not Started

## Phase 3: Policy Engine
**Status:** Not Started

## Phase 4: Approval System
**Status:** Not Started

## Phase 5: Audit System
**Status:** Not Started

## Phase 6: Risk Engine
**Status:** Not Started

## Phase 7: DLP
**Status:** Not Started

## Phase 8: Kill Switch
**Status:** Not Started

## Phase 9: Attack Playground
**Status:** Not Started

## Phase 10: Dashboard
**Status:** Not Started
