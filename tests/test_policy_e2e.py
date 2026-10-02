"""End-to-end test for Phase 3: Policy Engine.

Tests Cedar policy evaluation on tool calls:
- Default-deny when no policies exist
- ALLOW for permitted tools
- DENY for forbidden tools
- APPROVAL_REQUIRED for approval-tagged policies
- Disabled tool rejection (before policy evaluation)
- Policy CRUD with validation
- Policy cache invalidation

This is the core MVP demo:
  coding-agent → github.read_file     → ALLOW
  coding-agent → github.create_pr     → ALLOW
  coding-agent → github.merge_pr      → APPROVAL_REQUIRED
  coding-agent → github.delete_repo   → DENY
"""

import httpx
import asyncio
import sys

API_BASE = "http://localhost:8000"


async def test_policy_engine():
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        print("\n=== AgentWall Phase 3 — Policy Engine E2E Test ===\n")

        # ── Setup ──

        print("1. Setup: create agent and register servers...")
        r = await client.post("/api/v1/agents", json={"name": "coding-agent", "description": "Coding agent"})
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
        print(f"   OK: agent={agent_id[:8]}..., tools discovered")

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
        print(f"   OK: session={session_id[:20]}...")

        # ── Test 2: Default-deny (no policies) ──

        print("\n2. Default-deny: tool call with NO policies...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 10, "method": "tools/call",
                "params": {"name": "github.read_file", "arguments": {"repo": "acme/app", "path": "README.md"}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "error" in result, "Expected denial with no policies"
        assert "denied" in result["error"]["message"].lower() or "no policies" in result["error"]["message"].lower()
        print(f"   OK: DENIED — {result['error']['message']}")

        # ── Test 3: Create policies ──

        print("\n3. Create Cedar policies...")

        # Policy 1: Allow coding-agent to read files and list files
        r = await client.post("/api/v1/policies", json={
            "name": "allow-read-ops",
            "description": "Allow coding-agent read operations",
            "cedar_policy": """permit(
    principal == User::"coding-agent",
    action == Action::"call",
    resource == Tool::"github.read_file"
);

permit(
    principal == User::"coding-agent",
    action == Action::"call",
    resource == Tool::"github.list_files"
);

permit(
    principal == User::"coding-agent",
    action == Action::"call",
    resource == Tool::"github.create_issue"
);""",
            "priority": 10,
        })
        assert r.status_code == 201, f"Policy creation failed: {r.text}"
        print(f"   OK: allow-read-ops (priority=10)")

        # Policy 2: Allow create_pull_request
        r = await client.post("/api/v1/policies", json={
            "name": "allow-create-pr",
            "description": "Allow coding-agent to create PRs",
            "cedar_policy": """permit(
    principal == User::"coding-agent",
    action == Action::"call",
    resource == Tool::"github.create_pull_request"
);""",
            "priority": 10,
        })
        assert r.status_code == 201
        print(f"   OK: allow-create-pr (priority=10)")

        # Policy 3: Approval required for merge_pull_request
        # The Cedar text is a normal permit — the metadata {"decision": "approval"}
        # is what tells the engine to return APPROVAL_REQUIRED instead of ALLOW.
        r = await client.post("/api/v1/policies", json={
            "name": "approval-merge-pr",
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
        print(f"   OK: approval-merge-pr (priority=20, decision=approval)")

        # Policy 4: Forbid delete_repo for everyone
        r = await client.post("/api/v1/policies", json={
            "name": "deny-delete-repo",
            "description": "Never allow repo deletion",
            "cedar_policy": """forbid(
    principal,
    action == Action::"call",
    resource == Tool::"github.delete_repo"
);""",
            "priority": 100,
        })
        assert r.status_code == 201
        print(f"   OK: deny-delete-repo (priority=100)")

        # Policy 5: Allow LOW-risk database reads via context
        r = await client.post("/api/v1/policies", json={
            "name": "allow-low-risk",
            "description": "Allow any agent to call LOW risk tools",
            "cedar_policy": """permit(
    principal,
    action == Action::"call",
    resource
) when {
    context.risk_classification == "LOW"
};""",
            "priority": 5,
        })
        assert r.status_code == 201
        print(f"   OK: allow-low-risk (priority=5)")

        # ── Test 4: ALLOW — read_file ──

        print("\n4. ALLOW: coding-agent → github.read_file...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 20, "method": "tools/call",
                "params": {"name": "github.read_file", "arguments": {"repo": "acme/app", "path": "src/main.py"}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "result" in result, f"Expected allow, got: {result}"
        assert result["result"]["isError"] is False
        print(f"   OK: ALLOWED — got file contents")

        # ── Test 5: ALLOW — create_pull_request ──

        print("\n5. ALLOW: coding-agent → github.create_pull_request...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 21, "method": "tools/call",
                "params": {
                    "name": "github.create_pull_request",
                    "arguments": {"repo": "acme/app", "title": "Fix bug", "body": "Fixes #42", "head": "fix-branch"},
                },
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "result" in result, f"Expected allow, got: {result}"
        print(f"   OK: ALLOWED — PR created")

        # ── Test 6: APPROVAL_REQUIRED — merge_pull_request ──

        print("\n6. APPROVAL_REQUIRED: coding-agent → github.merge_pull_request...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 22, "method": "tools/call",
                "params": {
                    "name": "github.merge_pull_request",
                    "arguments": {"repo": "acme/app", "pull_number": 182},
                },
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "error" in result, f"Expected approval-required, got: {result}"
        assert result["error"]["code"] == -32001
        assert "approval" in result["error"]["message"].lower()
        print(f"   OK: APPROVAL_REQUIRED — {result['error']['message']}")

        # ── Test 7: DENY — delete_repo ──

        print("\n7. DENY: coding-agent → github.delete_repo...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 23, "method": "tools/call",
                "params": {"name": "github.delete_repo", "arguments": {"repo": "acme/app", "confirm": True}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "error" in result, f"Expected deny, got: {result}"
        assert "denied" in result["error"]["message"].lower()
        print(f"   OK: DENIED — {result['error']['message']}")

        # ── Test 8: DENY — no policy for database tools ──

        print("\n8. DENY: coding-agent → database.query (no matching policy)...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 24, "method": "tools/call",
                "params": {"name": "database.query", "arguments": {"sql": "SELECT 1"}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "error" in result, f"Expected deny (no policy), got: {result}"
        assert "denied" in result["error"]["message"].lower()
        print(f"   OK: DENIED (default-deny) — {result['error']['message']}")

        # ── Test 9: Context-based policy — LOW risk tools ──

        print("\n9. Context-based: set database.read to LOW risk, then call...")
        # Find the tool and set it to LOW risk
        r = await client.get("/api/v1/tools?search=database.read")
        assert r.status_code == 200
        tools = r.json()
        assert len(tools) >= 1
        tool_id = tools[0]["id"]

        r = await client.patch(f"/api/v1/tools/{tool_id}", json={"risk_classification": "LOW"})
        assert r.status_code == 200
        assert r.json()["risk_classification"] == "LOW"

        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 25, "method": "tools/call",
                "params": {"name": "database.read", "arguments": {"table": "users"}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "result" in result, f"Expected allow (LOW risk), got: {result}"
        print(f"   OK: ALLOWED — LOW risk tool permitted by context policy")

        # ── Test 10: Policy validation ──

        print("\n10. Policy validation (invalid syntax)...")
        r = await client.post("/api/v1/policies/validate", json={
            "name": "bad-policy",
            "cedar_policy": "this is not valid cedar syntax {{{",
        })
        assert r.status_code == 422
        print(f"   OK: rejected — {r.json()['detail'][:60]}...")

        r = await client.post("/api/v1/policies/validate", json={
            "name": "good-policy",
            "cedar_policy": 'permit(principal, action == Action::"call", resource);',
        })
        assert r.status_code == 200
        assert r.json()["valid"] is True
        print(f"   OK: valid policy accepted")

        # ── Test 11: Disabled tool rejected before policy ──

        print("\n11. Disabled tool rejected before policy evaluation...")
        # Find github.create_issue and disable it
        r = await client.get("/api/v1/tools?search=github.create_issue")
        tools = r.json()
        issue_tool_id = tools[0]["id"]
        r = await client.patch(f"/api/v1/tools/{issue_tool_id}", json={"enabled": False})
        assert r.status_code == 200

        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 26, "method": "tools/call",
                "params": {"name": "github.create_issue", "arguments": {"repo": "acme/app", "title": "Test", "body": "test"}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "error" in result
        assert "disabled" in result["error"]["message"].lower()
        print(f"   OK: REJECTED — {result['error']['message']}")

        # Re-enable it
        await client.patch(f"/api/v1/tools/{issue_tool_id}", json={"enabled": True})

        # ── Test 12: Policy update + cache invalidation ──

        print("\n12. Delete allow-read-ops → read_file should now be DENIED...")
        r = await client.get("/api/v1/policies")
        policies = r.json()
        read_policy = next(p for p in policies if p["name"] == "allow-read-ops")

        r = await client.delete(f"/api/v1/policies/{read_policy['id']}")
        assert r.status_code == 204

        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 30, "method": "tools/call",
                "params": {"name": "github.read_file", "arguments": {"repo": "acme/app", "path": "README.md"}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        result = r.json()
        assert "error" in result, f"Expected deny after policy deleted, got: {result}"
        assert "denied" in result["error"]["message"].lower()
        print(f"   OK: DENIED after policy removal (cache invalidated)")

        # ── Cleanup ──
        try:
            await client.delete(f"/api/v1/agents/{agent_id}")
            for p in policies:
                await client.delete(f"/api/v1/policies/{p['id']}")
        except Exception:
            pass

        print("\n=== ALL PHASE 3 TESTS PASSED ===\n")
        print("Phase 3 verified:")
        print("  ✓ Default-deny when no policies exist")
        print("  ✓ ALLOW for permitted tools (coding-agent → read_file, create_pr)")
        print("  ✓ DENY for forbidden tools (delete_repo)")
        print("  ✓ DENY for unmatched tools (default-deny)")
        print("  ✓ APPROVAL_REQUIRED for approval-tagged policies (merge_pr)")
        print("  ✓ Context-based policies (LOW risk → allow)")
        print("  ✓ Disabled tool rejection (before policy eval)")
        print("  ✓ Cedar syntax validation on create")
        print("  ✓ Policy cache invalidation on delete")
        print()
        print("MVP demo flow proven:")
        print("  coding-agent → github.read_file         → ALLOW")
        print("  coding-agent → github.create_pull_request → ALLOW")
        print("  coding-agent → github.merge_pull_request  → APPROVAL_REQUIRED")
        print("  coding-agent → github.delete_repo         → DENY")


if __name__ == "__main__":
    try:
        asyncio.run(test_policy_engine())
    except AssertionError as e:
        print(f"\n  FAILED: {e}")
        sys.exit(1)
    except httpx.ConnectError:
        print("\n  ERROR: Cannot connect to AgentWall API at localhost:8000")
        sys.exit(1)
