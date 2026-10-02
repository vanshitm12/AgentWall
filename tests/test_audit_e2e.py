"""End-to-end test for Phase 5: Audit System.

Tests that every tool call decision is recorded as an audit event:
- ALLOW → audit event with decision=ALLOW
- DENY → audit event with decision=DENY
- APPROVAL_REQUIRED → audit event with decision=APPROVAL_REQUIRED
- Approved retry → audit event with decision=ALLOW_APPROVED
- Audit log levels: METADATA strips args/response, ARGS_ONLY keeps args, FULL keeps both
- Per-tool audit_log_level override
- Audit filtering by agent, tool, decision
- Audit stats endpoint
- Pagination
"""

import httpx
import asyncio
import sys

API_BASE = "http://localhost:8000"


async def test_audit_system():
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        print("\n=== AgentWall Phase 5 — Audit System E2E Test ===\n")

        # ── Setup ──

        print("1. Setup: agent, servers, policies...")
        r = await client.post("/api/v1/agents", json={"name": "audit-agent", "description": "Audit test agent"})
        assert r.status_code == 201
        agent = r.json()
        api_key = agent["api_key"]
        agent_id = agent["id"]

        r = await client.post("/api/v1/servers", json={
            "name": "github", "endpoint": "http://demo-github-mcp:8001", "transport_type": "sse",
        })
        assert r.status_code in (201, 409)

        r = await client.post("/api/v1/servers", json={
            "name": "database", "endpoint": "http://demo-database-mcp:8002", "transport_type": "sse",
        })
        assert r.status_code in (201, 409)

        r = await client.post("/api/v1/discovery/scan")
        assert r.status_code == 200

        # Policies: allow read_file, deny delete_repo, approval for merge
        r = await client.post("/api/v1/policies", json={
            "name": "allow-read",
            "cedar_policy": 'permit(principal == User::"audit-agent", action == Action::"call", resource == Tool::"github.read_file");',
            "priority": 10,
        })
        assert r.status_code == 201

        r = await client.post("/api/v1/policies", json={
            "name": "deny-delete",
            "cedar_policy": 'forbid(principal, action == Action::"call", resource == Tool::"github.delete_repo");',
            "priority": 100,
        })
        assert r.status_code == 201

        r = await client.post("/api/v1/policies", json={
            "name": "approval-merge",
            "cedar_policy": 'permit(principal == User::"audit-agent", action == Action::"call", resource == Tool::"github.merge_pull_request");',
            "priority": 20,
            "metadata": {"decision": "approval"},
        })
        assert r.status_code == 201

        # MCP session
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "audit-agent", "version": "1.0"},
                },
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert r.status_code == 200
        session_id = r.headers.get("mcp-session-id")
        print(f"   OK: agent={agent_id[:8]}..., session={session_id[:20]}...")

        # ── Test 2: ALLOW generates audit event ──

        print("\n2. ALLOW: read_file → verify audit event...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 10, "method": "tools/call",
                "params": {"name": "github.read_file", "arguments": {"repo": "acme/app", "path": "README.md"}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        assert "result" in r.json()

        r = await client.get(f"/api/v1/audit?agent_id={agent_id}&tool_name=github.read_file")
        assert r.status_code == 200
        audit = r.json()
        assert audit["total"] >= 1
        event = audit["events"][0]
        assert event["decision"] == "ALLOW"
        assert event["tool_name"] == "github.read_file"
        assert event["agent_id"] == agent_id
        assert event["latency_ms"] is not None
        assert event["arguments"] is not None, "ARGS_ONLY default should include arguments"
        assert event["response"] is None, "ARGS_ONLY default should NOT include response"
        allow_event_id = event["id"]
        print(f"   OK: audit event {allow_event_id[:12]}... decision=ALLOW, args present, response=None")

        # ── Test 3: DENY generates audit event ──

        print("\n3. DENY: delete_repo → verify audit event...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 11, "method": "tools/call",
                "params": {"name": "github.delete_repo", "arguments": {"repo": "acme/app"}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        assert "error" in r.json()

        r = await client.get(f"/api/v1/audit?agent_id={agent_id}&decision=DENY")
        assert r.status_code == 200
        deny_events = r.json()
        assert deny_events["total"] >= 1
        deny_event = deny_events["events"][0]
        assert deny_event["decision"] == "DENY"
        assert deny_event["tool_name"] == "github.delete_repo"
        assert deny_event["error"] is not None
        print(f"   OK: audit event decision=DENY, error recorded")

        # ── Test 4: APPROVAL_REQUIRED generates audit event ──

        print("\n4. APPROVAL_REQUIRED: merge_pull_request → verify audit event...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 12, "method": "tools/call",
                "params": {"name": "github.merge_pull_request", "arguments": {"repo": "acme/app", "pull_number": 10}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        assert r.json()["error"]["code"] == -32001
        approval_id = r.json()["error"]["data"]["approval_id"]

        r = await client.get(f"/api/v1/audit?agent_id={agent_id}&decision=APPROVAL_REQUIRED")
        assert r.status_code == 200
        approval_events = r.json()
        assert approval_events["total"] >= 1
        ae = approval_events["events"][0]
        assert ae["decision"] == "APPROVAL_REQUIRED"
        assert ae["approval_id"] == approval_id
        print(f"   OK: audit event decision=APPROVAL_REQUIRED, approval_id linked")

        # ── Test 5: ALLOW_APPROVED generates audit event ──

        print("\n5. ALLOW_APPROVED: approve then retry → verify audit event...")
        r = await client.post(f"/api/v1/approvals/{approval_id}/decide", json={
            "status": "APPROVED", "reviewer": "admin",
        })
        assert r.status_code == 200

        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 13, "method": "tools/call",
                "params": {"name": "github.merge_pull_request", "arguments": {"repo": "acme/app", "pull_number": 10}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        assert "result" in r.json()

        r = await client.get(f"/api/v1/audit?agent_id={agent_id}&decision=ALLOW_APPROVED")
        assert r.status_code == 200
        approved_events = r.json()
        assert approved_events["total"] >= 1
        aae = approved_events["events"][0]
        assert aae["decision"] == "ALLOW_APPROVED"
        assert aae["approval_id"] == approval_id
        print(f"   OK: audit event decision=ALLOW_APPROVED, approval_id={approval_id[:12]}...")

        # ── Test 6: Get audit event by ID ──

        print("\n6. Get audit event by ID...")
        r = await client.get(f"/api/v1/audit/{allow_event_id}")
        assert r.status_code == 200
        assert r.json()["id"] == allow_event_id
        print(f"   OK: event found")

        # ── Test 7: Per-tool audit level override (FULL) ──

        print("\n7. Per-tool audit level: set read_file to FULL, verify response is logged...")
        r = await client.get("/api/v1/tools?search=github.read_file")
        read_tool_id = r.json()[0]["id"]
        r = await client.patch(f"/api/v1/tools/{read_tool_id}", json={"audit_log_level": "FULL"})
        assert r.status_code == 200

        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 14, "method": "tools/call",
                "params": {"name": "github.read_file", "arguments": {"repo": "acme/app", "path": "src/main.py"}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        assert "result" in r.json()

        r = await client.get(f"/api/v1/audit?agent_id={agent_id}&tool_name=github.read_file&page_size=1")
        assert r.status_code == 200
        full_event = r.json()["events"][0]
        assert full_event["arguments"] is not None, "FULL should include arguments"
        assert full_event["response"] is not None, "FULL should include response"
        print(f"   OK: FULL level — arguments AND response logged")

        # Reset to default
        await client.patch(f"/api/v1/tools/{read_tool_id}", json={"audit_log_level": None})

        # ── Test 8: Per-tool audit level override (METADATA) ──

        print("\n8. Per-tool audit level: set read_file to METADATA, verify args stripped...")
        r = await client.patch(f"/api/v1/tools/{read_tool_id}", json={"audit_log_level": "METADATA"})
        assert r.status_code == 200

        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 15, "method": "tools/call",
                "params": {"name": "github.read_file", "arguments": {"repo": "acme/app", "path": "secret.key"}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200

        r = await client.get(f"/api/v1/audit?agent_id={agent_id}&tool_name=github.read_file&page_size=1")
        assert r.status_code == 200
        meta_event = r.json()["events"][0]
        assert meta_event["arguments"] is None, "METADATA should NOT include arguments"
        assert meta_event["response"] is None, "METADATA should NOT include response"
        print(f"   OK: METADATA level — arguments AND response stripped")

        # Reset
        await client.patch(f"/api/v1/tools/{read_tool_id}", json={"audit_log_level": None})

        # ── Test 9: Audit stats ──

        print("\n9. Audit stats...")
        r = await client.get("/api/v1/audit/stats")
        assert r.status_code == 200
        stats = r.json()
        assert stats["total_events"] >= 5
        assert stats["by_decision"]["ALLOW"] >= 3
        assert stats["by_decision"]["DENY"] >= 1
        assert stats["by_decision"]["APPROVAL_REQUIRED"] >= 1
        assert stats["by_decision"]["ALLOW_APPROVED"] >= 1
        assert len(stats["top_tools"]) >= 1
        assert stats["avg_latency_ms"] is not None
        print(f"   OK: total={stats['total_events']}, allow={stats['by_decision']['ALLOW']}, "
              f"deny={stats['by_decision']['DENY']}, approval={stats['by_decision']['APPROVAL_REQUIRED']}, "
              f"avg_latency={stats['avg_latency_ms']}ms")

        # ── Test 10: Audit stats filtered by agent ──

        print("\n10. Audit stats filtered by agent...")
        r = await client.get(f"/api/v1/audit/stats?agent_id={agent_id}")
        assert r.status_code == 200
        agent_stats = r.json()
        assert agent_stats["total_events"] == stats["total_events"]
        print(f"   OK: agent-specific stats match (all events are from this agent)")

        # ── Test 11: Pagination ──

        print("\n11. Pagination...")
        r = await client.get(f"/api/v1/audit?page=1&page_size=2")
        assert r.status_code == 200
        page1 = r.json()
        assert len(page1["events"]) == 2
        assert page1["total"] >= 5
        assert page1["page"] == 1

        r = await client.get(f"/api/v1/audit?page=2&page_size=2")
        assert r.status_code == 200
        page2 = r.json()
        assert len(page2["events"]) == 2
        assert page2["page"] == 2
        assert page1["events"][0]["id"] != page2["events"][0]["id"]
        print(f"   OK: page1 has 2 events, page2 has 2 different events, total={page1['total']}")

        # ── Cleanup ──
        try:
            await client.delete(f"/api/v1/agents/{agent_id}")
            r = await client.get("/api/v1/policies")
            for p in r.json():
                await client.delete(f"/api/v1/policies/{p['id']}")
        except Exception:
            pass

        print("\n=== ALL PHASE 5 TESTS PASSED ===\n")
        print("Phase 5 verified:")
        print("  ✓ ALLOW → audit event with decision=ALLOW, arguments logged")
        print("  ✓ DENY → audit event with decision=DENY, error recorded")
        print("  ✓ APPROVAL_REQUIRED → audit event with approval_id linked")
        print("  ✓ ALLOW_APPROVED → audit event on approved retry")
        print("  ✓ Default ARGS_ONLY: arguments logged, response stripped")
        print("  ✓ Per-tool FULL: arguments AND response logged")
        print("  ✓ Per-tool METADATA: arguments AND response stripped")
        print("  ✓ GET audit event by ID")
        print("  ✓ Audit stats (total, by_decision, top_tools, avg_latency)")
        print("  ✓ Stats filtered by agent_id")
        print("  ✓ Pagination (page, page_size)")


if __name__ == "__main__":
    try:
        asyncio.run(test_audit_system())
    except AssertionError as e:
        print(f"\n  FAILED: {e}")
        sys.exit(1)
    except httpx.ConnectError:
        print("\n  ERROR: Cannot connect to AgentWall API at localhost:8000")
        sys.exit(1)
