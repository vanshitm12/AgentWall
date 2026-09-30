# ADR-002: MCP Transport Protocol

## Status
Accepted (2026-09-30)

## Context
MCP supports multiple transports: stdio, HTTP+SSE, and Streamable HTTP. We need to decide which transports AgentWall supports for agent-facing and downstream connections.

## Problem
Which MCP transport protocols should AgentWall implement for MVP?

## Options

### A. HTTP + SSE Only
### B. Streamable HTTP Only
### C. Streamable HTTP (agent-facing) + Both SSE and Streamable HTTP (downstream) (Chosen)

## Decision
**Option C: Streamable HTTP agent-facing, both SSE and Streamable HTTP downstream**

## Why
- Streamable HTTP is the modern MCP direction — building on it avoids future migration
- Downstream servers may use either SSE or Streamable HTTP — we must support both
- stdio is out of MVP scope (can be bridged later via a local wrapper)
- MCP SDK abstracts transport differences, keeping downstream complexity manageable

## Security Consequences
- Network-based transports support TLS
- All transports flow through the same policy pipeline

## Performance Consequences
- Streamable HTTP is simpler than SSE (single endpoint vs two channels)
- No significant difference at MVP scale

## Future Consequences
- Can add stdio bridge later without changing core architecture
- Agent-facing protocol is what users configure — changing it later requires user coordination
- Adding SSE as a second agent-facing transport is additive, not breaking

## Alternatives Rejected
- **stdio** excluded from MVP — it's process-local and conflicts with the network proxy model
- **SSE-only** rejected because Streamable HTTP is the recommended modern transport
