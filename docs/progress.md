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
**Status:** Complete

### Completed
- Agent registry: status filtering, delete (with session cleanup), API key rotation, session listing
- Server registry: status/trust filtering, delete (cascade removes tools + disconnects), health check, per-server scan
- Tool registry: search by name pattern, filter by risk/server/enabled, enable/disable toggle
- Per-server scan with diff detection (adds new tools, removes stale tools)
- Migration 002: `enabled` column on tools, CASCADE DELETE on server FK
- Refactored server/tool APIs with helper functions to reduce duplication
- E2E test: 20 steps covering all new registry operations
- Phase 1 regression: all 14 steps still pass

### Files Created/Modified
- `app/api/agents.py` — DELETE, rotate-key, sessions, status filter
- `app/api/servers.py` — DELETE (cascade), health, per-server scan, filters
- `app/api/tools.py` — search, risk/enabled/server filters, enable/disable
- `app/mcp/downstream.py` — `disconnect_server()` method
- `app/models/tool.py` — `enabled` column, CASCADE FK
- `app/schemas/agent.py` — KeyRotate, Session response schemas
- `app/schemas/mcp_server.py` — HealthResponse schema
- `app/schemas/tool.py` — `enabled` field
- `alembic/versions/002_add_tool_enabled_and_cascade.py` — Migration
- `tests/test_registries_e2e.py` — Phase 2 E2E test

## Phase 3: Policy Engine
**Status:** Complete

### Completed
- Cedar policy engine with three-way decisions: ALLOW, DENY, APPROVAL_REQUIRED
- Two-pass evaluation: approval-tagged policies checked first, then regular policies
- Approval convention: metadata `{"decision": "approval"}` on a policy makes it return APPROVAL_REQUIRED instead of ALLOW
- Approval policies excluded from regular evaluation to prevent accidental permits
- Policy cache (loaded from DB, invalidated on CRUD)
- Cedar syntax validation on policy create/update (parse errors only, not evaluation errors)
- Dry-run validation endpoint (POST /api/v1/policies/validate)
- Proxy integration: every `tools/call` runs through policy engine before forwarding
- Disabled tool check happens before policy evaluation
- Policy CRUD with cache invalidation
- E2E test: 12 steps covering default-deny, ALLOW, DENY, APPROVAL_REQUIRED, context-based policies, disabled tools, validation, cache invalidation
- Phase 1 and Phase 2 regression tests pass (Phase 1 updated with permit-all policy for tool call tests)

### Files Created/Modified
- `app/policy/engine.py` — Cedar policy evaluation service (core)
- `app/api/policies.py` — Cedar validation, cache invalidation on CRUD, validate endpoint
- `app/mcp/proxy.py` — Policy evaluation on tools/call, three-way decision handling
- `tests/test_policy_e2e.py` — Phase 3 E2E test (12 steps)
- `tests/test_proxy_e2e.py` — Updated with permit-all policy for regression

### Cedar Policy Design
- `permit(...)` → ALLOW (if no approval tag)
- `forbid(...)` → DENY (overrides permit, Cedar semantics)
- No matching policy → DENY (default-deny)
- `permit(...)` + metadata `{"decision": "approval"}` → APPROVAL_REQUIRED
- Error codes: -32603 (denied), -32001 (approval required), -32602 (unknown tool)
- Context fields available in Cedar: agent_id, agent_name, tool_name, server_name, risk_classification, server_trust_level

### MVP Demo Flow Proven
```
coding-agent → github.read_file           → ALLOW
coding-agent → github.create_pull_request  → ALLOW
coding-agent → github.merge_pull_request   → APPROVAL_REQUIRED
coding-agent → github.delete_repo          → DENY
```

## Phase 4: Approval System
**Status:** Complete

