"""DLP scanning REST API.

Provides endpoints for testing DLP scanning without making actual tool calls.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.dlp.scanner import (
    BUILT_IN_PATTERNS,
    scan_dict,
    scan_text,
    findings_to_summary,
    redact_dict,
    redact_text,
    has_block_finding,
)

router = APIRouter(prefix="/dlp", tags=["dlp"])


class DlpScanRequest(BaseModel):
    text: str | None = None
    data: dict | None = None


class DlpPatternInfo(BaseModel):
    name: str
    category: str
    action: str
    description: str


class DlpScanResponse(BaseModel):
    findings: list[dict]
    would_block: bool
    redacted_text: str | None = None
    redacted_data: dict | None = None


@router.post("/scan", response_model=DlpScanResponse)
async def scan_for_sensitive_data(req: DlpScanRequest):
    """Scan text or structured data for sensitive content."""
    findings = []

    if req.text:
        findings.extend(scan_text(req.text))
    if req.data:
        findings.extend(scan_dict(req.data))

    summary = findings_to_summary(findings)
    would_block = has_block_finding(findings)

    redacted_t = redact_text(req.text) if req.text else None
    redacted_d = redact_dict(req.data) if req.data else None

    return DlpScanResponse(
        findings=summary,
        would_block=would_block,
        redacted_text=redacted_t,
        redacted_data=redacted_d,
    )


@router.get("/patterns", response_model=list[DlpPatternInfo])
async def list_dlp_patterns():
    """List all active DLP patterns."""
    return [
        DlpPatternInfo(
            name=p.name,
            category=p.category.value,
            action=p.action.value,
            description=p.description,
        )
        for p in BUILT_IN_PATTERNS
    ]
