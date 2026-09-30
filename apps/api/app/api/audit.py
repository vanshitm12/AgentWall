from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit_event import AuditEvent
from app.schemas.audit import AuditEventListResponse, AuditEventResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditEventListResponse)
async def list_audit_events(
    agent_id: str | None = None,
    tool_name: str | None = None,
    decision: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditEvent).order_by(AuditEvent.timestamp.desc())
    count_query = select(func.count()).select_from(AuditEvent)

    if agent_id:
        query = query.where(AuditEvent.agent_id == agent_id)
        count_query = count_query.where(AuditEvent.agent_id == agent_id)
    if tool_name:
        query = query.where(AuditEvent.tool_name == tool_name)
        count_query = count_query.where(AuditEvent.tool_name == tool_name)
    if decision:
        query = query.where(AuditEvent.decision == decision)
        count_query = count_query.where(AuditEvent.decision == decision)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    events = result.scalars().all()

    return AuditEventListResponse(
        events=[
            AuditEventResponse(
                id=e.id,
                timestamp=e.timestamp,
                agent_id=e.agent_id,
                session_id=e.session_id,
                server_id=e.server_id,
                tool_name=e.tool_name,
                decision=e.decision,
                policy_id=e.policy_id,
                risk_score=e.risk_score,
                risk_level=e.risk_level,
                arguments=e.arguments,
                response=e.response,
                approval_id=e.approval_id,
                latency_ms=e.latency_ms,
                error=e.error,
                metadata=e.metadata_,
            )
            for e in events
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
