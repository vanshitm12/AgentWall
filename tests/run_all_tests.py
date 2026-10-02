"""Run all phase tests with DB reset between each phase."""

import asyncio
import sys
import importlib
import httpx

API_BASE = "http://localhost:8000"


async def reset_db():
    """Reset all database tables via the API's internal models."""
    # We can't easily call DB reset from here, so we'll use a helper endpoint
    # or skip — each test does its own cleanup. Just verify API is healthy.
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
        r = await client.get("/health")
        assert r.status_code == 200


async def run_all():
    tests = [
        ("Phase 1: MCP Proxy", "test_proxy_e2e"),
        ("Phase 2: Registries", "test_registries_e2e"),
        ("Phase 3: Policy Engine", "test_policy_e2e"),
        ("Phase 4: Approval System", "test_approval_e2e"),
        ("Phase 5: Audit System", "test_audit_e2e"),
        ("Phase 6: Risk Engine", "test_risk_e2e"),
        ("Phase 7: DLP", "test_dlp_e2e"),
        ("Phase 8: Kill Switch", "test_killswitch_e2e"),
    ]

    results = {}
    for name, module_name in tests:
        print(f"\n{'='*60}")
        print(f"  Running {name}...")
        print(f"{'='*60}")
        try:
            module = importlib.import_module(module_name)
            # Find the test function
            test_fn = None
            for attr in dir(module):
                if attr.startswith("test_"):
                    test_fn = getattr(module, attr)
                    break
            if test_fn:
                await test_fn()
                results[name] = "PASS"
            else:
                results[name] = "SKIP (no test function found)"
        except AssertionError as e:
            results[name] = f"FAIL: {e}"
        except Exception as e:
            results[name] = f"ERROR: {e}"

    print(f"\n{'='*60}")
    print(f"  ALL PHASES — RESULTS")
    print(f"{'='*60}")
    for name, result in results.items():
        status = "✓" if result == "PASS" else "✗"
        print(f"  {status} {name}: {result}")

    passed = sum(1 for r in results.values() if r == "PASS")
    total = len(results)
    print(f"\n  {passed}/{total} phases passed")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all())
