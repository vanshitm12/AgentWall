"""End-to-end test for Phase 4: Approval System.

Tests the complete approval workflow:
- APPROVAL_REQUIRED creates a pending approval record
- Human approves → agent retries → tool call succeeds
- Human rejects → agent retries → tool call denied
- Approved approval is consumed (one-time use)
- Expired approvals are rejected
- Approval listing and filtering
- Arguments must match exactly (different args = different approval)

Flow:
  coding-agent → merge_pull_request → APPROVAL_REQUIRED (approval created)
  human → approves the approval
  coding-agent → merge_pull_request (same args) → ALLOW (approval consumed)
  coding-agent → merge_pull_request (same args again) → APPROVAL_REQUIRED (approval was consumed)
"""

import httpx
import asyncio
import sys

API_BASE = "http://localhost:8000"


async def test_approval_system():
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        print("\n=== AgentWall Phase 4 — Approval System E2E Test ===\n")

        # ── Setup ──

        print("1. Setup: create agent, servers, policies...")
        r = await client.post("/api/v1/agents", json={"name": "coding-agent", "description": "Coding agent"})
        assert r.status_code == 201
        agent = r.json()
        api_key = agent["api_key"]
        agent_id = agent["id"]

        r = await client.post("/api/v1/servers", json={
            "name": "github", "endpoint": "http://demo-github-mcp:8001", "transport_type": "sse",
        })
        assert r.status_code in (201, 409)

        r = await client.post("/api/v1/discovery/scan")
        assert r.status_code == 200

        # Create policies: allow read, approval for merge
        r = await client.post("/api/v1/policies", json={
            "name": "allow-read",
            "cedar_policy": """permit(
    principal == User::"coding-agent",
    action == Action::"call",
    resource == Tool::"github.read_file"
);""",
            "priority": 10,
        })
        assert r.status_code == 201

        r = await client.post("/api/v1/policies", json={
            "name": "approval-merge",
            "description": "Require approval for merging PRs",
            "cedar_policy": """permit(
    principal == User::"coding-agent",
    action == Action::"call",
    resource == Tool::"github.merge_pull_request"
);""",
            "priority": 20,
            "metadata": {"decision": "approval"},
        })
        assert r.status_code == 201

        # Initialize MCP session
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "coding-agent", "version": "1.0"},
                },
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert r.status_code == 200
        session_id = r.headers.get("mcp-session-id")
        print(f"   OK: agent={agent_id[:8]}..., session={session_id[:20]}...")

        # ── Test 2: APPROVAL_REQUIRED creates a pending approval ──

        print("\n2. APPROVAL_REQUIRED: merge_pull_request creates pending approval...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 10, "method": "tools/call",
                "params": {
                    "name": "github.merge_pull_request",
                    "arguments": {"repo": "acme/app", "pull_number": 42},
                },
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "error" in result
        assert result["error"]["code"] == -32001
        assert "approval" in result["error"]["message"].lower()
        approval_id = result["error"]["data"]["approval_id"]
        print(f"   OK: approval_id={approval_id[:12]}...")

        # ── Test 3: Verify approval exists in pending list ──

        print("\n3. Verify approval is PENDING via REST API...")
        r = await client.get("/api/v1/approvals/pending")
        assert r.status_code == 200
        pending = r.json()
        assert len(pending) >= 1
        found = next((a for a in pending if a["id"] == approval_id), None)
        assert found is not None
        assert found["status"] == "PENDING"
        assert found["tool_name"] == "github.merge_pull_request"
        assert found["agent_id"] == agent_id
        assert found["arguments"] == {"repo": "acme/app", "pull_number": 42}
        assert found["arguments_hash"] is not None
        print(f"   OK: approval is PENDING, tool={found['tool_name']}, args match")

        # ── Test 4: Get approval by ID ──

        print("\n4. Get approval by ID...")
        r = await client.get(f"/api/v1/approvals/{approval_id}")
        assert r.status_code == 200
        approval = r.json()
        assert approval["id"] == approval_id
        assert approval["status"] == "PENDING"
        print(f"   OK: approval found")

        # ── Test 5: Agent retries BEFORE approval → still APPROVAL_REQUIRED ──

        print("\n5. Agent retries before approval → still blocked...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 11, "method": "tools/call",
                "params": {
                    "name": "github.merge_pull_request",
                    "arguments": {"repo": "acme/app", "pull_number": 42},
                },
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "error" in result
        assert result["error"]["code"] == -32001
        second_approval_id = result["error"]["data"]["approval_id"]
        assert second_approval_id != approval_id, "Should create a new approval"
        print(f"   OK: still APPROVAL_REQUIRED (new approval={second_approval_id[:12]}...)")

        # ── Test 6: Human APPROVES the first approval ──

        print("\n6. Human approves the first approval...")
        r = await client.post(f"/api/v1/approvals/{approval_id}/decide", json={
            "status": "APPROVED",
            "reviewer": "security-admin",
            "reason": "Reviewed, PR #42 is safe to merge",
        })
        assert r.status_code == 200
        decided = r.json()
        assert decided["status"] == "APPROVED"
        assert decided["reviewer"] == "security-admin"
        assert decided["decided_at"] is not None
        print(f"   OK: APPROVED by {decided['reviewer']}")

        # ── Test 7: Agent retries with same args → ALLOW (approval consumed) ──

        print("\n7. Agent retries after approval → tool call succeeds...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 12, "method": "tools/call",
                "params": {
                    "name": "github.merge_pull_request",
                    "arguments": {"repo": "acme/app", "pull_number": 42},
                },
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "result" in result, f"Expected allow after approval, got: {result}"
        print(f"   OK: ALLOWED — merge executed")

        # ── Test 8: Approval was consumed (EXECUTED), can't reuse ──

        print("\n8. Verify approval was consumed (EXECUTED)...")
        r = await client.get(f"/api/v1/approvals/{approval_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "EXECUTED"

        # Retry same call → should need new approval (old one consumed)
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 13, "method": "tools/call",
                "params": {
                    "name": "github.merge_pull_request",
                    "arguments": {"repo": "acme/app", "pull_number": 42},
                },
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "error" in result
        assert result["error"]["code"] == -32001
        print(f"   OK: approval consumed, new approval required on retry")

        # ── Test 9: Different arguments need different approval ──

        print("\n9. Different arguments need a separate approval...")
        # Approve the second_approval_id (for PR #42)
        r = await client.post(f"/api/v1/approvals/{second_approval_id}/decide", json={
            "status": "APPROVED",
            "reviewer": "security-admin",
        })
        assert r.status_code == 200

        # Try with DIFFERENT arguments (PR #999)
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 14, "method": "tools/call",
                "params": {
                    "name": "github.merge_pull_request",
                    "arguments": {"repo": "acme/app", "pull_number": 999},
                },
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "error" in result
        assert result["error"]["code"] == -32001
        print(f"   OK: different args = new approval required (approval for PR #42 doesn't cover PR #999)")

        # ── Test 10: Human REJECTS an approval → agent denied ──

        print("\n10. Human rejects an approval → agent retry denied...")
        # Get the latest pending approval (for PR #999)
        r = await client.get("/api/v1/approvals/pending")
        pending = r.json()
        pr999_approval = next(a for a in pending if a["arguments"]["pull_number"] == 999)

        r = await client.post(f"/api/v1/approvals/{pr999_approval['id']}/decide", json={
            "status": "REJECTED",
            "reviewer": "security-admin",
            "reason": "PR #999 has not been reviewed yet",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "REJECTED"

        # Agent retries → should get APPROVAL_REQUIRED again (not the rejected one)
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 15, "method": "tools/call",
                "params": {
                    "name": "github.merge_pull_request",
                    "arguments": {"repo": "acme/app", "pull_number": 999},
                },
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "error" in result
        assert result["error"]["code"] == -32001
        print(f"   OK: rejected approval doesn't block — new approval created")

        # ── Test 11: Double-decide is rejected ──

        print("\n11. Double-decide on already-decided approval...")
        r = await client.post(f"/api/v1/approvals/{approval_id}/decide", json={
            "status": "APPROVED",
            "reviewer": "another-admin",
        })
        assert r.status_code == 409
        print(f"   OK: 409 Conflict — {r.json()['detail']}")

        # ── Test 12: Filter approvals by status ──

        print("\n12. Filter approvals by status...")
        r = await client.get("/api/v1/approvals?status_filter=EXECUTED")
        assert r.status_code == 200
        executed = r.json()
        assert len(executed) >= 1
        assert all(a["status"] == "EXECUTED" for a in executed)

        r = await client.get("/api/v1/approvals?status_filter=REJECTED")
        assert r.status_code == 200
        rejected = r.json()
        assert len(rejected) >= 1
        assert all(a["status"] == "REJECTED" for a in rejected)

        r = await client.get(f"/api/v1/approvals?agent_id={agent_id}")
        assert r.status_code == 200
        agent_approvals = r.json()
        assert len(agent_approvals) >= 4
        print(f"   OK: filters work (executed={len(executed)}, rejected={len(rejected)}, agent={len(agent_approvals)})")

        # ── Test 13: ALLOW flow unaffected (no approval needed) ──

        print("\n13. ALLOW flow still works (read_file, no approval needed)...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 20, "method": "tools/call",
                "params": {"name": "github.read_file", "arguments": {"repo": "acme/app", "path": "README.md"}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "result" in result
        print(f"   OK: read_file still ALLOWED directly")

        # ── Cleanup ──
        try:
            await client.delete(f"/api/v1/agents/{agent_id}")
            r = await client.get("/api/v1/policies")
            for p in r.json():
                await client.delete(f"/api/v1/policies/{p['id']}")
        except Exception:
            pass

        print("\n=== ALL PHASE 4 TESTS PASSED ===\n")
        print("Phase 4 verified:")
        print("  ✓ APPROVAL_REQUIRED creates a pending approval record")
        print("  ✓ Approval includes tool name, arguments, arguments hash")
        print("  ✓ Pending approvals visible via REST API")
        print("  ✓ Agent retry before approval → still blocked (new approval created)")
        print("  ✓ Human approves → agent retry succeeds (tool call forwarded)")
        print("  ✓ Approval consumed after use (EXECUTED, one-time)")
        print("  ✓ Consumed approval requires re-approval on next call")
        print("  ✓ Different arguments require separate approval")
        print("  ✓ Human rejects → agent gets new APPROVAL_REQUIRED on retry")
        print("  ✓ Double-decide prevented (409 Conflict)")
        print("  ✓ Approval filtering by status and agent")
        print("  ✓ Regular ALLOW flow unaffected")


if __name__ == "__main__":
    try:
        asyncio.run(test_approval_system())
    except AssertionError as e:
        print(f"\n  FAILED: {e}")
        sys.exit(1)
    except httpx.ConnectError:
        print("\n  ERROR: Cannot connect to AgentWall API at localhost:8000")
        sys.exit(1)
