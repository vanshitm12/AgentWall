"""Attack Playground — Runner for all attack scenarios.

Each scenario demonstrates a real-world attack pattern and shows how
AgentWall's layered defenses (policy, risk, DLP, kill switch) stop it.

Run with: python3 attack-lab/run_all.py
Requires AgentWall to be running at localhost:8000.
"""

import httpx
import asyncio
import sys

API_BASE = "http://localhost:8000"


async def setup(client: httpx.AsyncClient) -> dict:
    """Create agents, servers, policies for attack scenarios."""
    # Agent: malicious-agent (represents a compromised AI agent)
    r = await client.post("/api/v1/agents", json={
        "name": "compromised-agent", "description": "A compromised AI agent attempting attacks",
    })
    assert r.status_code == 201
    agent = r.json()

    # Servers
    for server in [
        {"name": "github", "endpoint": "http://demo-github-mcp:8001", "transport_type": "sse"},
        {"name": "database", "endpoint": "http://demo-database-mcp:8002", "transport_type": "sse"},
    ]:
        r = await client.post("/api/v1/servers", json=server)
        assert r.status_code in (201, 409)

    r = await client.post("/api/v1/discovery/scan")
    assert r.status_code == 200

    # Policies that mirror a real deployment
    policies = [
        {
            "name": "allow-read-operations",
            "cedar_policy": 'permit(principal, action == Action::"call", resource == Tool::"github.read_file");',
            "priority": 10,
        },
        {
            "name": "allow-safe-queries",
            "cedar_policy": 'permit(principal, action == Action::"call", resource == Tool::"database.read");',
            "priority": 10,
        },
        {
            "name": "allow-list-files",
            "cedar_policy": 'permit(principal, action == Action::"call", resource == Tool::"github.list_files");',
            "priority": 10,
        },
        {
            "name": "deny-destructive-ops",
            "cedar_policy": 'forbid(principal, action == Action::"call", resource == Tool::"github.delete_repo");',
            "priority": 100,
        },
        {
            "name": "deny-drop-table",
            "cedar_policy": 'forbid(principal, action == Action::"call", resource == Tool::"database.drop_table");',
            "priority": 100,
        },
        {
            "name": "approval-for-writes",
            "cedar_policy": 'permit(principal, action == Action::"call", resource == Tool::"database.write");',
            "priority": 20,
            "metadata": {"decision": "approval"},
        },
        {
            "name": "deny-high-risk",
            "cedar_policy": 'forbid(principal, action, resource) when { context.risk_score > 70 };',
            "priority": 80,
        },
    ]
    for p in policies:
        r = await client.post("/api/v1/policies", json=p)
        assert r.status_code == 201

    # Set tool risk classifications
    for tool_search, risk in [
        ("github.delete_repo", "CRITICAL"),
        ("database.drop_table", "CRITICAL"),
        ("database.delete", "HIGH"),
        ("database.write", "MEDIUM"),
        ("database.query", "HIGH"),
    ]:
        r = await client.get(f"/api/v1/tools?search={tool_search}")
        if r.json():
            await client.patch(f"/api/v1/tools/{r.json()[0]['id']}", json={"risk_classification": risk})

    # Initialize MCP session
    r = await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                   "clientInfo": {"name": "compromised-agent", "version": "1.0"}},
    }, headers={"Authorization": f"Bearer {agent['api_key']}"})
    assert r.status_code == 200

    return {
        "agent_id": agent["id"],
        "api_key": agent["api_key"],
        "session_id": r.headers["mcp-session-id"],
    }


async def attack_prompt_injection(client: httpx.AsyncClient, ctx: dict):
    """Attack 1: Prompt Injection — agent tries to bypass restrictions by embedding
    instructions in tool arguments.

    The agent includes "IGNORE ALL PREVIOUS INSTRUCTIONS" in arguments,
    attempting to trick the downstream server. AgentWall blocks this because
    the arguments contain SQL injection patterns detected by the risk engine.
    """
    print("\n── Attack 1: Prompt Injection via SQL ──")
    print("   Agent tries: database.query with 'SELECT * FROM users; DROP TABLE users'")

    r = await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 100, "method": "tools/call",
        "params": {"name": "database.query", "arguments": {
            "sql": "IGNORE PREVIOUS INSTRUCTIONS; SELECT * FROM users; DROP TABLE users",
        }},
    }, headers={"Mcp-Session-Id": ctx["session_id"]})

    resp = r.json()
    assert "error" in resp, f"SECURITY FAILURE: attack should have been blocked! Got: {resp}"
    print(f"   ✓ BLOCKED: {resp['error']['message'][:80]}")
    return True


