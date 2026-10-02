"""AgentWall MCP Proxy — the core security boundary.

The proxy:
1. Authenticates the agent (API key → session)
2. Intercepts every JSON-RPC message
3. For tools/list: aggregates tools from all downstream servers
4. For tools/call: kill switch → risk scoring → auto-deny → DLP scan (args) →
   approval check → policy evaluation → forward → DLP scan (response) → audit
5. Returns responses to the agent
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.audit.writer import write_audit_event
from app.config import settings
from app.database import async_session
from app.killswitch.engine import check_kill_switch
from app.dlp.scanner import (
    findings_to_summary,
    has_block_finding,
    has_redact_finding,
    redact_content_list,
    redact_dict,
    scan_content_list,
    scan_dict,
)
from app.models.agent import Agent
from app.models.approval import Approval
from app.models.tool import Tool
from app.mcp.downstream import downstream_manager
from app.mcp.session import session_manager
from app.policy.engine import PolicyDecision, policy_engine
from app.risk.engine import score_tool_call

logger = logging.getLogger(__name__)

router = APIRouter()

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "agentwall", "version": "0.1.0"}
APPROVAL_TTL_SECONDS = 3600


def jsonrpc_response(id: int | str | None, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def jsonrpc_error(id: int | str | None, code: int, message: str, data: dict | None = None) -> dict:
    error: dict = {"code": code, "message": message}
    if data:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": error}


def _hash_arguments(arguments: dict | None) -> str:
    canonical = json.dumps(arguments or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def _authenticate(request: Request) -> tuple[str | None, str | None, str | None]:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None, "Missing or invalid Authorization header"

    api_key = auth_header.removeprefix("Bearer ").strip()
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    async with async_session() as db:
        result = await db.execute(select(Agent).where(Agent.api_key_hash == key_hash))
        agent = result.scalar_one_or_none()

    if agent is None:
        return None, None, "Invalid API key"
    if agent.status == "KILLED":
        return None, None, "Agent has been killed"
    if agent.status == "SUSPENDED":
        return None, None, "Agent is suspended"

    return agent.id, agent.name, None


async def _get_session_agent(session_id: str) -> tuple[str | None, str | None, str | None]:
    agent_id = await session_manager.get_agent_id(session_id)
    if not agent_id:
        return None, None, "Invalid or expired session"

    async with async_session() as db:
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()

    if not agent:
        return None, None, "Agent not found"
    if agent.status in ("KILLED", "SUSPENDED"):
        await session_manager.destroy(session_id)
        return None, None, f"Agent is {agent.status.lower()}"

    return agent_id, agent.name, None


async def _handle_initialize(msg_id: int | str | None) -> dict:
    return jsonrpc_response(
        msg_id,
        {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        },
    )


async def _handle_ping(msg_id: int | str | None) -> dict:
    return jsonrpc_response(msg_id, {})


async def _handle_tools_list(msg_id: int | str | None) -> dict:
    tools = downstream_manager.list_all_tools()
    return jsonrpc_response(msg_id, {"tools": tools})


async def _check_existing_approval(
    agent_id: str, tool_name: str, arguments_hash: str
) -> Approval | None:
    async with async_session() as db:
        result = await db.execute(
            select(Approval)
            .where(
                Approval.agent_id == agent_id,
                Approval.tool_name == tool_name,
                Approval.arguments_hash == arguments_hash,
                Approval.status == "APPROVED",
            )
            .order_by(Approval.decided_at.desc())
            .limit(1)
        )
        approval = result.scalar_one_or_none()

    if not approval:
        return None

    if approval.expires_at and approval.expires_at < datetime.now(timezone.utc):
        async with async_session() as db:
            result = await db.execute(select(Approval).where(Approval.id == approval.id))
            a = result.scalar_one()
            a.status = "EXPIRED"
            await db.commit()
        return None

    return approval


async def _consume_approval(approval_id: str) -> None:
    async with async_session() as db:
        result = await db.execute(select(Approval).where(Approval.id == approval_id))
        approval = result.scalar_one_or_none()
        if approval:
            approval.status = "EXECUTED"
            await db.commit()


async def _create_approval(
    agent_id: str, tool_name: str, arguments: dict | None, arguments_hash: str,
    policy_name: str | None, risk_score: int | None = None, risk_level: str | None = None,
) -> Approval:
    approval = Approval(
        agent_id=agent_id,
        tool_name=tool_name,
        arguments=arguments,
        arguments_hash=arguments_hash,
        status="PENDING",
        reason=f"Approval required by policy: {policy_name}" if policy_name else None,
        risk_score=risk_score,
        risk_level=risk_level,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=APPROVAL_TTL_SECONDS),
    )

    async with async_session() as db:
        db.add(approval)
        await db.commit()
        await db.refresh(approval)

    logger.info(
        "Approval created: id=%s | agent=%s | tool=%s | risk=%s/%s | expires=%s",
        approval.id, agent_id, tool_name, risk_score, risk_level, approval.expires_at,
    )
    return approval


def _build_audit_metadata(
    risk_factors: list[str] | None = None,
    dlp_findings: list[dict] | None = None,
    extra: dict | None = None,
) -> dict:
    meta: dict = {}
    if risk_factors:
        meta["risk_factors"] = risk_factors
    if dlp_findings:
        meta["dlp_findings"] = dlp_findings
    if extra:
        meta.update(extra)
    return meta


async def _handle_tools_call(
    msg_id: int | str | None,
    params: dict,
    agent_id: str,
    agent_name: str,
    session_id: str,
) -> dict:
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    start = time.monotonic()

    # ── Kill switch (fastest check — Redis only) ──
    kill_reason = await check_kill_switch(agent_id)
    if kill_reason:
        return jsonrpc_error(msg_id, -32603, f"Agent blocked: {kill_reason}")

    resolved = downstream_manager.resolve_tool(tool_name)
    if not resolved:
        return jsonrpc_error(msg_id, -32602, f"Unknown tool: {tool_name}")

    server_id, original_name, server = resolved

    async with async_session() as db:
        result = await db.execute(
            select(Tool).where(Tool.server_id == server_id, Tool.name == tool_name)
        )
        tool_record = result.scalar_one_or_none()

    risk_classification = "MEDIUM"
    tool_audit_level = None
    if tool_record:
        if not tool_record.enabled:
            return jsonrpc_error(msg_id, -32603, f"Tool is disabled: {tool_name}")
        risk_classification = tool_record.risk_classification
        tool_audit_level = tool_record.audit_log_level

    server_trust_level = "TRUSTED"

    # ── Risk scoring ──
    risk_result = await score_tool_call(
        agent_id=agent_id,
        tool_name=tool_name,
        risk_classification=risk_classification,
        server_trust_level=server_trust_level,
        arguments=arguments,
    )

    # Auto-deny if risk score exceeds threshold
    if risk_result.score >= settings.risk_auto_deny_threshold:
        latency = int((time.monotonic() - start) * 1000)
        await write_audit_event(
            agent_id=agent_id, session_id=session_id, tool_name=tool_name,
            decision="DENY", server_id=server_id,
            risk_score=risk_result.score, risk_level=risk_result.level,
            arguments=arguments, latency_ms=latency,
            error=f"auto-deny: risk score {risk_result.score} >= threshold {settings.risk_auto_deny_threshold}",
            tool_audit_level=tool_audit_level,
            metadata=_build_audit_metadata(risk_factors=risk_result.factors),
        )
        return jsonrpc_error(
            msg_id, -32603,
            f"Risk auto-deny: {tool_name} (score={risk_result.score}, level={risk_result.level})",
            data={"risk_score": risk_result.score, "risk_level": risk_result.level, "risk_factors": risk_result.factors},
        )

    # ── DLP scan on arguments ──
    arg_dlp_findings = scan_dict(arguments)
    dlp_summary = findings_to_summary(arg_dlp_findings) if arg_dlp_findings else []

    if has_block_finding(arg_dlp_findings):
        latency = int((time.monotonic() - start) * 1000)
        await write_audit_event(
            agent_id=agent_id, session_id=session_id, tool_name=tool_name,
            decision="DENY", server_id=server_id,
            risk_score=risk_result.score, risk_level=risk_result.level,
            arguments=arguments, latency_ms=latency,
            error=f"DLP blocked: sensitive data in arguments ({len(arg_dlp_findings)} findings)",
            tool_audit_level=tool_audit_level,
            metadata=_build_audit_metadata(dlp_findings=dlp_summary),
        )
        return jsonrpc_error(
            msg_id, -32603,
            f"DLP blocked: sensitive data detected in arguments for {tool_name}",
            data={"dlp_findings": dlp_summary},
        )

    forward_arguments = arguments
    if has_redact_finding(arg_dlp_findings):
        forward_arguments = redact_dict(arguments)

    # ── Check existing approval ──
    args_hash = _hash_arguments(arguments)
    existing_approval = await _check_existing_approval(agent_id, tool_name, args_hash)

    if existing_approval:
        try:
            call_result = await downstream_manager.call_tool(tool_name, forward_arguments)
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            await write_audit_event(
                agent_id=agent_id, session_id=session_id, tool_name=tool_name,
                decision="ALLOW_APPROVED", server_id=server_id,
                approval_id=existing_approval.id,
                risk_score=risk_result.score, risk_level=risk_result.level,
                arguments=arguments, latency_ms=latency,
                error=str(e), tool_audit_level=tool_audit_level,
                metadata=_build_audit_metadata(dlp_findings=dlp_summary) if dlp_summary else None,
            )
            return jsonrpc_error(msg_id, -32603, f"Tool execution failed: {e}")

        await _consume_approval(existing_approval.id)

        latency = int((time.monotonic() - start) * 1000)
        response_content = _format_result_content(call_result) if call_result else None

        # DLP scan on response
        resp_dlp_findings = []
        if response_content:
            resp_dlp_findings = scan_content_list(response_content)
            if has_block_finding(resp_dlp_findings):
                resp_dlp_summary = findings_to_summary(resp_dlp_findings)
                await write_audit_event(
                    agent_id=agent_id, session_id=session_id, tool_name=tool_name,
                    decision="ALLOW_APPROVED", server_id=server_id,
                    approval_id=existing_approval.id,
                    risk_score=risk_result.score, risk_level=risk_result.level,
                    arguments=arguments, latency_ms=latency,
                    error=f"DLP blocked response ({len(resp_dlp_findings)} findings)",
                    tool_audit_level=tool_audit_level,
                    metadata=_build_audit_metadata(dlp_findings=resp_dlp_summary),
                )
                return jsonrpc_error(
                    msg_id, -32603,
                    f"DLP blocked: sensitive data detected in response from {tool_name}",
                    data={"dlp_findings": resp_dlp_summary},
                )
            if has_redact_finding(resp_dlp_findings):
                response_content = redact_content_list(response_content)

        all_dlp = dlp_summary + findings_to_summary(resp_dlp_findings)
        await write_audit_event(
            agent_id=agent_id, session_id=session_id, tool_name=tool_name,
            decision="ALLOW_APPROVED", server_id=server_id,
            approval_id=existing_approval.id,
            risk_score=risk_result.score, risk_level=risk_result.level,
            arguments=arguments, response={"content": response_content} if response_content else None,
            latency_ms=latency, tool_audit_level=tool_audit_level,
            metadata=_build_audit_metadata(dlp_findings=all_dlp) if all_dlp else None,
        )

        if call_result is None:
            return jsonrpc_error(msg_id, -32603, "No result from downstream server")

        content = response_content if response_content else _format_result_content(call_result)
        return jsonrpc_response(
            msg_id,
            {"content": content, "isError": call_result.is_error if call_result.is_error else False},
        )

    # ── Policy evaluation (with risk in context) ──
    eval_result = await policy_engine.evaluate(
        agent_id=agent_id,
        agent_name=agent_name,
        tool_name=tool_name,
        server_name=server.name,
        risk_classification=risk_classification,
        server_trust_level=server_trust_level,
        arguments=arguments,
        risk_score=risk_result.score,
        risk_level=risk_result.level,
    )

    if eval_result.decision == PolicyDecision.DENY:
        latency = int((time.monotonic() - start) * 1000)
        await write_audit_event(
            agent_id=agent_id, session_id=session_id, tool_name=tool_name,
            decision="DENY", server_id=server_id, policy_id=eval_result.policy_id,
            risk_score=risk_result.score, risk_level=risk_result.level,
            arguments=arguments, latency_ms=latency,
            error=", ".join(eval_result.reasons or []),
            tool_audit_level=tool_audit_level,
            metadata=_build_audit_metadata(dlp_findings=dlp_summary) if dlp_summary else None,
        )
        return jsonrpc_error(
            msg_id, -32603,
            f"Policy denied: {tool_name} (reason: {', '.join(eval_result.reasons or ['default-deny'])})",
        )

    if eval_result.decision == PolicyDecision.APPROVAL_REQUIRED:
        approval = await _create_approval(
            agent_id=agent_id,
            tool_name=tool_name,
            arguments=arguments,
            arguments_hash=args_hash,
            policy_name=eval_result.policy_name,
            risk_score=risk_result.score,
            risk_level=risk_result.level,
        )
        latency = int((time.monotonic() - start) * 1000)
        await write_audit_event(
            agent_id=agent_id, session_id=session_id, tool_name=tool_name,
            decision="APPROVAL_REQUIRED", server_id=server_id,
            policy_id=eval_result.policy_id, approval_id=approval.id,
            risk_score=risk_result.score, risk_level=risk_result.level,
            arguments=arguments, latency_ms=latency,
            tool_audit_level=tool_audit_level,
            metadata=_build_audit_metadata(dlp_findings=dlp_summary) if dlp_summary else None,
        )
        return jsonrpc_error(
            msg_id, -32001,
            f"Approval required for {tool_name}. Request has been queued for human review.",
            data={"approval_id": approval.id, "risk_score": risk_result.score, "risk_level": risk_result.level},
        )

    # ALLOW — forward the call
    try:
        call_result = await downstream_manager.call_tool(tool_name, forward_arguments)
    except Exception as e:
        latency = int((time.monotonic() - start) * 1000)
        await write_audit_event(
            agent_id=agent_id, session_id=session_id, tool_name=tool_name,
            decision="ALLOW", server_id=server_id, policy_id=eval_result.policy_id,
            risk_score=risk_result.score, risk_level=risk_result.level,
            arguments=arguments, latency_ms=latency,
            error=str(e), tool_audit_level=tool_audit_level,
            metadata=_build_audit_metadata(dlp_findings=dlp_summary) if dlp_summary else None,
        )
        return jsonrpc_error(msg_id, -32603, f"Tool execution failed: {e}")

    latency = int((time.monotonic() - start) * 1000)
    response_content = _format_result_content(call_result) if call_result else None

    # ── DLP scan on response ──
    resp_dlp_findings = []
    if response_content:
        resp_dlp_findings = scan_content_list(response_content)
        if has_block_finding(resp_dlp_findings):
            resp_dlp_summary = findings_to_summary(resp_dlp_findings)
            await write_audit_event(
                agent_id=agent_id, session_id=session_id, tool_name=tool_name,
                decision="ALLOW", server_id=server_id, policy_id=eval_result.policy_id,
                risk_score=risk_result.score, risk_level=risk_result.level,
                arguments=arguments, latency_ms=latency,
                error=f"DLP blocked response ({len(resp_dlp_findings)} findings)",
                tool_audit_level=tool_audit_level,
                metadata=_build_audit_metadata(dlp_findings=resp_dlp_summary),
            )
            return jsonrpc_error(
                msg_id, -32603,
                f"DLP blocked: sensitive data detected in response from {tool_name}",
                data={"dlp_findings": resp_dlp_summary},
            )
        if has_redact_finding(resp_dlp_findings):
            response_content = redact_content_list(response_content)

    all_dlp = dlp_summary + findings_to_summary(resp_dlp_findings)
    await write_audit_event(
        agent_id=agent_id, session_id=session_id, tool_name=tool_name,
        decision="ALLOW", server_id=server_id, policy_id=eval_result.policy_id,
        risk_score=risk_result.score, risk_level=risk_result.level,
        arguments=arguments, response={"content": response_content} if response_content else None,
        latency_ms=latency, tool_audit_level=tool_audit_level,
        metadata=_build_audit_metadata(dlp_findings=all_dlp) if all_dlp else None,
    )

    if call_result is None:
        return jsonrpc_error(msg_id, -32603, "No result from downstream server")

    content = response_content if response_content else _format_result_content(call_result)
    return jsonrpc_response(
        msg_id,
        {"content": content, "isError": call_result.is_error if call_result.is_error else False},
    )


def _format_result_content(result) -> list[dict]:
    content = []
    for item in result.content:
        if hasattr(item, "text"):
            content.append({"type": "text", "text": item.text})
        elif hasattr(item, "data"):
            content.append({"type": "image", "data": item.data, "mimeType": item.mime_type})
        else:
            content.append({"type": "text", "text": str(item)})
    return content


@router.post("/mcp")
async def mcp_post(request: Request) -> JSONResponse:
    session_id = request.headers.get("mcp-session-id")
    agent_id: str | None = None
    agent_name: str | None = None

    if session_id:
        agent_id, agent_name, error = await _get_session_agent(session_id)
        if error:
            return JSONResponse(status_code=401, content={"error": error})
    else:
        agent_id, agent_name, error = await _authenticate(request)
        if error:
            return JSONResponse(status_code=401, content={"error": error})
        assert agent_id is not None
        session_id = await session_manager.create(agent_id)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content=jsonrpc_error(None, -32700, "Parse error"),
        )

    if isinstance(body, list):
        responses = []
        for msg in body:
            resp = await _process_message(msg, agent_id, agent_name or "", session_id)
            if resp is not None:
                responses.append(resp)
        if not responses:
            return JSONResponse(status_code=202, content=None)
        result = responses if len(responses) > 1 else responses[0]
        return JSONResponse(content=result, headers={"Mcp-Session-Id": session_id})

    response = await _process_message(body, agent_id, agent_name or "", session_id)
    if response is None:
        return JSONResponse(
            status_code=202, content=None,
            headers={"Mcp-Session-Id": session_id},
        )

    return JSONResponse(content=response, headers={"Mcp-Session-Id": session_id})


@router.delete("/mcp")
async def mcp_delete(request: Request) -> JSONResponse:
    session_id = request.headers.get("mcp-session-id")
    if session_id:
        await session_manager.destroy(session_id)
    return JSONResponse(status_code=200, content={"terminated": True})


async def _process_message(
    msg: dict, agent_id: str, agent_name: str, session_id: str
) -> dict | None:
    msg_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params", {})

    if msg_id is None:
        return None

    if method == "initialize":
        return await _handle_initialize(msg_id)
    elif method == "ping":
        return await _handle_ping(msg_id)
    elif method == "tools/list":
        return await _handle_tools_list(msg_id)
    elif method == "tools/call":
        return await _handle_tools_call(msg_id, params, agent_id, agent_name, session_id)
    elif method == "resources/list":
        return jsonrpc_response(msg_id, {"resources": []})
    elif method == "prompts/list":
        return jsonrpc_response(msg_id, {"prompts": []})
    else:
        return jsonrpc_error(msg_id, -32601, f"Method not found: {method}")
