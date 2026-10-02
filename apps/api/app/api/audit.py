from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit_event import AuditEvent
from app.schemas.audit import AuditEventListResponse, AuditEventResponse, AuditStatsResponse

router = APIRouter(prefix="/audit", tags=["audit"])


def _to_response(e: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
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
        events=[_to_response(e) for e in events],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=AuditStatsResponse)
async def audit_stats(
    agent_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Aggregate audit statistics for the dashboard."""
    base = select(func.count()).select_from(AuditEvent)
    if agent_id:
        base = base.where(AuditEvent.agent_id == agent_id)

    total = (await db.execute(base)).scalar() or 0

    by_decision = {}
    for d in ("ALLOW", "DENY", "APPROVAL_REQUIRED", "ALLOW_APPROVED"):
        q = base.where(AuditEvent.decision == d)
        by_decision[d] = (await db.execute(q)).scalar() or 0

    top_tools_q = (
        select(AuditEvent.tool_name, func.count().label("count"))
        .group_by(AuditEvent.tool_name)
        .order_by(func.count().desc())
        .limit(10)
    )
    if agent_id:
        top_tools_q = top_tools_q.where(AuditEvent.agent_id == agent_id)
    top_tools_result = await db.execute(top_tools_q)
    top_tools = [{"tool_name": row[0], "count": row[1]} for row in top_tools_result.all()]

    avg_latency_q = select(func.avg(AuditEvent.latency_ms)).select_from(AuditEvent)
    if agent_id:
        avg_latency_q = avg_latency_q.where(AuditEvent.agent_id == agent_id)
    avg_latency = (await db.execute(avg_latency_q)).scalar()

    return AuditStatsResponse(
        total_events=total,
        by_decision=by_decision,
        top_tools=top_tools,
        avg_latency_ms=round(avg_latency, 1) if avg_latency else None,
    )


@router.get("/{event_id}", response_model=AuditEventResponse)
async def get_audit_event(event_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuditEvent).where(AuditEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return _to_response(event)
