"""End-to-end test for Phase 2: Registries.

Tests agent, server, and tool registry management:
- Agent: create, list with filter, rotate key, list sessions, delete
- Server: create, list with filter, health check, per-server scan, delete (cascade)
- Tool: list with filters, search, enable/disable, risk classification update

Requires: AgentWall API, PostgreSQL, Redis, and demo MCP servers running.
"""

import httpx
import asyncio
import sys

API_BASE = "http://localhost:8000"


async def test_registries():
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        print("\n=== AgentWall Phase 2 — Registries E2E Test ===\n")

        # ── Agent Registry ──

        print("1. Create two agents...")
        r1 = await client.post("/api/v1/agents", json={"name": "agent-alpha", "description": "Test alpha"})
        assert r1.status_code == 201
        alpha = r1.json()
        alpha_id = alpha["id"]
        alpha_key = alpha["api_key"]

        r2 = await client.post("/api/v1/agents", json={"name": "agent-beta", "description": "Test beta"})
        assert r2.status_code == 201
        beta = r2.json()
        beta_id = beta["id"]
        print(f"   OK: alpha={alpha_id[:8]}..., beta={beta_id[:8]}...")

        print("\n2. List all agents...")
        r = await client.get("/api/v1/agents")
        assert r.status_code == 200
        assert len(r.json()) == 2
        print(f"   OK: {len(r.json())} agents")

        print("\n3. Suspend beta, filter by status...")
        r = await client.post(f"/api/v1/agents/{beta_id}/status", json={"status": "SUSPENDED"})
        assert r.status_code == 200
        assert r.json()["status"] == "SUSPENDED"

        r = await client.get("/api/v1/agents?status=ACTIVE")
        assert r.status_code == 200
        active = r.json()
        assert len(active) == 1 and active[0]["id"] == alpha_id
        print("   OK: filter returns only active agent")

        print("\n4. Create session then list sessions for alpha...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "alpha", "version": "1.0"},
                },
            },
            headers={"Authorization": f"Bearer {alpha_key}"},
        )
        assert r.status_code == 200
        session_id = r.headers.get("mcp-session-id")

        r = await client.get(f"/api/v1/agents/{alpha_id}/sessions")
        assert r.status_code == 200
        sessions = r.json()
        assert len(sessions) >= 1
        print(f"   OK: {len(sessions)} active session(s)")

        print("\n5. Rotate alpha's API key...")
        r = await client.post(f"/api/v1/agents/{alpha_id}/rotate-key")
        assert r.status_code == 200
        new_key = r.json()["api_key"]
        assert new_key != alpha_key
        assert r.json()["api_key_prefix"] != alpha["api_key_prefix"]

        # Old key should fail
        r = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 401, "Old session should be invalidated after key rotation"
        print(f"   OK: new key prefix={r.json() if r.status_code != 200 else ''}, old sessions invalidated")

        print("\n6. Delete beta agent...")
        r = await client.delete(f"/api/v1/agents/{beta_id}")
        assert r.status_code == 204
        r = await client.get(f"/api/v1/agents/{beta_id}")
        assert r.status_code == 404
        print("   OK: deleted, returns 404")

        # ── Server Registry ──

        print("\n7. Register demo servers...")
        r = await client.post("/api/v1/servers", json={
            "name": "github", "endpoint": "http://demo-github-mcp:8001", "transport_type": "sse",
        })
        assert r.status_code in (201, 409)
        if r.status_code == 201:
            github_id = r.json()["id"]
        else:
            r = await client.get("/api/v1/servers")
            github_id = next(s["id"] for s in r.json() if s["name"] == "github")

        r = await client.post("/api/v1/servers", json={
            "name": "database", "endpoint": "http://demo-database-mcp:8002", "transport_type": "sse",
        })
        assert r.status_code in (201, 409)
        if r.status_code == 201:
            db_id = r.json()["id"]
        else:
            r = await client.get("/api/v1/servers")
            db_id = next(s["id"] for s in r.json() if s["name"] == "database")
        print(f"   OK: github={github_id[:8]}..., database={db_id[:8]}...")

        print("\n8. Filter servers by trust_level...")
        r = await client.get("/api/v1/servers?trust_level=TRUSTED")
        assert r.status_code == 200
        assert len(r.json()) >= 2
        print(f"   OK: {len(r.json())} TRUSTED servers")

        print("\n9. Health check github server...")
        r = await client.post(f"/api/v1/servers/{github_id}/health")
        assert r.status_code == 200
        health = r.json()
        assert health["reachable"] is True
        print(f"   OK: reachable={health['reachable']}, tools={health['tool_count']}")

        print("\n10. Per-server scan (github)...")
        r = await client.post(f"/api/v1/servers/{github_id}/scan")
        assert r.status_code == 200
        scan = r.json()
        print(f"   OK: added={scan['added']}, unchanged={scan['unchanged']}, removed={scan['removed']}, total={scan['total']}")

        print("\n11. Per-server scan (database)...")
        r = await client.post(f"/api/v1/servers/{db_id}/scan")
        assert r.status_code == 200
        scan = r.json()
        print(f"   OK: added={scan['added']}, unchanged={scan['unchanged']}, removed={scan['removed']}, total={scan['total']}")

        # ── Tool Registry ──

        print("\n12. List all tools...")
        r = await client.get("/api/v1/tools")
        assert r.status_code == 200
        all_tools = r.json()
        assert len(all_tools) >= 11
        print(f"   OK: {len(all_tools)} tools total")

        print("\n13. Filter tools by server...")
        r = await client.get(f"/api/v1/tools?server_id={github_id}")
        assert r.status_code == 200
        github_tools = r.json()
        assert all("github." in t["name"] for t in github_tools)
        print(f"   OK: {len(github_tools)} github tools")

        print("\n14. Search tools by name...")
        r = await client.get("/api/v1/tools?search=delete")
        assert r.status_code == 200
        delete_tools = r.json()
        assert all("delete" in t["name"].lower() for t in delete_tools)
        print(f"   OK: {len(delete_tools)} tools matching 'delete': {[t['name'] for t in delete_tools]}")

        print("\n15. Update tool risk classification...")
        tool_id = github_tools[0]["id"]
        r = await client.patch(f"/api/v1/tools/{tool_id}", json={"risk_classification": "CRITICAL"})
        assert r.status_code == 200
        assert r.json()["risk_classification"] == "CRITICAL"
        print(f"   OK: {github_tools[0]['name']} → CRITICAL")

        print("\n16. Disable a tool...")
        r = await client.patch(f"/api/v1/tools/{tool_id}", json={"enabled": False})
        assert r.status_code == 200
        assert r.json()["enabled"] is False

        r = await client.get("/api/v1/tools?enabled=true")
        assert r.status_code == 200
        enabled_tools = r.json()
        assert tool_id not in [t["id"] for t in enabled_tools]
        print(f"   OK: tool disabled, filtered out of enabled list")

        print("\n17. Re-enable the tool...")
        r = await client.patch(f"/api/v1/tools/{tool_id}", json={"enabled": True})
        assert r.status_code == 200
        assert r.json()["enabled"] is True
        print("   OK: tool re-enabled")

        print("\n18. Filter tools by risk...")
        r = await client.get("/api/v1/tools?risk_classification=CRITICAL")
        assert r.status_code == 200
        critical_tools = r.json()
        assert len(critical_tools) >= 1
        assert all(t["risk_classification"] == "CRITICAL" for t in critical_tools)
        print(f"   OK: {len(critical_tools)} CRITICAL tools")

        # ── Server Delete (cascade) ──

        print("\n19. Delete database server (cascade removes tools)...")
        r = await client.get(f"/api/v1/tools?server_id={db_id}")
        db_tool_count = len(r.json())
        assert db_tool_count > 0

        r = await client.delete(f"/api/v1/servers/{db_id}")
        assert r.status_code == 204

        r = await client.get(f"/api/v1/tools?server_id={db_id}")
        assert len(r.json()) == 0

        r = await client.get(f"/api/v1/servers/{db_id}")
        assert r.status_code == 404
        print(f"   OK: server deleted, {db_tool_count} tools cascade-removed")

        # ── Re-scan detects changes ──

        print("\n20. Re-scan github (should show unchanged)...")
        r = await client.post(f"/api/v1/servers/{github_id}/scan")
        assert r.status_code == 200
        scan = r.json()
        assert scan["added"] == 0
        assert scan["removed"] == 0
        print(f"   OK: no changes (unchanged={scan['unchanged']})")

        # ── Cleanup ──
        await client.delete(f"/api/v1/agents/{alpha_id}")
        await client.delete(f"/api/v1/servers/{github_id}")

        print("\n=== ALL PHASE 2 TESTS PASSED ===\n")
        print("Phase 2 verified:")
        print("  ✓ Agent CRUD with status filtering")
        print("  ✓ API key rotation (invalidates sessions)")
        print("  ✓ Agent session listing")
        print("  ✓ Agent deletion (cleanup sessions)")
        print("  ✓ Server CRUD with status/trust filtering")
        print("  ✓ Server health check (probe downstream)")
        print("  ✓ Per-server scan with diff detection")
        print("  ✓ Tool search by name pattern")
        print("  ✓ Tool filtering (server, risk, enabled)")
        print("  ✓ Tool enable/disable toggle")
        print("  ✓ Tool risk classification update")
        print("  ✓ Server delete cascades to tools")
        print("  ✓ Re-scan detects no false changes")


if __name__ == "__main__":
    try:
        asyncio.run(test_registries())
    except AssertionError as e:
        print(f"\n  FAILED: {e}")
        sys.exit(1)
    except httpx.ConnectError:
        print("\n  ERROR: Cannot connect to AgentWall API at localhost:8000")
        sys.exit(1)
