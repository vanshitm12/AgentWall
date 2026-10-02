# AgentWall

**Runtime Security Firewall for AI Agents**

AgentWall is a security and governance layer that sits between autonomous AI agents and the MCP (Model Context Protocol) servers they access. It enforces authorization policies, risk scoring, data loss prevention, human approval workflows, and comprehensive audit logging — ensuring that AI agents cannot exceed their intended permissions.

## The Problem

AI agents using MCP can read data, write data, send messages, execute code, and call APIs. MCP has no built-in authorization layer — if an agent can connect to an MCP server, it can call any tool with any arguments. AgentWall provides the missing security boundary.

## How It Works

```
AI Agent  →  AgentWall (MCP Proxy)  →  Real MCP Server
                    │
             ┌──────┴──────┐
             │              │
          Policy          Audit
          Engine          System
             │
       ┌─────┼─────┐
       │     │     │
     ALLOW  DENY  APPROVAL
```

The agent connects to AgentWall as if it were a normal MCP server. AgentWall intercepts every tool call, evaluates it against Cedar policies, scores the risk, scans for sensitive data, and either allows it, denies it, or holds it for human approval. Every action is logged.

## Core Features

- **MCP Reverse Proxy** — Transparent interception of all MCP tool calls
- **Cedar Policy Engine** — Declarative authorization (ALLOW / DENY / APPROVAL)
- **Agent Identity** — API key authentication with session-based runtime authorization
- **Risk Scoring** — Deterministic heuristic risk assessment per tool call
- **DLP** — Detection of API keys, credentials, PII in tool arguments and responses
- **Human Approval** — Hold high-risk actions for human review before execution
- **Audit Logging** — Configurable logging of every tool invocation and decision
- **Kill Switch** — Instantly revoke an agent's access by invalidating its sessions
- **Security Dashboard** — Real-time monitoring, policy management, approval workflow
- **Attack Playground** — Demonstrate prompt injection, data exfiltration, privilege escalation

## Architecture

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12+, FastAPI |
| Policy Engine | Cedar (AWS) |
| Frontend | Next.js, TypeScript, Tailwind, shadcn/ui |
| Database | PostgreSQL 16 |
| Cache/Sessions | Redis 7 |
| MCP | Official MCP Python SDK |
| Runtime | Docker Compose |

## Quick Start

```bash
# Clone and start
git clone https://github.com/vanshitm12/AgentWall.git
cd agentwall
make up

# Dashboard available at http://localhost:3000
# AgentWall MCP endpoint at http://localhost:8000/mcp
# API at http://localhost:8000/api/v1
```

## Documentation

- [Product Spec](docs/product-spec.md)
- [Architecture](docs/architecture.md)
- [Threat Model](docs/threat-model.md)
- [MVP Scope](docs/mvp.md)
- [API Reference](docs/api.md)
- [Architecture Decision Records](docs/decisions/)

## Security Model

AgentWall's core principle: **the AI agent must never be trusted to enforce its own security permissions.** The security boundary exists outside the model, in infrastructure the agent cannot control.

AgentWall does NOT prevent prompt injection from occurring inside the agent. What it does is ensure that even if an agent is compromised, the *actions* it attempts are governed by externally-enforced policy.

## License

TBD
