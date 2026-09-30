# AgentWall — Architecture

## System Overview

```
                        ┌─────────────────┐
                        │   AI Agent(s)   │
                        └────────┬────────┘
                                 │ Streamable HTTP + API Key
                                 ▼
┌──────────────────────────────────────────────────────────┐
│                    AgentWall API                          │
│                  (Python / FastAPI)                       │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ MCP Proxy│  │ REST API │  │ Identity │  │ Session │ │
│  │ /mcp     │  │ /api/v1  │  │ Resolver │  │ Manager │ │
│  └────┬─────┘  └──────────┘  └──────────┘  └─────────┘ │
│       │                                                  │
│  ┌────┴──────────────────────────────────────┐          │
│  │            Request Pipeline               │          │
│  │  Session → Policy → Risk → DLP → Forward  │          │
│  │                    ↓                       │          │
│  │              Audit Event                   │          │
│  └───────────────────────────────────────────┘          │
└──────────────┬──────────────┬───────────────┬────────────┘
               ▼              ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────────┐
        │ MCP      │   │ MCP      │   │ MCP          │
        │ Server 1 │   │ Server 2 │   │ Server N     │
        └──────────┘   └──────────┘   └──────────────┘

        ┌──────────┐   ┌──────────┐
        │PostgreSQL│   │  Redis   │
        └──────────┘   └──────────┘

        ┌─────────────────────────┐
        │   Dashboard (Next.js)   │
        └─────────────────────────┘
```

## Components

### MCP Reverse Proxy

AgentWall implements a full MCP server that agents connect to via Streamable HTTP. When an agent sends `tools/list`, AgentWall fetches tools from all registered downstream MCP servers, merges them (prefixed by server name), and returns the filtered list based on the agent's policies. When an agent sends `tools/call`, AgentWall intercepts, evaluates the request pipeline, and forwards to the correct downstream server if allowed.

The agent never has direct access to downstream MCP servers. This is the fundamental security boundary.

**Agent-facing transport:** Streamable HTTP
**Downstream transport:** SSE or Streamable HTTP (configurable per server)

### Request Pipeline

Every `tools/call` request passes through this pipeline:

```
1. Session Lookup (Redis)
   → Identify agent from session token
   → Check agent status (reject if KILLED/SUSPENDED)

2. Policy Evaluation (Cedar)
   → Load Cedar policies for this agent
   → Evaluate: principal(agent) + action(tool_call) + resource(tool)
   → Result: ALLOW / DENY / APPROVAL

3. Risk Scoring (Deterministic)
   → Evaluate risk signals (destructive, sensitive, external, etc.)
   → Accumulate per-session risk
   → May escalate ALLOW to APPROVAL if risk is extreme

4. DLP Scan
   → Scan tool arguments for sensitive patterns
   → Action: ALLOW / WARN / BLOCK

5. Decision
   → DENY: return error, write audit event
   → APPROVAL: create pending approval, write audit event
   → ALLOW: forward to downstream MCP server

6. Forward & Respond
   → Send tool call to downstream MCP server
   → Receive response
   → DLP scan on response
   → Write audit event
   → Return response to agent
```

### Identity & Authentication

Two-layer identity model:

**Layer 1: API Key (long-lived)**
- Generated when an agent is registered
- Stored as SHA-256 hash in PostgreSQL
- Presented in Authorization header on first connection
- Used only for initial authentication

**Layer 2: Session Token (short-lived)**
- Created after successful API key verification
- Stored in Redis with TTL
- Returned as Mcp-Session-Id header
- Used for all subsequent MCP requests
- Invalidated on kill switch activation

### Policy Engine (Cedar)

Cedar policies define authorization rules using a principal/action/resource model:

```cedar
// Allow coding-agent to read GitHub files
permit(
  principal == Agent::"coding-agent",
  action == Action::"tool_call",
  resource == Tool::"github.read_file"
);

// Require approval for merging PRs
permit(
  principal == Agent::"coding-agent",
  action == Action::"tool_call",
  resource == Tool::"github.merge_pr"
) when { context.decision == "APPROVAL" };

// Deny all repo deletion
forbid(
  principal,
  action == Action::"tool_call",
  resource == Tool::"github.delete_repo"
);
```

Default behavior: **DENY** (if no policy matches, the request is denied).

### Storage

**PostgreSQL** — All durable data:
- Agent registrations
- MCP server configurations
- Tool registry
- Cedar policies
- Audit events (synchronous writes)
- Approval requests and decisions

**Redis** — All ephemeral data:
- Active sessions (with TTL)
- Rate limit counters
- Per-session risk state
- Policy cache (rebuilt from PostgreSQL)
- Kill switch markers

### Dashboard

Next.js application that communicates with the AgentWall REST API (`/api/v1/*`).

Pages:
- **Overview** — Active agents, blocked actions, approvals, risk events
- **Agents** — Registry, status, permissions, activity
- **Tools** — MCP servers, tools, schemas, trust state
- **Policies** — Cedar policy editor and management
- **Approvals** — Pending actions, approval/rejection workflow
- **Activity** — Real-time tool call log
- **Incidents** — Attack detection and timeline
- **Attack Lab** — Interactive attack demonstrations

## Data Model

See database schema in `apps/api/app/models/`.

Key relationships:
- An **agent** has many **audit_events** and **approvals**
- An **mcp_server** has many **tools**
- A **policy** references agents and tools via Cedar policy text
- An **audit_event** references the agent, server, tool, policy, and optionally an approval
- An **approval** references an audit_event

## Deployment

Docker Compose with 4 services:

| Service | Port | Purpose |
|---------|------|---------|
| agentwall-api | 8000 | FastAPI (MCP proxy + REST API) |
| agentwall-dashboard | 3000 | Next.js dashboard |
| postgres | 5432 | PostgreSQL 16 |
| redis | 6379 | Redis 7 |

Plus demo MCP servers for testing:

| Service | Port | Purpose |
|---------|------|---------|
| demo-github-mcp | 8001 | Simulated GitHub MCP server |
| demo-database-mcp | 8002 | Simulated database MCP server |

## Security Boundaries

1. **Agent ↔ AgentWall** — Authenticated via API key + session. Agent cannot bypass proxy.
2. **AgentWall ↔ Downstream MCP** — AgentWall is the only client. Agents have no direct access.
3. **Policy evaluation** — Happens before any tool call reaches the downstream server.
4. **Audit writes** — Synchronous to PostgreSQL. Every action is recorded before response is returned.
5. **Kill switch** — Session invalidation in Redis. Effective immediately on next request.
