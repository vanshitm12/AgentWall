from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tool import Tool
from app.schemas.tool import ToolResponse, ToolUpdate

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=list[ToolResponse])
async def list_tools(
    server_id: str | None = None,
    risk: str | None = Query(default=None, alias="risk_classification"),
    enabled: bool | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Tool).order_by(Tool.name)
    if server_id:
        query = query.where(Tool.server_id == server_id)
    if risk:
        query = query.where(Tool.risk_classification == risk)
    if enabled is not None:
        query = query.where(Tool.enabled == enabled)
    if search:
        query = query.where(Tool.name.ilike(f"%{search}%"))
    result = await db.execute(query)
    tools = result.scalars().all()
    return [_to_response(t) for t in tools]


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(tool_id: str, db: AsyncSession = Depends(get_db)):
    tool = await _get_or_404(tool_id, db)
    return _to_response(tool)


@router.patch("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str, body: ToolUpdate, db: AsyncSession = Depends(get_db)
):
    tool = await _get_or_404(tool_id, db)

    if body.risk_classification is not None:
        tool.risk_classification = body.risk_classification
    if "audit_log_level" in body.model_fields_set:
        if body.audit_log_level is not None and body.audit_log_level not in ("METADATA", "ARGS_ONLY", "FULL"):
            raise HTTPException(status_code=422, detail="audit_log_level must be METADATA, ARGS_ONLY, FULL, or null")
        tool.audit_log_level = body.audit_log_level
    if body.enabled is not None:
        tool.enabled = body.enabled
    if body.metadata is not None:
        tool.metadata_ = body.metadata

    await db.commit()
    await db.refresh(tool)

    return _to_response(tool)


def _to_response(tool: Tool) -> ToolResponse:
    return ToolResponse(
        id=tool.id,
        server_id=tool.server_id,
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema,
        risk_classification=tool.risk_classification,
        audit_log_level=tool.audit_log_level,
        enabled=tool.enabled,
        metadata=tool.metadata_,
        created_at=tool.created_at,
    )


async def _get_or_404(tool_id: str, db: AsyncSession) -> Tool:
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool
