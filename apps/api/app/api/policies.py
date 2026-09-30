from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.policy import Policy
from app.schemas.policy import PolicyCreate, PolicyResponse, PolicyUpdate

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(body: PolicyCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Policy).where(Policy.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Policy name already exists")

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


@router.get("", response_model=list[PolicyResponse])
async def list_policies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Policy).order_by(Policy.priority.desc()))
    policies = result.scalars().all()
    return [
        PolicyResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            cedar_policy=p.cedar_policy,
            priority=p.priority,
            enabled=p.enabled,
            metadata=p.metadata_,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in policies
    ]


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(policy_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
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


@router.patch("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str, body: PolicyUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    if body.name is not None:
        policy.name = body.name
    if body.description is not None:
        policy.description = body.description
    if body.cedar_policy is not None:
        policy.cedar_policy = body.cedar_policy
    if body.priority is not None:
        policy.priority = body.priority
    if body.enabled is not None:
        policy.enabled = body.enabled
    if body.metadata is not None:
        policy.metadata_ = body.metadata

    await db.commit()
    await db.refresh(policy)

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


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(policy_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    await db.delete(policy)
    await db.commit()
