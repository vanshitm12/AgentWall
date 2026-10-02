from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.approval import Approval
from app.schemas.approval import ApprovalDecision, ApprovalResponse

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _to_response(a: Approval) -> ApprovalResponse:
    return ApprovalResponse(
        id=a.id,
        audit_event_id=a.audit_event_id,
        agent_id=a.agent_id,
        tool_name=a.tool_name,
        arguments=a.arguments,
        arguments_hash=a.arguments_hash,
        status=a.status,
        risk_score=a.risk_score,
        risk_level=a.risk_level,
        reason=a.reason,
        reviewer=a.reviewer,
        decided_at=a.decided_at,
        expires_at=a.expires_at,
        created_at=a.created_at,
    )


@router.get("", response_model=list[ApprovalResponse])
async def list_approvals(
    status_filter: str | None = None,
    agent_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Approval).order_by(Approval.created_at.desc())
    if status_filter:
        query = query.where(Approval.status == status_filter)
    if agent_id:
        query = query.where(Approval.agent_id == agent_id)
    result = await db.execute(query)
    return [_to_response(a) for a in result.scalars().all()]


@router.get("/pending", response_model=list[ApprovalResponse])
async def list_pending_approvals(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Approval)
        .where(Approval.status == "PENDING")
        .order_by(Approval.created_at.desc())
    )
    return [_to_response(a) for a in result.scalars().all()]


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(approval_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return _to_response(approval)


@router.post("/{approval_id}/decide", response_model=ApprovalResponse)
async def decide_approval(
    approval_id: str,
    body: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Approval already {approval.status}")

    if approval.expires_at and approval.expires_at < datetime.now(timezone.utc):
        approval.status = "EXPIRED"
        await db.commit()
        raise HTTPException(status_code=410, detail="Approval has expired")

    approval.status = body.status
    approval.reviewer = body.reviewer
    approval.reason = body.reason
    approval.decided_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(approval)

    return _to_response(approval)
