# ADR-004: Agent Identity

## Status
Accepted (2026-09-30)

## Context
AgentWall must reliably identify which agent is making each request to apply the correct policies.

## Problem
What credential model should agents use to authenticate with AgentWall?

## Options

### A. API Key per Agent
Long-lived API key in every request.

### B. Short-Lived Tokens (JWT)
Agent authenticates first, receives a JWT, uses it for subsequent requests.

### C. API Key + Session Token (Chosen)
API key for initial authentication, session token for runtime.

## Decision
**Option C: API Key for authentication + Session Token for runtime**

## Why
- Natural fit with MCP's existing session model (Mcp-Session-Id header)
- Kill switch is trivial: invalidate session in Redis → agent blocked immediately
- Per-session state enables risk scoring (frequency, patterns within a session)
- Two-layer security: long-lived key for auth, short-lived session for runtime
- API key rotation doesn't disrupt active sessions

## Security Consequences
- Positive: Session tokens are short-lived (limited blast radius if leaked)
- Positive: Kill switch via session invalidation is immediate
- Positive: API keys hashed at rest (SHA-256)
- Negative: API key is still a long-lived secret that must be securely managed

## Performance Consequences
- API key verification only on session creation (one-time)
- Session lookup in Redis on every request (sub-millisecond)

## Future Consequences
- Can replace API key step with mTLS, OAuth, or other auth methods
- Session layer remains the same regardless of initial auth method
- Session-per-connection model — multi-connection sessions would be a redesign

## Alternatives Rejected
- **API key only** rejected — no session concept means no kill switch latency, no per-session state
- **JWT only** rejected — adds complexity without solving the initial auth problem (still needs a long-lived credential)
