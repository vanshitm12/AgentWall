# ADR-006: Application Architecture

## Status
Accepted (2026-09-30)

## Context
AgentWall has three workloads: MCP proxy, REST API, and dashboard. We need to decide how these are organized and deployed.

## Problem
Should the MCP proxy and REST API be separate services or a single service?

## Options

### A. Single Python Service (Chosen)
One FastAPI application handles both MCP proxy and REST API. Dashboard is separate (Next.js).

### B. Separate MCP Proxy and REST API Services
Two Python/FastAPI services sharing PostgreSQL and Redis.

## Decision
**Option A: Single Python service (FastAPI handles both MCP and REST)**

Docker Compose: 4 services (agentwall-api, agentwall-dashboard, postgres, redis)

## Why
- Simplest deployment: fewer containers, fewer things to manage
- Shared code: policy engine, audit, identity used by both paths without duplication
- Shared database/Redis connections (one pool each)
- FastAPI is async — MCP and REST run concurrently without blocking each other
- Can split later by extracting routes into separate apps

## Security Consequences
- MCP proxy and REST API share the same process — a vulnerability in one affects the other
- Both need the same data access, so no privilege separation benefit from splitting

## Performance Consequences
- Resource sharing — but asyncio handles concurrent workloads well
- No inter-service communication overhead
- At MVP scale, no contention

## Future Consequences
- Must maintain clean module boundaries for future split
- If independent scaling is needed, extraction to two services is straightforward

## Alternatives Rejected
- **Separate services** rejected — premature optimization that adds operational complexity without MVP benefit
