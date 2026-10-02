"""Synchronous audit event writer.

Every tool call decision (ALLOW, DENY, APPROVAL_REQUIRED) is recorded
as an AuditEvent in PostgreSQL. This is a synchronous write — the proxy
waits for the audit record to be committed before returning the response
to the agent. This guarantees no decision goes unrecorded.

Audit log levels (per ADR-007):
  METADATA   — tool_name, agent_id, decision, latency, policy. No arguments or response.
  ARGS_ONLY  — above + arguments (default)
  FULL       — above + arguments + response

Per-tool audit_log_level overrides the global default.
"""

import logging

from app.config import settings
from app.database import async_session
from app.models.audit_event import AuditEvent

logger = logging.getLogger(__name__)

VALID_LEVELS = {"METADATA", "ARGS_ONLY", "FULL"}


def _effective_level(tool_level: str | None) -> str:
    """Per-tool override wins; fall back to global default."""
    if tool_level and tool_level in VALID_LEVELS:
        return tool_level
    return settings.default_audit_log_level


async def write_audit_event(
    agent_id: str,
    session_id: str,
    tool_name: str,
    decision: str,
    server_id: str | None = None,
    policy_id: str | None = None,
    arguments: dict | None = None,
    response: dict | None = None,
    approval_id: str | None = None,
    latency_ms: int | None = None,
    error: str | None = None,
    tool_audit_level: str | None = None,
    metadata: dict | None = None,
    risk_score: int | None = None,
    risk_level: str | None = None,
) -> AuditEvent:
    """Write an audit event, applying sensitivity level filtering."""
    level = _effective_level(tool_audit_level)

    filtered_args = None
    filtered_response = None

    if level in ("ARGS_ONLY", "FULL"):
        filtered_args = arguments
    if level == "FULL":
        filtered_response = response

    event = AuditEvent(
        agent_id=agent_id,
        session_id=session_id,
        server_id=server_id,
        tool_name=tool_name,
        decision=decision,
        policy_id=policy_id,
        risk_score=risk_score,
        risk_level=risk_level,
        arguments=filtered_args,
        response=filtered_response,
        approval_id=approval_id,
        latency_ms=latency_ms,
        error=error,
        metadata_=metadata or {},
    )

    async with async_session() as db:
        db.add(event)
        await db.commit()
        await db.refresh(event)

    logger.info(
        "AUDIT | %s | agent=%s | tool=%s | policy=%s | latency=%sms | level=%s",
        decision, agent_id[:8], tool_name, policy_id and policy_id[:8], latency_ms, level,
    )

    return event
