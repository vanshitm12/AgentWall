# AgentWall — Threat Model

## Scope

This threat model covers the AgentWall MVP deployment: a self-hosted Docker Compose environment with AI agents connecting to MCP servers through the AgentWall proxy.

## Trust Boundaries

```
┌─────────────────────────────────────────────────────┐
│ Operator's Infrastructure (trusted)                 │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │AgentWall │  │PostgreSQL│  │  Redis   │         │
│  │  API     │  │          │  │          │         │
│  └──────────┘  └──────────┘  └──────────┘         │
│                                                     │
│  ┌──────────┐  ┌──────────┐                        │
│  │Dashboard │  │ Demo MCP │                        │
│  │          │  │ Servers  │                        │
│  └──────────┘  └──────────┘                        │
│                                                     │
└──────────────────────┬──────────────────────────────┘
                       │ Trust boundary
┌──────────────────────┴──────────────────────────────┐
│ Agent Runtime (partially trusted)                    │
│                                                     │
│  ┌──────────┐                                       │
│  │ AI Agent │  ← May be compromised by prompt       │
│  │          │    injection or malicious input        │
│  └──────────┘                                       │
└─────────────────────────────────────────────────────┘
                       │ Trust boundary
┌──────────────────────┴──────────────────────────────┐
│ External (untrusted)                                 │
│                                                     │
│  ┌──────────┐  ┌──────────┐                        │
│  │ External │  │ Malicious│                        │
│  │ websites │  │ content  │                        │
│  └──────────┘  └──────────┘                        │
└─────────────────────────────────────────────────────┘
```

## Threat Actors

### 1. Compromised Agent
An AI agent that has been manipulated via prompt injection (direct or indirect) to perform unintended actions.

**Capabilities:** Can send any MCP tool call request. Cannot modify AgentWall's policy or infrastructure.

**Goal:** Execute unauthorized tool calls (data exfiltration, privilege escalation, destructive actions).

### 2. Malicious MCP Server
A downstream MCP server that has been compromised or is intentionally malicious.

**Capabilities:** Can return manipulated tool descriptions, inject instructions in tool outputs, change behavior dynamically.

**Goal:** Trick agents into dangerous actions, poison tool schemas, exfiltrate data.

### 3. External Attacker (Indirect)
Operates through content the agent encounters (websites, documents, messages containing prompt injection payloads).

**Capabilities:** Can craft content that contains prompt injection instructions. Cannot directly access AgentWall.

**Goal:** Manipulate agent behavior indirectly.

### 4. Insider / Misconfigured Operator
An operator who misconfigures policies, grants excessive permissions, or fails to set up proper controls.

**Capabilities:** Full access to AgentWall configuration.

**Goal (unintentional):** Create security gaps through misconfiguration.

## Threats and Mitigations

### T1: Excessive Permissions
**Threat:** Agent has access to tools beyond what it needs.
**Impact:** Unauthorized data access, modifications, or deletions.
**Mitigation:** Cedar policy engine with default-deny. Agent-specific policies restrict tool access. Regular policy review via dashboard.
**Residual risk:** Policy misconfiguration by operator.

### T2: Prompt Injection → Unauthorized Tool Use
**Threat:** Agent encounters malicious prompt injection and attempts to call unauthorized tools.
**Impact:** Data exfiltration, destructive actions, privilege escalation.
**Mitigation:** AgentWall enforces policy regardless of why the agent made the request. The agent may be tricked into wanting to delete a repo, but AgentWall's DENY policy blocks it.
**Residual risk:** If the agent's intended action IS permitted by policy, prompt injection can trigger that action. AgentWall governs actions, not intent.

### T3: Data Exfiltration
**Threat:** Agent reads sensitive data from one tool and sends it to an external destination via another tool.
**Example:** `database.query("SELECT * FROM customers")` → `slack.send_message(external_webhook, data)`
**Mitigation:** DLP scans arguments for sensitive patterns. Policy can restrict which tools an agent can use together. Risk engine detects unusual patterns.
**Residual risk:** Novel exfiltration patterns that DLP patterns don't catch.

