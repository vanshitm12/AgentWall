# AgentWall — MVP Scope

## Definition

The MVP proves this end-to-end flow:

```
Agent → AgentWall → Policy → Risk → ALLOW/DENY/APPROVAL → MCP Tool → Audit
```

## In Scope

### Core Infrastructure
- [x] MCP reverse proxy (Streamable HTTP agent-facing)
- [ ] Downstream MCP client (SSE + Streamable HTTP)
- [ ] Agent authentication (API key → session)
- [ ] Session management (Redis)
- [ ] PostgreSQL schema and migrations
- [ ] Docker Compose environment

### Registries
- [ ] Agent registry (CRUD + status management)
- [ ] MCP server registry (CRUD + transport config)
- [ ] Tool registry (auto-discovery from MCP servers)

### Policy Engine
- [ ] Cedar integration (cedarpy)
- [ ] Policy CRUD via API
- [ ] Policy evaluation on every tool call
- [ ] Default-deny semantics
- [ ] Priority-based policy resolution

### Security Features
- [ ] Risk scoring (deterministic heuristics)
- [ ] DLP pattern detection (API keys, credentials, PII)
- [ ] Human approval workflow (PENDING → APPROVED/REJECTED)
- [ ] Kill switch (session invalidation)

### Audit
- [ ] Audit event on every tool call
- [ ] Configurable log levels (METADATA / ARGS_ONLY / FULL)
- [ ] Synchronous PostgreSQL writes

### Dashboard
- [ ] Overview page
- [ ] Agent management
- [ ] Tool/server management
- [ ] Policy editor
- [ ] Approval workflow UI
- [ ] Audit log viewer
- [ ] Attack playground UI

### Attack Playground
- [ ] Prompt injection demo
- [ ] Tool poisoning demo
- [ ] Data exfiltration demo
- [ ] Privilege escalation demo
- [ ] Credential abuse demo
- [ ] Excessive usage demo

### Testing
- [ ] Unit tests (policy, risk, DLP, identity)
- [ ] Integration tests (agent → proxy → MCP)
- [ ] Security tests (bypass attempts, malformed requests)
- [ ] End-to-end tests (realistic agent workflows)

### Documentation
- [x] Product spec
- [x] Architecture
- [x] Threat model
- [x] MVP scope (this document)
- [ ] API reference
- [ ] ADRs for all major decisions

## Out of Scope

See product-spec.md "Out of Scope" section. Key exclusions:
- Billing, enterprise SSO, Kubernetes, multi-region
- Custom ML models, SIEM integration
- stdio MCP transport
- Production cloud deployment
- Multi-tenancy

## Phases

| Phase | Name | Goal |
|-------|------|------|
| 0 | Discovery & Design | Architecture, decisions, documentation |
| 1 | MCP Proxy | Agent → AgentWall → MCP (allow everything) |
| 2 | Registries | Agent, server, tool registration and management |
| 3 | Policy Engine | Cedar-based ALLOW / DENY / APPROVAL |
| 4 | Approval System | Human approval workflow |
| 5 | Audit System | Configurable logging of all events |
| 6 | Risk Engine | Deterministic risk scoring |
| 7 | DLP | Sensitive data detection |
| 8 | Kill Switch | Agent termination |
| 9 | Attack Playground | Demo attack scenarios |
| 10 | Dashboard | Full security dashboard |

## Success Demo

The following must work reproducibly:

### Demo 1: Policy Enforcement
```
coding-agent → github.read_file     → ALLOW
coding-agent → github.create_pr     → ALLOW
coding-agent → github.merge_pr      → APPROVAL → human approves → executes
coding-agent → github.delete_repo   → DENY
```

### Demo 2: Attack Detection
```
Malicious website → prompt injection → agent attempts dangerous action
  → AgentWall → BLOCK → incident recorded → agent contained
```