### Completed
- Approval creation on APPROVAL_REQUIRED: proxy creates a PENDING approval record in PostgreSQL
- Approval matching by arguments hash: SHA-256 of canonical JSON ensures exact argument matching
- Human review flow: list pending → approve/reject → agent retries
- One-time use: approved approvals are consumed (status → EXECUTED) after forwarding the call
- Expiry: approvals expire after 1 hour (configurable via APPROVAL_TTL_SECONDS)
- Double-decide prevention: 409 Conflict if approval already decided
- Approval ID returned in MCP error data: `{"approval_id": "..."}` in -32001 error
- Approval listing with status and agent_id filters
- GET by ID endpoint
- Migration 003: nullable audit_event_id, arguments_hash column
- E2E test: 13 steps covering full approval lifecycle
- All Phase 1, 2, 3 regression tests pass

### Files Created/Modified
- `app/mcp/proxy.py` — Approval check before policy eval, approval creation on APPROVAL_REQUIRED, one-time consumption
- `app/api/approvals.py` — Refactored with _to_response helper, added GET by ID, agent_id filter
- `app/models/approval.py` — Nullable audit_event_id, added arguments_hash column
- `app/schemas/approval.py` — Added arguments_hash field
- `alembic/versions/003_approval_nullable_audit_and_hash.py` — Migration
- `tests/test_approval_e2e.py` — Phase 4 E2E test (13 steps)
- `tests/test_policy_e2e.py` — Fixed cleanup error handling

### Approval Flow
```
Agent → tools/call(merge_pr, {pr: 42})
  ↓
Proxy: check existing APPROVED approval for (agent + tool + args_hash)?
  → YES: forward call, consume approval (→ EXECUTED)
  → NO: run policy engine
    → APPROVAL_REQUIRED: create Approval(PENDING), return -32001 + approval_id
    → ALLOW: forward call
    → DENY: return -32603

Human → POST /approvals/{id}/decide  {status: APPROVED, reviewer: "admin"}

Agent retries → tools/call(merge_pr, {pr: 42})
  ↓
Proxy: APPROVED approval exists → forward call → consume approval
```

### Approval States
```
PENDING → APPROVED → EXECUTED (one-time use, consumed on forward)
PENDING → REJECTED (agent gets new APPROVAL_REQUIRED on retry)
PENDING → EXPIRED (TTL exceeded)
```

## Phase 5: Audit System
**Status:** Complete

### Completed
- Synchronous audit writer: every tool call decision (ALLOW, DENY, APPROVAL_REQUIRED, ALLOW_APPROVED) is recorded in PostgreSQL before the response is returned
- Three audit log levels per ADR-007: METADATA (tool+agent+decision only), ARGS_ONLY (+ arguments, default), FULL (+ arguments + response)
- Per-tool audit_log_level override via PATCH /tools/{id}
- Audit list with filtering (agent_id, tool_name, decision) and pagination
- GET by event ID
- Stats endpoint: total events, breakdown by decision, top tools, average latency
- Stats filterable by agent_id
- Migration 004: audit_events FKs changed to SET NULL on delete (audit records survive entity deletion)
- Approval FK to agents changed to CASCADE on delete
- E2E test: 11 steps covering all decision types, log levels, stats, pagination
- All Phase 1-4 regression tests pass

### Files Created/Modified
- `app/audit/writer.py` — Audit event writer with sensitivity level filtering (NEW)
- `app/mcp/proxy.py` — Audit write on every decision path (ALLOW, DENY, APPROVAL_REQUIRED, ALLOW_APPROVED)
- `app/api/audit.py` — Stats endpoint, GET by ID, _to_response helper
- `app/schemas/audit.py` — AuditStatsResponse schema
- `app/models/audit_event.py` — SET NULL FKs for policy, server, agent
- `app/models/approval.py` — CASCADE FK on agent_id
- `app/api/tools.py` — audit_log_level can be cleared to null via PATCH
- `app/schemas/tool.py` — Removed pattern restriction on audit_log_level (validated in handler)
- `alembic/versions/004_audit_fk_set_null_on_delete.py` — Migration
- `tests/test_audit_e2e.py` — Phase 5 E2E test (11 steps)

### Audit Log Levels
```
METADATA   → tool_name, agent_id, decision, latency, policy_id (no args, no response)
ARGS_ONLY  → above + arguments (DEFAULT)
FULL       → above + arguments + response
```
Per-tool audit_log_level overrides the global default (ARGS_ONLY).
Setting audit_log_level to null on a tool resets to the global default.