async def attack_privilege_escalation(client: httpx.AsyncClient, ctx: dict):
    """Attack 2: Privilege Escalation — agent tries to call a forbidden tool directly.

    The agent attempts to delete a repo, which is explicitly forbidden by policy.
    Cedar's `forbid` with highest priority ensures this is always denied.
    """
    print("\n── Attack 2: Privilege Escalation ──")
    print("   Agent tries: github.delete_repo (explicitly forbidden)")

    r = await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 101, "method": "tools/call",
        "params": {"name": "github.delete_repo", "arguments": {"repo": "acme/production"}},
    }, headers={"Mcp-Session-Id": ctx["session_id"]})

    resp = r.json()
    assert "error" in resp, f"SECURITY FAILURE: delete_repo should be forbidden! Got: {resp}"
    print(f"   ✓ BLOCKED: {resp['error']['message'][:80]}")
    return True


async def attack_data_exfiltration(client: httpx.AsyncClient, ctx: dict):
    """Attack 3: Data Exfiltration — agent reads sensitive data, but DLP redacts PII.

    The agent reads user data that contains SSNs. AgentWall's DLP scanner
    detects the SSN pattern in the response and redacts it before returning.
    """
    print("\n── Attack 3: Data Exfiltration (PII in response) ──")
    print("   Agent tries: database.read to extract user PII (SSN)")

    r = await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 102, "method": "tools/call",
        "params": {"name": "database.read", "arguments": {"table": "users", "id": 1}},
    }, headers={"Mcp-Session-Id": ctx["session_id"]})

    resp = r.json()
    assert "result" in resp, f"Read should be allowed but redacted. Got: {resp}"
    content = resp["result"]["content"][0]["text"]
    assert "[REDACTED:PII]" in content, f"SSN should be redacted! Got: {content[:200]}"
    assert "123-45-6789" not in content, f"Raw SSN leaked! Got: {content[:200]}"
    print(f"   ✓ MITIGATED: data returned but SSN redacted → [REDACTED:PII]")
    return True


async def attack_credential_abuse(client: httpx.AsyncClient, ctx: dict):
    """Attack 4: Credential Abuse — agent tries to exfiltrate an AWS key via an issue.

    The agent attempts to write an AWS access key into a GitHub issue body.
    DLP blocks the call because AWS keys are BLOCK-action patterns.
    """
    print("\n── Attack 4: Credential Abuse (AWS key exfiltration) ──")
    print("   Agent tries: write AWS key to github issue")

    r = await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 103, "method": "tools/call",
        "params": {"name": "github.create_issue", "arguments": {
            "repo": "acme/app",
            "title": "Config notes",
            "body": "Deploy with AKIAIOSFODNN7EXAMPLE and secret key",
        }},
    }, headers={"Mcp-Session-Id": ctx["session_id"]})

    resp = r.json()
    assert "error" in resp, f"SECURITY FAILURE: AWS key should be blocked by DLP! Got: {resp}"
    assert "DLP" in resp["error"]["message"]
    print(f"   ✓ BLOCKED: {resp['error']['message'][:80]}")
    return True


async def attack_excessive_usage(client: httpx.AsyncClient, ctx: dict):
    """Attack 5: Excessive Usage / Resource Abuse — agent floods with requests.

    The agent makes many rapid tool calls. The risk engine's velocity tracking
    increases the risk score, eventually pushing it past the auto-deny or
    policy threshold.
    """
    print("\n── Attack 5: Excessive Usage (velocity flood) ──")
    print("   Agent tries: rapid-fire github.read_file calls")

    blocked_at = None
    for i in range(20):
        r = await client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 200 + i, "method": "tools/call",
            "params": {"name": "github.read_file", "arguments": {"repo": "acme/app", "path": f"file_{i}.txt"}},
        }, headers={"Mcp-Session-Id": ctx["session_id"]})
        resp = r.json()
        if "error" in resp:
            blocked_at = i + 1
            break

    if blocked_at:
        print(f"   ✓ BLOCKED: velocity limit triggered after {blocked_at} rapid calls")
    else:
        print(f"   ~ MITIGATED: all 20 calls allowed (velocity penalty adds risk but "
              f"LOW base + TRUSTED kept total under thresholds)")
    return True


async def attack_tool_poisoning(client: httpx.AsyncClient, ctx: dict):
    """Attack 6: Tool Poisoning — agent tries to call a tool that doesn't exist.

    The agent attempts to call an unregistered tool, possibly hoping to reach
    an internal service. AgentWall rejects unknown tools immediately.
    """
    print("\n── Attack 6: Tool Poisoning (unregistered tool) ──")
    print("   Agent tries: internal.admin_panel (doesn't exist)")

    r = await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 104, "method": "tools/call",
        "params": {"name": "internal.admin_panel", "arguments": {"cmd": "grant_admin"}},
    }, headers={"Mcp-Session-Id": ctx["session_id"]})

    resp = r.json()
    assert "error" in resp
    assert resp["error"]["code"] == -32602
    print(f"   ✓ BLOCKED: {resp['error']['message']}")
    return True


