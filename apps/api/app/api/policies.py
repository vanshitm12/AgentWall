from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.policy import Policy
from app.policy.engine import policy_engine
from app.schemas.policy import PolicyCreate, PolicyResponse, PolicyUpdate

router = APIRouter(prefix="/policies", tags=["policies"])


def _validate_cedar(cedar_text: str) -> None:
    """Validate that the Cedar policy text is syntactically valid.

    We run a dummy evaluation and check for parse errors only.
    Evaluation errors (e.g. missing context attributes) are expected
    because the dummy request has no context — those are not syntax issues.
    """
    import cedarpy

    try:
        result = cedarpy.is_authorized(
            {
                "principal": 'User::"__validation_test__"',
                "action": 'Action::"call"',
                "resource": 'Tool::"__validation_test__"',
            },
            cedar_text,
            [],
        )
        parse_errors = [
            e for e in (result.diagnostics.errors or [])
            if "parse error" in e.lower()
        ]
        if parse_errors:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid Cedar policy syntax: {'; '.join(parse_errors)}",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid Cedar policy syntax: {e}",
        )


def _to_response(policy: Policy) -> PolicyResponse:
    return PolicyResponse(
        id=policy.id,
        name=policy.name,
        description=policy.description,
        cedar_policy=policy.cedar_policy,
        priority=policy.priority,
        enabled=policy.enabled,
        metadata=policy.metadata_,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(body: PolicyCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Policy).where(Policy.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Policy name already exists")

    _validate_cedar(body.cedar_policy)

    policy = Policy(
        name=body.name,
        description=body.description,
        cedar_policy=body.cedar_policy,
        priority=body.priority,
        enabled=body.enabled,
        metadata_=body.metadata,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    policy_engine.invalidate_cache()

    return _to_response(policy)


@router.get("", response_model=list[PolicyResponse])
async def list_policies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Policy).order_by(Policy.priority.desc()))
    policies = result.scalars().all()
    return [_to_response(p) for p in policies]


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(policy_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _to_response(policy)


@router.patch("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str, body: PolicyUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    if body.cedar_policy is not None:
        _validate_cedar(body.cedar_policy)
        policy.cedar_policy = body.cedar_policy
    if body.name is not None:
        policy.name = body.name
    if body.description is not None:
        policy.description = body.description
    if body.priority is not None:
        policy.priority = body.priority
    if body.enabled is not None:
        policy.enabled = body.enabled
    if body.metadata is not None:
        policy.metadata_ = body.metadata

    await db.commit()
    await db.refresh(policy)

    policy_engine.invalidate_cache()

    return _to_response(policy)


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(policy_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    await db.delete(policy)
    await db.commit()

    policy_engine.invalidate_cache()


@router.post("/validate")
async def validate_policy(body: PolicyCreate):
    """Validate Cedar policy syntax without saving."""
    _validate_cedar(body.cedar_policy)
    return {"valid": True, "name": body.name}