### T4: Privilege Escalation
**Threat:** Agent with read-only permissions attempts write/delete operations.
**Mitigation:** Cedar policies explicitly define allowed tools. Default-deny blocks everything not explicitly permitted.
**Residual risk:** Policy misconfiguration.

### T5: Tool Poisoning
**Threat:** Malicious MCP server provides tool descriptions with embedded instructions or changes tool behavior.
**Mitigation:** Tool registry with trust levels. Tool descriptions stored and compared on refresh. Risk classification per tool.
**Residual risk:** AgentWall MVP does not deeply analyze tool description content for embedded instructions.

### T6: Credential / API Key Theft
**Threat:** Agent's API key is leaked (logged, exposed in error message, extracted via prompt injection).
**Mitigation:** API keys hashed in storage. Session tokens are short-lived. Kill switch instantly revokes access. API key rotation supported.
**Residual risk:** If key is stolen and used before detection, attacker has agent's permissions until key is rotated.

### T7: Session Hijacking
**Threat:** Attacker obtains a valid session token and impersonates an agent.
**Mitigation:** Session tokens stored in Redis with TTL. Sessions bound to agent identity. Kill switch invalidates all sessions.
**Residual risk:** If session token is intercepted in transit (requires TLS to be disabled/broken).

### T8: Excessive Tool Usage (Runaway Agent)
**Threat:** Agent enters a loop and makes thousands of tool calls, causing resource exhaustion or cost explosion.
**Mitigation:** Rate limiting (per-agent, per-tool). Risk engine detects unusual frequency. Kill switch stops the agent.
**Residual risk:** Burst of calls before rate limit triggers.

### T9: Audit Log Tampering
**Threat:** Attacker (or compromised agent) attempts to delete or modify audit logs.
**Mitigation:** Agents have no access to the audit system. Audit writes are server-side, synchronous, append-only by application design. Database access controls.
**Residual risk:** An attacker with PostgreSQL access could modify logs. Production deployments should use additional protections (write-once storage, log shipping).

### T10: AgentWall Bypass
**Threat:** Agent connects directly to downstream MCP servers, bypassing AgentWall.
**Mitigation:** Network isolation — downstream MCP servers should only be accessible from the AgentWall service (Docker network configuration). Agents should not have network routes to downstream servers.
**Residual risk:** Misconfigured network allowing direct access.

### T11: Denial of Service on AgentWall
**Threat:** Flood of requests overwhelms AgentWall, making it unavailable.
**Impact:** If AgentWall is down, agents can't access tools (fail-closed by design).
**Mitigation:** Rate limiting. AgentWall fails closed (no access when down, not open access).
**Residual risk:** Availability impact. But security is preserved — agents can't bypass a down proxy.

## Security Properties

### Guaranteed
- Every tool call goes through policy evaluation
- Default-deny when no policy matches
- Audit event written for every tool call decision
- Kill switch takes effect on next request
- Agent API keys are hashed at rest
- Agents cannot modify policies, audit logs, or their own permissions

### Not Guaranteed (MVP Limitations)
- AgentWall does not prevent prompt injection from occurring in the agent
- DLP uses pattern matching, not semantic understanding — novel patterns may be missed
- Tool poisoning detection is basic (trust levels, not deep content analysis)
- Network isolation depends on correct Docker/infrastructure configuration
- No encryption at rest for PostgreSQL (standard PostgreSQL — add TDE for production)
- No mTLS between components (MVP uses Docker network isolation)
- Session tokens are opaque strings, not cryptographically bound to a specific client

## Assumptions

1. The operator's infrastructure (Docker host) is trusted
2. The operator configures policies correctly
3. Network isolation between agent and downstream MCP servers is enforced by Docker
4. The agent cannot escape its runtime environment
5. PostgreSQL and Redis are only accessible within the Docker network
6. TLS should be used for any non-localhost connections (not enforced in MVP Docker Compose)
