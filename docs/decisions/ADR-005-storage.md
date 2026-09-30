# ADR-005: Storage Architecture

## Status
Accepted (2026-09-30)

## Context
AgentWall has different data types with different access patterns, durability requirements, and performance needs.

## Problem
How should data be distributed across storage systems?

## Options

### A. PostgreSQL (durable) + Redis (ephemeral), synchronous audit writes (Chosen)
### B. PostgreSQL + Redis + async audit queue
### C. PostgreSQL + Redis, synchronous audit with async fallback

## Decision
**Option A: Clean PostgreSQL + Redis split, synchronous audit writes**

## Why
- Simple: permanent data in PostgreSQL, temporary data in Redis
- Audit integrity: synchronous writes guarantee every event is recorded
- MVP scale: PostgreSQL handles thousands of inserts/second trivially
- 1-5ms audit write cost is invisible compared to tool execution time (100ms-10s)
- Redis role is clear: fast ephemeral lookups, no critical data

## Data Distribution

**PostgreSQL:**
- Agent registrations
- MCP server configurations
- Tool registry
- Cedar policies
- Audit events (append-only, synchronous)
- Approval requests and decisions

**Redis:**
- Active sessions (with TTL)
- Rate limit counters
- Per-session risk state
- Policy cache
- Kill switch markers

## Security Consequences
- Positive: Audit events are ACID-durable — no data loss on crash
- Positive: Redis crash only loses ephemeral state (sessions recreated on reconnect)
- Negative: Audit DB is a sensitive store if ARGS_ONLY or FULL logging is used

## Performance Consequences
- Synchronous PostgreSQL write on every tool call (~1-5ms)
- Redis lookups sub-millisecond
- Adequate for MVP; can add TimescaleDB for audit at scale

## Future Consequences
- Audit event schema locked in early — migrations needed for changes
- Can migrate audit to time-series DB (TimescaleDB, ClickHouse) if volume requires
- Redis data structures are ephemeral — changes just require restart

## Alternatives Rejected
- **Async audit queue** rejected — risk of losing audit events if Redis crashes (unacceptable for security product)
- **Async with fallback** rejected — added complexity without meaningful benefit at MVP scale
