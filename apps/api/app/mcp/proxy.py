"""AgentWall MCP Proxy — the core security boundary.

This module implements the agent-facing MCP endpoint using the
Streamable HTTP transport protocol. Agents connect here as if
AgentWall were a normal MCP server.

The proxy:
1. Authenticates the agent (API key → session)
2. Intercepts every JSON-RPC message
3. For tools/list: aggregates tools from all downstream servers
4. For tools/call: forwards to the correct downstream server
5. Returns responses to the agent

Phase 1: ALLOW EVERYTHING — no policy evaluation yet.
The goal is to prove the proxy networking layer works.
"""

import hashlib
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.database import async_session
from app.models.agent import Agent
from app.mcp.downstream import downstream_manager
from app.mcp.session import session_manager

logger = logging.getLogger(__name__)

router = APIRouter()

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "agentwall", "version": "0.1.0"}


def jsonrpc_response(id: int | str | None, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def jsonrpc_error(id: int | str | None, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


async def _authenticate(request: Request) -> tuple[str | None, str | None]:
    """Authenticate via API key. Returns (agent_id, error_message)."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, "Missing or invalid Authorization header"

    api_key = auth_header.removeprefix("Bearer ").strip()
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    async with async_session() as db:
        result = await db.execute(select(Agent).where(Agent.api_key_hash == key_hash))
        agent = result.scalar_one_or_none()

    if agent is None:
        return None, "Invalid API key"

    if agent.status == "KILLED":
        return None, "Agent has been killed"

    if agent.status == "SUSPENDED":
        return None, "Agent is suspended"

    return agent.id, None


async def _get_session_agent_id(session_id: str) -> tuple[str | None, str | None]:
    """Look up agent from session. Returns (agent_id, error_message)."""
    agent_id = await session_manager.get_agent_id(session_id)
    if not agent_id:
        return None, "Invalid or expired session"

    async with async_session() as db:
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()

    if not agent:
        return None, "Agent not found"

    if agent.status in ("KILLED", "SUSPENDED"):
        await session_manager.destroy(session_id)
        return None, f"Agent is {agent.status.lower()}"

    return agent_id, None


async def _handle_initialize(msg_id: int | str | None) -> dict:
    """Handle the MCP initialize request."""
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
    """Aggregate tools from all downstream servers and return."""
    tools = downstream_manager.list_all_tools()
    return jsonrpc_response(msg_id, {"tools": tools})


async def _handle_tools_call(
    msg_id: int | str | None,
    params: dict,
    agent_id: str,
    session_id: str,
) -> dict:
    """Forward a tool call to the correct downstream server."""
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    start = time.monotonic()

    resolved = downstream_manager.resolve_tool(tool_name)
    if not resolved:
        return jsonrpc_error(msg_id, -32602, f"Unknown tool: {tool_name}")

    server_id, original_name, server = resolved

    logger.info(
        "ALLOW | agent=%s | tool=%s | server=%s (Phase 1: allow everything)",
        agent_id,
        tool_name,
        server.name,
    )

    try:
        result = await downstream_manager.call_tool(tool_name, arguments)
    except Exception as e:
        latency = int((time.monotonic() - start) * 1000)
        logger.error(
            "Tool call failed: %s → %s (latency=%dms, error=%s)",
            tool_name,
            server.name,
            latency,
            str(e),
        )
        return jsonrpc_error(msg_id, -32603, f"Tool execution failed: {e}")

    latency = int((time.monotonic() - start) * 1000)
    logger.info(
        "Tool call completed: %s → %s (latency=%dms)",
        tool_name,
        server.name,
        latency,
    )

    if result is None:
        return jsonrpc_error(msg_id, -32603, "No result from downstream server")

    content = []
    for item in result.content:
        if hasattr(item, "text"):
            content.append({"type": "text", "text": item.text})
        elif hasattr(item, "data"):
            content.append({"type": "image", "data": item.data, "mimeType": item.mimeType})
        else:
            content.append({"type": "text", "text": str(item)})

    return jsonrpc_response(
        msg_id,
        {"content": content, "isError": result.isError if result.isError else False},
    )


@router.post("/mcp")
async def mcp_post(request: Request) -> JSONResponse:
    """Handle MCP Streamable HTTP POST requests.

    This is the main entry point for agents. Every MCP message
    from the agent comes through here.
    """
    session_id = request.headers.get("mcp-session-id")
    agent_id: str | None = None

    if session_id:
        agent_id, error = await _get_session_agent_id(session_id)
        if error:
            return JSONResponse(
                status_code=401,
                content={"error": error},
            )
    else:
        agent_id, error = await _authenticate(request)
        if error:
            return JSONResponse(
                status_code=401,
                content={"error": error},
            )
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
            resp = await _process_message(msg, agent_id, session_id)  # type: ignore[arg-type]
            if resp is not None:
                responses.append(resp)
        if not responses:
            return JSONResponse(status_code=202, content=None)
        result = responses if len(responses) > 1 else responses[0]
        return JSONResponse(
            content=result,
            headers={"Mcp-Session-Id": session_id},
        )

    response = await _process_message(body, agent_id, session_id)  # type: ignore[arg-type]
    if response is None:
        return JSONResponse(
            status_code=202,
            content=None,
            headers={"Mcp-Session-Id": session_id},
        )

    return JSONResponse(
        content=response,
        headers={"Mcp-Session-Id": session_id},
    )


@router.delete("/mcp")
async def mcp_delete(request: Request) -> JSONResponse:
    """Terminate an MCP session."""
    session_id = request.headers.get("mcp-session-id")
    if session_id:
        await session_manager.destroy(session_id)
    return JSONResponse(status_code=200, content={"terminated": True})


async def _process_message(
    msg: dict, agent_id: str, session_id: str
) -> dict | None:
    """Process a single JSON-RPC message and return response (or None for notifications)."""
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
        return await _handle_tools_call(msg_id, params, agent_id, session_id)
    elif method == "resources/list":
        return jsonrpc_response(msg_id, {"resources": []})
    elif method == "prompts/list":
        return jsonrpc_response(msg_id, {"prompts": []})
    else:
        return jsonrpc_error(msg_id, -32601, f"Method not found: {method}")
