# AgentWall — Development Guide

## Project Overview

AgentWall is a runtime security and governance layer (MCP Agent Firewall) that sits between AI agents and MCP servers, enforcing policy, approval, DLP, risk scoring, and audit at the tool-call level.

## Architecture

- **Single FastAPI service** handles both MCP proxy (`/mcp`) and REST API (`/api/v1/*`)
- **Next.js dashboard** for security monitoring and management
- **PostgreSQL** for all durable data (agents, servers, tools, policies, audit, approvals)
- **Redis** for ephemeral state (sessions, rate limits, risk state, policy cache, kill switch)
- **Cedar** (AWS) for policy evaluation
- **Streamable HTTP** for agent-facing MCP transport
- **SSE + Streamable HTTP** for downstream MCP server connections

## Tech Stack

- Backend: Python 3.12+, FastAPI, SQLAlchemy, Pydantic, cedarpy
- Frontend: Next.js 14+, TypeScript, Tailwind CSS, shadcn/ui
- Database: PostgreSQL 16, Redis 7
- MCP: official mcp Python SDK
- Observability: OpenTelemetry
- Runtime: Docker Compose

## Project Structure

```
apps/api/          — Python/FastAPI backend (MCP proxy + REST API)
apps/dashboard/    — Next.js frontend dashboard
mcp-servers/       — Demo MCP servers for testing
attack-lab/        — Attack playground scenarios
policies/          — Example Cedar policies
docs/              — Documentation and ADRs
tests/             — End-to-end tests
```

## Development Commands

```bash
make up            # Start all services (Docker Compose)
make down          # Stop all services
make test          # Run all tests
make test-api      # Run API tests only
make test-e2e      # Run end-to-end tests
make migrate       # Run database migrations
make logs          # Tail all service logs
make shell-api     # Shell into API container
```

## Key Decisions (see docs/decisions/ for full ADRs)

1. Full MCP Reverse Proxy — agent never touches real MCP servers
2. Streamable HTTP (agent-facing) + both SSE/Streamable HTTP (downstream)
3. Cedar policy engine for authorization
4. API Key + Session Token for agent identity
5. PostgreSQL (durable) + Redis (ephemeral), synchronous audit writes
6. Single FastAPI service for MCP + REST
7. Configurable audit log levels (METADATA/ARGS_ONLY/FULL), default ARGS_ONLY

## Security Rules

- Never commit secrets or credentials
- Never disable security checks to pass tests
- Never bypass the policy engine
- Never log raw secrets in audit events
- Default-deny in policy evaluation
- All security boundaries must have tests
- Label demo simplifications explicitly
