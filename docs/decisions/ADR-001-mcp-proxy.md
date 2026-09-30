# ADR-001: MCP Proxy Architecture

## Status
Accepted (2026-09-30)

## Context
AgentWall needs to intercept MCP traffic between AI agents and MCP servers to enforce security policies. We need to decide how this interception happens.

## Problem
How does AgentWall position itself between agents and MCP servers to inspect and control every tool call?

## Options

### A. Full MCP Reverse Proxy (Chosen)
AgentWall implements a full MCP server. The agent connects to AgentWall as its MCP endpoint. AgentWall forwards allowed requests to real downstream MCP servers.

### B. SDK/Library Interception
An AgentWall SDK wraps the MCP client inside the agent's code, intercepting calls before they're sent.

### C. Sidecar / Network-Level Interception
AgentWall runs as a network sidecar that intercepts MCP traffic at the network layer.

## Decision
**Option A: Full MCP Reverse Proxy**

## Why
- Strongest security boundary — agent never touches real MCP servers
- Agent-agnostic — any MCP client works without modification
- Complete control over tool discovery and tool calls
- Aligns with core principle: security enforcement outside the agent
- MCP SDK provides server/client primitives

## Security Consequences
- Positive: Agent cannot bypass policy. All traffic is mediated.
- Positive: Tool listings can be filtered/modified before reaching the agent.
- Negative: AgentWall sees all data in transit (acceptable for self-hosted deployment).

## Performance Consequences
- One extra network hop per tool call (~1-5ms)
- Acceptable for MVP; can optimize with connection pooling

## Future Consequences
- Can add SDK approach (Option B) as additional integration path later
- Can add network-level enforcement (Option C) on top
- Transport support is constrained to what we implement

## Alternatives Rejected
- **SDK interception** rejected because it places security enforcement inside the agent's process, violating the core security principle
- **Sidecar** rejected because it's too complex for MVP and doesn't work for stdio transport
