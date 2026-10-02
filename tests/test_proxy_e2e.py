"""End-to-end test for the AgentWall MCP proxy.

Tests the complete flow:
1. Create an agent (get API key)
2. Register a downstream MCP server
3. Trigger tool discovery
4. Connect to AgentWall as the agent
5. Initialize MCP session
6. List tools
7. Call a tool
8. Verify response
9. Terminate session

Requires: AgentWall API, PostgreSQL, Redis, and demo MCP servers running.
Run with: python -m pytest tests/test_proxy_e2e.py -v
Or standalone: python tests/test_proxy_e2e.py
"""

import httpx
import asyncio
import sys
import json

API_BASE = "http://localhost:8000"


async def test_full_proxy_flow():
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        print("\n=== AgentWall Phase 1 — MCP Proxy E2E Test ===\n")

        # Step 1: Health check
        print("1. Health check...")
        r = await client.get("/health")
        assert r.status_code == 200, f"Health check failed: {r.text}"
        print(f"   OK: {r.json()}")

        # Step 2: Create an agent
        print("\n2. Creating agent 'test-agent'...")
        r = await client.post(
            "/api/v1/agents",
            json={"name": "test-agent", "description": "E2E test agent"},
        )
        assert r.status_code == 201, f"Agent creation failed: {r.text}"
        agent_data = r.json()
        api_key = agent_data["api_key"]
        agent_id = agent_data["id"]
        print(f"   OK: id={agent_id}, api_key_prefix={agent_data['api_key_prefix']}")

        # Step 3: Register demo GitHub MCP server
        print("\n3. Registering demo-github MCP server...")
        r = await client.post(
            "/api/v1/servers",
            json={
                "name": "github",
                "endpoint": "http://demo-github-mcp:8001",
                "transport_type": "sse",
            },
        )
        if r.status_code == 409:
            print("   Already registered, continuing...")
        else:
            assert r.status_code == 201, f"Server registration failed: {r.text}"
            print(f"   OK: {r.json()['name']}")

        # Step 4: Register demo database MCP server
        print("\n4. Registering demo-database MCP server...")
        r = await client.post(
            "/api/v1/servers",
            json={
                "name": "database",
                "endpoint": "http://demo-database-mcp:8002",
                "transport_type": "sse",
            },
        )
        if r.status_code == 409:
            print("   Already registered, continuing...")
        else:
            assert r.status_code == 201, f"Server registration failed: {r.text}"
            print(f"   OK: {r.json()['name']}")

        # Step 5: Trigger tool discovery
        print("\n5. Scanning for tools...")
        r = await client.post("/api/v1/discovery/scan")
        assert r.status_code == 200, f"Discovery failed: {r.text}"
        discovery = r.json()
        print(f"   OK: {discovery['message']}")
        if discovery.get("errors"):
            print(f"   Errors: {discovery['errors']}")

        # Step 5b: Create a permit-all policy so tool calls succeed
        r = await client.post("/api/v1/policies", json={
            "name": "test-permit-all",
            "description": "Allow all tool calls for test-agent",
            "cedar_policy": 'permit(principal, action == Action::"call", resource);',
            "priority": 1,
        })
        assert r.status_code == 201, f"Policy creation failed: {r.text}"
        test_policy_id = r.json()["id"]

        # Step 6: Verify tools are registered
        print("\n6. Listing discovered tools...")
        r = await client.get("/api/v1/tools")
        assert r.status_code == 200
        tools = r.json()
        print(f"   OK: {len(tools)} tools found")
        for t in tools:
            print(f"   - {t['name']}: {t.get('description', '')[:60]}")

        # Step 7: MCP Initialize (with API key auth)
        print("\n7. MCP Initialize (agent authenticates)...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "test-agent", "version": "1.0"},
                },
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert r.status_code == 200, f"Initialize failed: {r.text}"
        session_id = r.headers.get("mcp-session-id")
        init_result = r.json()
        print(f"   OK: session={session_id}")
        print(f"   Server: {init_result['result']['serverInfo']}")

        # Step 8: Send initialized notification
        print("\n8. Sending initialized notification...")
        r = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 202, f"Initialized notification failed: {r.status_code}"
        print("   OK: 202 Accepted")

        # Step 9: List tools via MCP
        print("\n9. MCP tools/list...")
        r = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200, f"tools/list failed: {r.text}"
        tools_result = r.json()
        mcp_tools = tools_result["result"]["tools"]
        print(f"   OK: {len(mcp_tools)} tools available")
        for t in mcp_tools:
            print(f"   - {t['name']}")

        # Step 10: Call github.read_file
        print("\n10. MCP tools/call — github.read_file...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "github.read_file",
                    "arguments": {"repo": "acme/payments", "path": "src/main.py"},
                },
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200, f"tools/call failed: {r.text}"
        call_result = r.json()
        print(f"   OK: {json.dumps(call_result['result'], indent=2)[:200]}")

        # Step 11: Call database.read
        print("\n11. MCP tools/call — database.read...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "database.read",
                    "arguments": {"table": "users"},
                },
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200, f"tools/call failed: {r.text}"
        call_result = r.json()
        print(f"   OK: {json.dumps(call_result['result'], indent=2)[:200]}")

        # Step 12: Call unknown tool (should fail)
        print("\n12. MCP tools/call — unknown.tool (should error)...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "unknown.tool", "arguments": {}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        error_result = r.json()
        assert "error" in error_result, "Expected error for unknown tool"
        print(f"   OK: Got error — {error_result['error']['message']}")

        # Step 13: Terminate session
        print("\n13. Terminating MCP session...")
        r = await client.delete(
            "/mcp",
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        print("   OK: Session terminated")

        # Step 14: Verify session is invalid
        print("\n14. Verify terminated session is rejected...")
        r = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 6, "method": "tools/list", "params": {}},
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        print("   OK: 401 Unauthorized (session expired)")

        # Cleanup
        try:
            await client.delete(f"/api/v1/policies/{test_policy_id}")
            await client.delete(f"/api/v1/agents/{agent_id}")
        except Exception:
            pass

        print("\n=== ALL TESTS PASSED ===\n")
        print("Phase 1 verified:")
        print("  ✓ Agent authentication (API key → session)")
        print("  ✓ MCP session lifecycle (create → use → terminate)")
        print("  ✓ Tool discovery from downstream MCP servers")
        print("  ✓ Tool listing via MCP proxy")
        print("  ✓ Tool call forwarding (github, database)")
        print("  ✓ Unknown tool rejection")
        print("  ✓ Session termination and validation")


if __name__ == "__main__":
    try:
        asyncio.run(test_full_proxy_flow())
    except AssertionError as e:
        print(f"\n  FAILED: {e}")
        sys.exit(1)
    except httpx.ConnectError:
        print("\n  ERROR: Cannot connect to AgentWall API at localhost:8000")
        print("  Make sure services are running: make up")
        sys.exit(1)
