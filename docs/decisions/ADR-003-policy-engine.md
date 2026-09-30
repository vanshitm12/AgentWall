# ADR-003: Policy Engine

## Status
Accepted (2026-09-30)

## Context
AgentWall needs a policy engine to evaluate authorization decisions (ALLOW / DENY / APPROVAL) for every tool call.

## Problem
What technology should evaluate authorization policies?

## Options

### A. Custom Deterministic Engine (Python)
Hand-written pattern matching with priority-based rule evaluation.

### B. OPA (Open Policy Agent) with Rego
Industry-standard policy engine with a declarative policy language (Rego).

### C. Cedar (AWS) (Chosen)
Purpose-built authorization language with formal verification support.

## Decision
**Option C: Cedar (AWS)**

## Why
- Readable policy syntax designed specifically for authorization
- Clean principal/action/resource model maps directly to agent/tool_call/tool
- Formal verification support — can mathematically prove policy properties
- Growing ecosystem backed by AWS (Amazon Verified Permissions)
- More intuitive than Rego for authorization-specific use cases
- Design a clean PolicyEngine interface so the evaluator can be swapped if needed

## Security Consequences
- Positive: Formal verification enables proving policy correctness
- Positive: Declarative language reduces risk of logic bugs vs imperative code
- Negative: Smaller community than OPA — fewer battle-tested examples

## Performance Consequences
- Cedar evaluation is fast (Rust core)
- Python bindings (cedarpy) add some overhead
- Acceptable for MVP scale

## Future Consequences
- Cedar ecosystem is growing but less mature than OPA
- PolicyEngine interface abstraction allows swapping to OPA later if needed
- Policies stored in DB and compiled to Cedar format

## Alternatives Rejected
- **Custom engine** rejected — though simpler for MVP, Cedar provides better long-term foundation with formal verification
- **OPA/Rego** rejected — Rego's learning curve is steeper and its general-purpose design is overkill for authorization-specific use
