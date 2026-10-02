"""End-to-end test for Phase 7: DLP (Data Loss Prevention).

Tests that sensitive data is detected, blocked, or redacted:
- Arguments with credit card numbers → BLOCK (deny the call)
- Arguments with SSN → REDACT (mask before forwarding)
- Response containing SSN → REDACT (mask before returning to agent)
- Arguments with email → LOG (allow but flag in audit)
- DLP scan REST API for dry-run checks
- DLP patterns list endpoint
- DLP findings recorded in audit metadata
- Multiple DLP patterns stack
- Clean arguments pass through unmodified
"""

import httpx
import asyncio
import sys

API_BASE = "http://localhost:8000"


async def test_dlp_system():
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        print("\n=== AgentWall Phase 7 — DLP E2E Test ===\n")

        # ── Setup ──

        print("1. Setup: agent, servers, permit-all policy...")
        r = await client.post("/api/v1/agents", json={"name": "dlp-agent", "description": "DLP test agent"})
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

        r = await client.post("/api/v1/policies", json={
            "name": "permit-all-dlp-test",
            "cedar_policy": 'permit(principal, action, resource);',
            "priority": 1,
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
                    "clientInfo": {"name": "dlp-agent", "version": "1.0"},
                },
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert r.status_code == 200
        session_id = r.headers.get("mcp-session-id")
        print(f"   OK: agent={agent_id[:8]}..., session={session_id[:20]}...")

        # ── Test 2: DLP BLOCK — credit card in arguments ──

        print("\n2. DLP BLOCK: credit card number in arguments → denied...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 10, "method": "tools/call",
                "params": {"name": "database.write", "arguments": {
                    "table": "payments",
                    "data": {"amount": 100, "card": "4111-1111-1111-1111"},
                }},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        resp = r.json()
        assert "error" in resp, f"Expected DLP block, got: {resp}"
        assert resp["error"]["code"] == -32603
        assert "DLP blocked" in resp["error"]["message"]
        assert "dlp_findings" in resp["error"]["data"]
        findings = resp["error"]["data"]["dlp_findings"]
        assert any(f["pattern"] == "credit_card" for f in findings)
        print(f"   OK: blocked — {len(findings)} finding(s): {[f['pattern'] for f in findings]}")

        # Verify audit event has DLP metadata
        r = await client.get(f"/api/v1/audit?agent_id={agent_id}&tool_name=database.write&page_size=1")
        assert r.status_code == 200
        audit_event = r.json()["events"][0]
        assert audit_event["decision"] == "DENY"
        assert "DLP blocked" in (audit_event["error"] or "")
        assert audit_event["metadata"].get("dlp_findings") is not None
        print(f"   OK: audit event recorded with DLP findings in metadata")

        # ── Test 3: DLP BLOCK — AWS access key in arguments ──

        print("\n3. DLP BLOCK: AWS access key in arguments → denied...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 11, "method": "tools/call",
                "params": {"name": "github.create_issue", "arguments": {
                    "repo": "acme/app",
                    "title": "Config update",
                    "body": "Set AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE in production",
                }},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        resp = r.json()
        assert "error" in resp
        assert "DLP blocked" in resp["error"]["message"]
        findings = resp["error"]["data"]["dlp_findings"]
        assert any(f["pattern"] == "aws_access_key" for f in findings)
        print(f"   OK: AWS key blocked — findings: {[f['pattern'] for f in findings]}")

        # ── Test 4: DLP BLOCK — private key in arguments ──

        print("\n4. DLP BLOCK: private key in arguments → denied...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 12, "method": "tools/call",
                "params": {"name": "github.create_issue", "arguments": {
                    "repo": "acme/app",
                    "title": "Key update",
                    "body": "-----BEGIN RSA PRIVATE KEY-----\nMIIBogIBAAJBALRiMLAHudeSA...",
                }},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        resp = r.json()
        assert "error" in resp
        findings = resp["error"]["data"]["dlp_findings"]
        assert any(f["pattern"] == "private_key" for f in findings)
        print(f"   OK: private key blocked — findings: {[f['pattern'] for f in findings]}")

        # ── Test 5: DLP REDACT on response — database.read returns SSN ──

        print("\n5. DLP REDACT on response: database.read returns SSN → redacted...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 13, "method": "tools/call",
                "params": {"name": "database.read", "arguments": {"table": "users", "id": 1}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        resp = r.json()
        assert "result" in resp, f"Expected result (redacted), got: {resp}"
        content_text = resp["result"]["content"][0]["text"]
        assert "[REDACTED:PII]" in content_text, f"SSN should be redacted, got: {content_text[:200]}"
        assert "123-45-6789" not in content_text, "Raw SSN should not appear in response"
        print(f"   OK: SSN redacted in response")

        # Check audit has DLP findings
        r = await client.get(f"/api/v1/audit?agent_id={agent_id}&tool_name=database.read&page_size=1")
        assert r.status_code == 200
        read_event = r.json()["events"][0]
        assert read_event["decision"] == "ALLOW"
        dlp_meta = read_event["metadata"].get("dlp_findings", [])
        assert any(f["pattern"] == "ssn" for f in dlp_meta), f"Audit should have SSN DLP finding, got: {dlp_meta}"
        print(f"   OK: audit event has DLP findings: {[f['pattern'] for f in dlp_meta]}")

        # ── Test 6: DLP LOG — email in arguments (allowed but flagged) ──

        print("\n6. DLP LOG: email in arguments → allowed but flagged in audit...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 14, "method": "tools/call",
                "params": {"name": "github.create_issue", "arguments": {
                    "repo": "acme/app",
                    "title": "Contact update",
                    "body": "Please reach out to admin@company.com for details",
                }},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        resp = r.json()
        assert "result" in resp, f"Email should be LOG action (allowed), got: {resp}"

        r = await client.get(f"/api/v1/audit?agent_id={agent_id}&tool_name=github.create_issue&page_size=1")
        assert r.status_code == 200
        email_event = r.json()["events"][0]
        dlp_meta = email_event["metadata"].get("dlp_findings", [])
        assert any(f["pattern"] == "email" for f in dlp_meta), f"Expected email finding, got: {dlp_meta}"
        print(f"   OK: email flagged in audit, call allowed")

        # ── Test 7: Clean arguments pass through unmodified ──

        print("\n7. Clean arguments: no sensitive data → no DLP interference...")
        r = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0", "id": 15, "method": "tools/call",
                "params": {"name": "github.read_file", "arguments": {"repo": "acme/app", "path": "README.md"}},
            },
            headers={"Mcp-Session-Id": session_id},
        )
        assert r.status_code == 200
        resp = r.json()
        assert "result" in resp
        # Check audit — should have no DLP findings
        r = await client.get(f"/api/v1/audit?agent_id={agent_id}&tool_name=github.read_file&page_size=1")
        assert r.status_code == 200
        clean_event = r.json()["events"][0]
        dlp_meta = clean_event["metadata"].get("dlp_findings", [])
        assert len(dlp_meta) == 0, f"Clean args should have no DLP findings, got: {dlp_meta}"
        print(f"   OK: clean args, no DLP findings in audit")

        # ── Test 8: DLP scan REST API ──

        print("\n8. DLP scan REST API: test scanning without tool call...")
        r = await client.post("/api/v1/dlp/scan", json={
            "text": "My SSN is 123-45-6789 and my card is 4111-1111-1111-1111",
        })
        assert r.status_code == 200
        scan = r.json()
        assert scan["would_block"] == True  # credit card = BLOCK
        assert len(scan["findings"]) >= 2
        pattern_names = [f["pattern"] for f in scan["findings"]]
        assert "ssn" in pattern_names
        assert "credit_card" in pattern_names
        assert "[REDACTED:" in scan["redacted_text"]
        assert "123-45-6789" not in scan["redacted_text"]
        print(f"   OK: found {len(scan['findings'])} patterns: {pattern_names}")
        print(f"   Redacted: {scan['redacted_text'][:80]}...")

        # ── Test 9: DLP scan REST API — structured data ──

        print("\n9. DLP scan REST API: structured data scanning...")
        r = await client.post("/api/v1/dlp/scan", json={
            "data": {
                "user": {"name": "Alice", "ssn": "999-88-7777", "email": "alice@test.com"},
                "config": {"api_key": "sk-abcdef1234567890123456789"},
            },
        })
        assert r.status_code == 200
        scan = r.json()
        assert len(scan["findings"]) >= 2
        fields = [f["field"] for f in scan["findings"]]
        assert any("ssn" in f for f in fields), f"Should find SSN in nested field, got: {fields}"
        assert scan["redacted_data"]["user"]["ssn"] == "[REDACTED:PII]"
        print(f"   OK: nested data scanned, findings in fields: {fields}")

        # ── Test 10: DLP patterns list endpoint ──

        print("\n10. DLP patterns list endpoint...")
        r = await client.get("/api/v1/dlp/patterns")
        assert r.status_code == 200
        patterns = r.json()
        assert len(patterns) >= 5
        names = [p["name"] for p in patterns]
        assert "ssn" in names
        assert "credit_card" in names
        assert "aws_access_key" in names
        print(f"   OK: {len(patterns)} patterns: {names}")

        # ── Test 11: Multiple DLP findings stack ──

        print("\n11. Multiple DLP findings: SSN + email + password → all detected...")
        r = await client.post("/api/v1/dlp/scan", json={
            "text": "SSN: 111-22-3333, email: bob@evil.com, password=SuperSecret123!",
        })
        assert r.status_code == 200
        scan = r.json()
        pattern_names = [f["pattern"] for f in scan["findings"]]
        assert "ssn" in pattern_names
        assert "email" in pattern_names
        assert "password_in_text" in pattern_names
        print(f"   OK: stacked findings: {pattern_names}")

        # ── Cleanup ──
        try:
            await client.delete(f"/mcp", headers={"Mcp-Session-Id": session_id})
            await client.delete(f"/api/v1/agents/{agent_id}")
            r = await client.get("/api/v1/policies")
            for p in r.json():
                await client.delete(f"/api/v1/policies/{p['id']}")
        except Exception:
            pass

        print("\n=== ALL PHASE 7 TESTS PASSED ===\n")
        print("Phase 7 verified:")
        print("  ✓ DLP BLOCK: credit card in arguments → denied")
        print("  ✓ DLP BLOCK: AWS access key in arguments → denied")
        print("  ✓ DLP BLOCK: private key in arguments → denied")
        print("  ✓ DLP REDACT: SSN in response → masked before returning to agent")
        print("  ✓ DLP LOG: email in arguments → allowed but flagged in audit")
        print("  ✓ Clean arguments pass through with no DLP interference")
        print("  ✓ DLP findings recorded in audit metadata")
        print("  ✓ DLP scan REST API (text)")
        print("  ✓ DLP scan REST API (structured data)")
        print("  ✓ DLP patterns list endpoint")
        print("  ✓ Multiple DLP findings stack")


if __name__ == "__main__":
    try:
        asyncio.run(test_dlp_system())
    except AssertionError as e:
        print(f"\n  FAILED: {e}")
        sys.exit(1)
    except httpx.ConnectError:
        print(f"\n  ERROR: Cannot connect to AgentWall API at localhost:8000")
        sys.exit(1)
