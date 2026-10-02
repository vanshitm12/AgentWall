"""End-to-end test for Phase 9: Attack Playground.

Runs the attack playground and verifies all attacks are defended.
This is a wrapper around attack-lab/run_all.py that provides
the same test interface as other phase tests.
"""

import httpx
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "attack-lab"))
from run_all import run_attack_playground


if __name__ == "__main__":
    try:
        asyncio.run(run_attack_playground())
    except AssertionError as e:
        print(f"\n  FAILED: {e}")
        sys.exit(1)
    except httpx.ConnectError:
        print(f"\n  ERROR: Cannot connect to AgentWall API at localhost:8000")
        sys.exit(1)
