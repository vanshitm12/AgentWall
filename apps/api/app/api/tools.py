from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tool import Tool
from app.schemas.tool import ToolResponse, ToolUpdate

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=list[ToolResponse])
async def list_tools(
    server_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Tool).order_by(Tool.name)
    if server_id:
        query = query.where(Tool.server_id == server_id)
    result = await db.execute(query)
    tools = result.scalars().all()
    return [
        ToolResponse(
            id=t.id,
            server_id=t.server_id,
            name=t.name,
            description=t.description,
            input_schema=t.input_schema,
            risk_classification=t.risk_classification,
            audit_log_level=t.audit_log_level,
            metadata=t.metadata_,
            created_at=t.created_at,
        )
        for t in tools
    ]


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(tool_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return ToolResponse(
        id=tool.id,
        server_id=tool.server_id,
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema,
        risk_classification=tool.risk_classification,
        audit_log_level=tool.audit_log_level,
        metadata=tool.metadata_,
        created_at=tool.created_at,
    )


@router.patch("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str, body: ToolUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    if body.risk_classification is not None:
        tool.risk_classification = body.risk_classification
    if body.audit_log_level is not None:
        tool.audit_log_level = body.audit_log_level
    if body.metadata is not None:
        tool.metadata_ = body.metadata

    await db.commit()
    await db.refresh(tool)

    return ToolResponse(
        id=tool.id,
        server_id=tool.server_id,
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema,
        risk_classification=tool.risk_classification,
        audit_log_level=tool.audit_log_level,
        metadata=tool.metadata_,
        created_at=tool.created_at,
    )