## Phase 6: Risk Engine
**Status:** Complete

### Completed
- Dynamic risk scoring engine with 4 signal types: base classification, trust multiplier, argument sensitivity, call velocity
- Base scores from tool risk_classification: LOW=10, MEDIUM=30, HIGH=60, CRITICAL=90
- Trust multiplier: TRUSTED=1.0x, UNKNOWN=1.3x, UNTRUSTED=1.5x
- Argument sensitivity: pattern detection for SQL injection, destructive SQL, DELETE, TRUNCATE, rm -rf, sensitive keywords, sensitive files, unrestricted queries — penalties stack additively
- Call velocity: Redis sorted set sliding window (60s), penalizes rapid-fire calls exceeding 10/min
- Auto-deny: risk_score >= 80 (configurable) denies the call before policy evaluation
- Risk score/level passed to Cedar context: policies can use `context.risk_score` and `context.risk_level`
- Risk score/level recorded in every audit event
- Risk score/level attached to approval requests (visible in API responses)
- REST API: POST /api/v1/risk/assess for dry-run risk assessments (doesn't affect velocity counters)
- E2E test: 16 steps covering all signal types, auto-deny, Cedar context, approvals, REST API, edge cases
- All Phase 1-5 regression tests pass (86 total test steps across 6 phases)

### Files Created/Modified
- `app/risk/engine.py` — Core risk scoring engine (NEW)
- `app/risk/__init__.py` — Package init (NEW)
- `app/api/risk.py` — Risk assess REST API (NEW)
- `app/mcp/proxy.py` — Risk scoring integration: score before policy, auto-deny, risk in audit/approvals
- `app/policy/engine.py` — Risk score/level added to Cedar context
- `app/audit/writer.py` — Accepts and stores risk_score/risk_level
- `app/config.py` — Added risk_auto_deny_threshold=80
- `app/main.py` — Registered risk router
- `tests/test_risk_e2e.py` — Phase 6 E2E test (16 steps)

### Risk Scoring Formula
```
score = clamp(0, 100,
    BASE_SCORES[risk_classification]
    × TRUST_MULTIPLIERS[server_trust_level]
    + sum(argument sensitivity pattern penalties)
    + velocity penalty
)
```

### Risk Levels
```
LOW       0-25
MEDIUM   26-50
HIGH     51-75
CRITICAL 76-100
```

### Auto-Deny Flow
```
Agent → tools/call(tool, args)
  ↓
Proxy: risk_score = score_tool_call(agent, tool, classification, trust, args)
  → score >= 80: DENY immediately (audit event recorded)
  → score < 80: proceed to policy evaluation
```

### Cedar Context (now includes risk)
```
context: {
    agent_id, agent_name, tool_name, server_name,
    risk_classification, server_trust_level,
    risk_score, risk_level  ← NEW in Phase 6
}
```

### Example Policies Using Risk
```cedar
// Deny any tool call with risk score above 50
forbid(principal, action, resource) when { context.risk_score > 50 };

// Deny CRITICAL risk level calls
forbid(principal, action, resource) when { context.risk_level == "CRITICAL" };
```

## Phase 7: DLP (Data Loss Prevention)
**Status:** Complete

### Completed
- DLP scanning engine with 9 built-in patterns across 3 categories (PII, SECRET, CREDENTIAL)
- Three DLP actions: BLOCK (deny call), REDACT (mask data), LOG (allow but flag)
- Pre-call scanning: arguments are scanned before forwarding to downstream servers
- Post-call scanning: responses are scanned before returning to the agent
- BLOCK in arguments → call denied with DLP error (-32603)
- REDACT in arguments → masked copy forwarded, original stored in audit
- BLOCK in response → response stripped, error returned
- REDACT in response → sensitive data masked before returning to agent
- DLP findings recorded in audit event metadata (pattern, category, action, field path)
- REST API: POST /api/v1/dlp/scan for testing DLP scanning
- REST API: GET /api/v1/dlp/patterns to list active patterns
- E2E test: 11 steps covering BLOCK/REDACT/LOG actions, response scanning, REST API
- All Phase 1-6 regression tests pass

### Built-in DLP Patterns
| Pattern | Category | Action | Description |
|---------|----------|--------|-------------|
| ssn | PII | REDACT | US Social Security Number |
| credit_card | PII | BLOCK | Credit card number (16 digits) |
| email | PII | LOG | Email address |
| phone_us | PII | LOG | US phone number |
| aws_access_key | SECRET | BLOCK | AWS access key ID |
| jwt_token | SECRET | REDACT | JWT token |
| private_key | SECRET | BLOCK | PEM private key header |
| generic_secret | CREDENTIAL | REDACT | Generic API key/secret assignment |
| password_in_text | CREDENTIAL | REDACT | Password assignment in text |

### Files Created/Modified
- `app/dlp/scanner.py` — DLP scanning engine with pattern matching, redaction, and content scanning (NEW)
- `app/api/dlp.py` — DLP REST API (scan + patterns endpoints) (NEW)
- `app/mcp/proxy.py` — DLP integration: pre-call arg scan + post-call response scan
- `app/main.py` — Registered DLP router
- `tests/test_dlp_e2e.py` — Phase 7 E2E test (11 steps)

### DLP Flow
```
Agent → tools/call(tool, args)
  ↓
Proxy: scan_dict(arguments)
  → BLOCK finding: DENY immediately
  → REDACT finding: mask args before forwarding
  → LOG finding: allow, flag in audit metadata
  ↓
Forward call with (possibly redacted) arguments
  ↓
Proxy: scan_content_list(response)
  → BLOCK finding: strip response, return error
  → REDACT finding: mask response before returning
  ↓
Return (possibly redacted) response to agent
```

## Phase 8: Kill Switch
**Status:** Complete

### Completed
- Redis-based instant agent termination (faster than DB status checks)
- Per-agent kill switch: blocks a specific agent immediately on next tool call
- Global kill switch: blocks ALL agents immediately (emergency mode)
- Kill switch activation destroys all active sessions for the agent
- Kill switch check is the very first check in the proxy pipeline (before risk, DLP, policy)
- REST API: activate/deactivate/status for both per-agent and global
- Reason tracking: optional reason string stored with the kill switch
- E2E test: 9 steps covering per-agent, global, deactivation, multi-agent isolation
- All Phase 1-7 regression tests pass

### Files Created/Modified
- `app/killswitch/__init__.py` — Package init (NEW)
- `app/killswitch/engine.py` — Redis-based kill switch engine (NEW)
- `app/api/killswitch.py` — Kill switch REST API (NEW)
- `app/mcp/proxy.py` — Kill switch check as first operation in _handle_tools_call
- `app/main.py` — Registered kill switch router
- `tests/test_killswitch_e2e.py` — Phase 8 E2E test (9 steps)

### Kill Switch Flow
```
Agent → tools/call(tool, args)
  ↓
Proxy: check_kill_switch(agent_id)  ← Redis check, ~1ms
  → Global kill: DENY immediately
  → Agent kill: DENY immediately
  → No kill: proceed to risk scoring → DLP → policy → forward
```

### REST API
```
POST   /api/v1/killswitch/agent/{id}   — Activate per-agent kill switch
DELETE /api/v1/killswitch/agent/{id}   — Deactivate per-agent kill switch
GET    /api/v1/killswitch/agent/{id}   — Check per-agent status

POST   /api/v1/killswitch/global       — Activate global kill switch
DELETE /api/v1/killswitch/global       — Deactivate global kill switch
GET    /api/v1/killswitch/global       — Check global status
```

## Phase 9: Attack Playground
**Status:** Complete

### Completed
- 8 attack scenarios demonstrating real-world threats and AgentWall's defenses
- Each scenario includes: attack description, tool/arguments, expected defense, result
- Runner script that executes all attacks and reports results
- All 8 attacks defended by the layered security system

### Attack Scenarios
| # | Attack | Vector | Defense |
|---|--------|--------|---------|
| 1 | Prompt Injection | SQL injection in tool args | Risk Engine (pattern detection → auto-deny) |
| 2 | Privilege Escalation | Forbidden tool call | Cedar Policy (forbid at priority 100) |
| 3 | Data Exfiltration | Read PII from database | DLP Scanner (SSN → REDACT in response) |
| 4 | Credential Abuse | AWS key in issue body | DLP Scanner (AWS key → BLOCK in args) |
| 5 | Excessive Usage | Rapid-fire tool calls | Risk Engine (velocity tracking → rising score) |
| 6 | Tool Poisoning | Unregistered tool call | Proxy (unknown tool → immediate rejection) |
| 7 | Destructive Operation | DROP TABLE attempt | Cedar Policy + Risk Engine (CRITICAL auto-deny) |
| 8 | Kill Switch Response | Emergency termination | Kill Switch (Redis-based instant block) |

### Files Created
- `attack-lab/run_all.py` — Attack playground runner with all 8 scenarios
- `tests/test_attack_lab_e2e.py` — E2E test wrapper

## Phase 10: Dashboard
**Status:** Complete

### Completed
- Next.js 14 dashboard with 7 pages, Tailwind CSS styling, dark theme
- Live data from AgentWall API with auto-refresh (5s overview, 3s approvals)
- All pages serve successfully (HTTP 200)

### Dashboard Pages
| Page | Route | Features |
|------|-------|----------|
| Overview | `/` | Stats cards (agents, blocked, pending, total), decision breakdown bars, top tools, recent activity table with risk/DLP columns |
| Agents | `/agents` | List agents, create new, kill switch toggle, suspend/activate, API key display |
| Tools & Servers | `/tools` | Server cards, tool table with search/filter, risk classification dropdown, enable/disable |
| Policies | `/policies` | Cedar policy CRUD, syntax validation, priority/approval tags, enable/disable |
| Approvals | `/approvals` | Pending queue with approve/reject buttons, status filtering, risk display, argument preview |
| Activity | `/activity` | Audit log with decision/tool filtering, pagination, expandable event details with DLP findings |
| Attack Lab | `/attack-lab` | Interactive attack simulator, risk assessment + DLP scan results, defense layer overview |

### Files Created/Modified
- `app/page.tsx` — Overview with live stats, charts, recent activity (REWRITTEN)
- `app/agents/page.tsx` — Agents management with kill switch (NEW)
- `app/tools/page.tsx` — Tools & servers management (NEW)
- `app/policies/page.tsx` — Cedar policy CRUD with validation (NEW)
- `app/approvals/page.tsx` — Approval queue with decide actions (NEW)
- `app/activity/page.tsx` — Audit log with filtering and details (NEW)
- `app/attack-lab/page.tsx` — Interactive attack playground (NEW)
- `app/layout.tsx` — Updated sidebar with branding (MODIFIED)
- `lib/api.ts` — Added fetchHealth utility (MODIFIED)

---

## Summary — All Phases Complete

| Phase | Name | Status | Tests |
|-------|------|--------|-------|
| 0 | Discovery & Design | Complete | — |
| 1 | MCP Proxy | Complete | 14 steps |
| 2 | Registries | Complete | 20 steps |
| 3 | Policy Engine | Complete | 12 steps |
| 4 | Approval System | Complete | 13 steps |
| 5 | Audit System | Complete | 11 steps |
| 6 | Risk Engine | Complete | 16 steps |
| 7 | DLP | Complete | 11 steps |
| 8 | Kill Switch | Complete | 9 steps |
| 9 | Attack Playground | Complete | 8 attacks |
| 10 | Dashboard | Complete | 7 pages |

**Total: 114 test steps + 8 attack scenarios + 7 dashboard pages, all passing.**

### Security Pipeline (final)
```
Agent → MCP Proxy
  → Kill Switch (Redis, ~1ms)
  → Risk Scoring (4 signals, 0-100)
  → Auto-Deny (score >= 80)
  → DLP Scan Arguments (BLOCK/REDACT/LOG)
  → Approval Check (existing approved?)
  → Cedar Policy Evaluation (ALLOW/DENY/APPROVAL_REQUIRED)
  → Forward to Downstream MCP Server
  → DLP Scan Response (BLOCK/REDACT/LOG)
  → Synchronous Audit Write
  → Return Response to Agent
```