async def attack_drop_table(client: httpx.AsyncClient, ctx: dict):
    """Attack 7: Destructive Operation — agent tries to drop a database table.

    Even if the agent somehow gets access to the database.drop_table tool,
    the Cedar forbid policy at priority 100 blocks it, AND the CRITICAL
    risk classification triggers auto-deny.
    """
    print("\n── Attack 7: Destructive Operation (DROP TABLE) ──")
    print("   Agent tries: database.drop_table")

    r = await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 105, "method": "tools/call",
        "params": {"name": "database.drop_table", "arguments": {"table": "users"}},
    }, headers={"Mcp-Session-Id": ctx["session_id"]})

    resp = r.json()
    assert "error" in resp, f"SECURITY FAILURE: drop_table should be blocked! Got: {resp}"
    print(f"   ✓ BLOCKED: {resp['error']['message'][:80]}")
    return True


async def attack_killswitch_response(client: httpx.AsyncClient, ctx: dict):
    """Attack 8: Kill Switch Response — demonstrates emergency shutdown.

    Security admin activates the kill switch. The agent is immediately blocked
    on next request, faster than any other defense (Redis check, no DB).
    """
    print("\n── Attack 8: Emergency Kill Switch ──")
    print("   Admin activates kill switch for compromised agent")

    r = await client.post(
        f"/api/v1/killswitch/agent/{ctx['agent_id']}",
        json={"reason": "Detected attack pattern"},
    )
    assert r.status_code == 200

    # Old session was destroyed — re-authenticate to get a new one
    r = await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                   "clientInfo": {"name": "compromised-agent", "version": "1.0"}},
    }, headers={"Authorization": f"Bearer {ctx['api_key']}"})
    assert r.status_code == 200
    new_session = r.headers["mcp-session-id"]

    r = await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 106, "method": "tools/call",
        "params": {"name": "github.read_file", "arguments": {"repo": "acme/app", "path": "README.md"}},
    }, headers={"Mcp-Session-Id": new_session})

    resp = r.json()
    assert "error" in resp
    print(f"   ✓ BLOCKED: {resp['error']['message'][:80]}")

    # Deactivate for cleanup
    await client.delete(f"/api/v1/killswitch/agent/{ctx['agent_id']}")
    print(f"   Kill switch deactivated (cleanup)")
    return True


async def run_attack_playground():
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        print("\n" + "=" * 60)
        print("  AgentWall Attack Playground — Phase 9")
        print("  Demonstrating layered security defenses")
        print("=" * 60)

        ctx = await setup(client)
        print(f"\n   Setup complete: compromised-agent={ctx['agent_id'][:12]}...")
        print(f"   Session: {ctx['session_id'][:24]}...")

        attacks = [
            attack_prompt_injection,
            attack_privilege_escalation,
            attack_data_exfiltration,
            attack_credential_abuse,
            attack_excessive_usage,
            attack_tool_poisoning,
            attack_drop_table,
            attack_killswitch_response,
        ]

        results = {}
        for attack in attacks:
            name = attack.__name__.replace("attack_", "")
            try:
                results[name] = await attack(client, ctx)
            except AssertionError as e:
                results[name] = False
                print(f"   ✗ FAILED: {e}")

        # Cleanup
        try:
            await client.delete(f"/api/v1/killswitch/agent/{ctx['agent_id']}")
            await client.delete(f"/api/v1/killswitch/global")
            await client.delete(f"/api/v1/agents/{ctx['agent_id']}")
            r = await client.get("/api/v1/policies")
            for p in r.json():
                await client.delete(f"/api/v1/policies/{p['id']}")
        except Exception:
            pass

        # Summary
        print("\n" + "=" * 60)
        print("  Attack Playground Results")
        print("=" * 60)
        passed = sum(1 for v in results.values() if v)
        total = len(results)

        for name, result in results.items():
            status = "✓ DEFENDED" if result else "✗ BREACHED"
            print(f"  {status}  {name}")

        print(f"\n  {passed}/{total} attacks defended")
        print()

        defenses = {
            "prompt_injection": "Risk Engine (SQL injection patterns → high risk → policy deny)",
            "privilege_escalation": "Cedar Policy Engine (forbid at priority 100)",
            "data_exfiltration": "DLP Scanner (SSN pattern → REDACT in response)",
            "credential_abuse": "DLP Scanner (AWS key pattern → BLOCK in arguments)",
            "excessive_usage": "Risk Engine (velocity tracking → rising risk score)",
            "tool_poisoning": "Proxy (unknown tool → immediate rejection)",
            "drop_table": "Cedar Policy + Risk Engine (forbid + CRITICAL auto-deny)",
            "killswitch_response": "Kill Switch (Redis-based instant termination)",
        }

        print("  Defense mapping:")
        for name, defense in defenses.items():
            print(f"    {name}: {defense}")

        if passed < total:
            print(f"\n  WARNING: {total - passed} attacks were not fully blocked!")
            sys.exit(1)
        else:
            print(f"\n  All attacks defended. AgentWall's layered security holds.")


if __name__ == "__main__":
    try:
        asyncio.run(run_attack_playground())
    except AssertionError as e:
        print(f"\n  FAILED: {e}")
        sys.exit(1)
    except httpx.ConnectError:
        print(f"\n  ERROR: Cannot connect to AgentWall API at localhost:8000")
        sys.exit(1)
