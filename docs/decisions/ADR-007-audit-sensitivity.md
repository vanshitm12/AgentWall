# ADR-007: Audit Log Sensitivity

## Status
Accepted (2026-09-30)

## Context
AgentWall logs every tool invocation. The audit log can contain sensitive data (tool arguments include SQL queries, message bodies, file paths; responses include query results, file contents, etc.).

## Problem
How much data should audit events contain?

## Options

### A. Configurable Logging Levels (Chosen)
Three levels (METADATA / ARGS_ONLY / FULL), configurable globally and per-tool. Default: ARGS_ONLY.

### B. Always Log Full + Automatic Redaction
Log everything but run a redaction pipeline to strip sensitive patterns.

### C. Log Arguments Always, Responses Configurable
Always store arguments, make response logging opt-in.

## Decision
**Option A: Configurable logging levels with ARGS_ONLY as default**

### Levels
- **METADATA** — Tool name, decision, timestamp, risk score. No arguments or responses.
- **ARGS_ONLY** — Includes request arguments. No responses.
- **FULL** — Includes arguments and responses.

### Configuration
- Global default level (ARGS_ONLY)
- Per-tool override (in tool registry)

## Why
- Operator controls the privacy/forensics trade-off
- ARGS_ONLY default shows what agents attempted without storing all downstream data
- Simple implementation (conditional field inclusion, no redaction pipeline)
- DLP handles real-time sensitive data detection separately
- Per-tool override enables FULL for critical tools, METADATA for routine ones

## Security Consequences
- Positive: Operator consciously decides data exposure
- Positive: ARGS_ONLY provides forensic capability without response data
- Negative: FULL logging makes audit DB a sensitive data store
- Negative: METADATA logging may be insufficient for incident investigation

## Performance Consequences
- FULL uses more storage
- No significant difference in write latency

## Future Consequences
- Can add a REDACTED level later (full data with PII scrubbing)
- Historical events at one level can't be retroactively upgraded to a higher level
- Starting at ARGS_ONLY is the safest middle ground

## Alternatives Rejected
- **Auto-redaction** rejected — redaction bugs are privacy bugs; false negatives leak PII
- **Always log arguments** rejected — arguments can contain sensitive data too (less flexible than full configurability)
