# AgentWall — Product Specification

## Vision

AgentWall is a runtime security and governance layer for autonomous AI agents. It sits between agents and the MCP (Model Context Protocol) tools they access, enforcing authorization policies, risk assessment, data protection, and audit logging.

## Core Principle

**The AI agent must never be trusted to enforce its own security permissions.**

The security boundary must exist outside the model, in infrastructure the agent cannot control or bypass.

## Problem Statement

MCP enables AI agents to discover and invoke tools (GitHub, databases, Slack, cloud APIs, etc.) through a standardized protocol. However, MCP has no built-in authorization layer. If an agent can connect to an MCP server, it can call any tool that server exposes with any arguments.

This creates security risks:
- **Excessive permissions** — Agents have access to tools they shouldn't
- **Prompt injection** — Malicious inputs trick agents into dangerous actions
- **Data exfiltration** — Agents read sensitive data and send it externally
- **Privilege escalation** — Read-only agents attempt write operations
- **Tool poisoning** — Malicious MCP servers provide dangerous tool descriptions
- **Credential abuse** — Agents use credentials outside intended scope
- **Excessive usage** — Runaway agents make thousands of calls
- **Insufficient auditability** — No record of what agents did

## Solution

AgentWall operates as a full MCP reverse proxy:

```
AI Agent  →  AgentWall  →  Real MCP Server
```

The agent connects to AgentWall as if it were a normal MCP server. AgentWall intercepts every request, evaluates it against policies, and either allows, denies, or escalates for human approval.

## Feature Set (MVP)

### MCP Proxy
- Transparent reverse proxy for MCP protocol
- Streamable HTTP transport (agent-facing)
- SSE and Streamable HTTP support (downstream)
- Tool discovery aggregation across multiple MCP servers
- Request/response inspection

### Agent Registry
- Register and manage agent identities
- API key authentication
- Session-based runtime authorization
- Agent status management (ACTIVE / SUSPENDED / KILLED)

### MCP Server Registry
- Register downstream MCP servers
- Transport type configuration (SSE or Streamable HTTP)
- Trust level classification (TRUSTED / UNTRUSTED / QUARANTINED)
- Health monitoring

### Tool Registry
- Automatic tool discovery from registered MCP servers
- Risk classification per tool (LOW / MEDIUM / HIGH / CRITICAL)
- Tool schema storage
- Audit log level configuration per tool

### Policy Engine (Cedar)
- Declarative authorization policies using Cedar language
- Three decision types: ALLOW / DENY / APPROVAL
- Agent-scoped and global policies
- Priority-based evaluation
- Default-deny semantics

### Risk Engine
- Deterministic heuristic risk scoring
- Risk signals: destructive action, sensitive data, external destination, privilege escalation, unusual frequency
- Per-session risk accumulation
- Risk level classification (LOW / MEDIUM / HIGH / CRITICAL)

### DLP (Data Loss Prevention)
- Pattern detection: API keys, cloud credentials, private keys, JWTs, credit cards, emails, phone numbers
- Scan tool arguments (outbound) and responses (inbound)
- Actions: ALLOW / WARN / BLOCK

### Human Approval Workflow
- Hold high-risk tool calls for human review
- Dashboard interface for approvals
- Approve / Reject with reason
- Approval expiration
- Full audit trail of approval decisions

### Audit System
- Every tool invocation logged
- Configurable logging levels: METADATA / ARGS_ONLY / FULL
- Per-tool log level override
- Synchronous writes to PostgreSQL for integrity
- Dashboard query and export

### Kill Switch
- Instantly revoke agent access
- Session invalidation via Redis
- Agent status transitions: ACTIVE → SUSPENDED → KILLED
- All subsequent tool calls rejected immediately

### Security Dashboard
- Overview: active agents, blocked actions, approvals, risk events
- Agent management and monitoring
- MCP server and tool registry
- Policy editor
- Approval workflow
- Audit log viewer
- Attack playground

### Attack Playground
- Prompt injection demonstration
- Tool poisoning demonstration
- Data exfiltration demonstration
- Privilege escalation demonstration
- Credential abuse demonstration
- Excessive usage demonstration

## Out of Scope (MVP)

- Billing / payments
- Enterprise SSO / SAML / OIDC
- Kubernetes deployment
- Multi-region deployment
- Complex microservices
- Custom ML/LLM security models
- Browser automation
- Full SIEM integration
- Enterprise compliance certifications
- Autonomous remediation
- Production cloud infrastructure
- Complex multi-tenancy
- stdio MCP transport (can be bridged later)

## Success Criteria

The MVP is complete when this flow works end-to-end:

1. An agent connects to AgentWall
2. Agent discovers tools from downstream MCP servers
3. `github.read_file` → ALLOW (policy)
4. `github.create_pr` → ALLOW (policy)
5. `github.merge_pr` → APPROVAL → human approves → executes
6. `github.delete_repo` → DENY (policy)
7. Prompt injection attack → agent attempts dangerous action → BLOCK
8. All actions recorded in audit log
9. Dashboard shows real-time activity
10. Kill switch stops agent immediately
