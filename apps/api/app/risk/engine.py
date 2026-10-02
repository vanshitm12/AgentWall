"""Dynamic risk scoring engine.

Scores every tool call on a 0-100 scale by combining multiple signals:
1. Tool risk classification (static base score from DB)
2. Server trust level (multiplier for untrusted servers)
3. Argument sensitivity (pattern detection for dangerous content)
4. Call velocity (Redis-based rate tracking per agent+tool)

Risk levels:
  LOW      0-25
  MEDIUM  26-50
  HIGH    51-75
  CRITICAL 76-100

The risk score and level are:
- Passed to Cedar as context (policies can use context.risk_score / context.risk_level)
- Recorded in audit events
- Used for auto-deny when score exceeds a configurable threshold
- Attached to approval requests
"""

import logging
import re
import time
from dataclasses import dataclass

from app.config import settings
from app.redis import redis_client

logger = logging.getLogger(__name__)

BASE_SCORES = {
    "LOW": 10,
    "MEDIUM": 30,
    "HIGH": 60,
    "CRITICAL": 90,
}

TRUST_MULTIPLIERS = {
    "TRUSTED": 1.0,
    "UNTRUSTED": 1.5,
    "UNKNOWN": 1.3,
}

SENSITIVE_PATTERNS = [
    (re.compile(r"\bDROP\s+(TABLE|DATABASE)\b", re.IGNORECASE), 25, "destructive SQL"),
    (re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE), 15, "delete SQL"),
    (re.compile(r"\bTRUNCATE\b", re.IGNORECASE), 20, "truncate SQL"),
    (re.compile(r"\b(password|secret|token|api_key|private_key|credential)\b", re.IGNORECASE), 10, "sensitive keyword"),
    (re.compile(r"\.(pem|key|env|credentials|secret)$", re.IGNORECASE), 10, "sensitive file"),
    (re.compile(r"rm\s+-rf\b", re.IGNORECASE), 20, "destructive command"),
    (re.compile(r"\*\s+FROM\b.*\bWHERE\s+1\s*=\s*1", re.IGNORECASE), 15, "unrestricted query"),
    (re.compile(r";\s*(DROP|DELETE|TRUNCATE|ALTER)", re.IGNORECASE), 25, "SQL injection pattern"),
]

VELOCITY_WINDOW_SECONDS = 60
VELOCITY_THRESHOLD = 10
VELOCITY_PENALTY = 15

RISK_KEY_PREFIX = "risk:velocity:"


@dataclass
class RiskResult:
    score: int
    level: str
    factors: list[str]


def _score_to_level(score: int) -> str:
    if score <= 25:
        return "LOW"
    if score <= 50:
        return "MEDIUM"
    if score <= 75:
        return "HIGH"
    return "CRITICAL"


def _scan_arguments(arguments: dict | None) -> tuple[int, list[str]]:
    """Scan argument values for sensitive patterns. Returns (penalty, factors)."""
    if not arguments:
        return 0, []

    text = _flatten_to_text(arguments)
    total_penalty = 0
    factors = []

    for pattern, penalty, label in SENSITIVE_PATTERNS:
        if pattern.search(text):
            total_penalty += penalty
            factors.append(f"arg_sensitivity:{label} (+{penalty})")

    return total_penalty, factors


def _flatten_to_text(obj: object) -> str:
    """Recursively flatten a dict/list into a single string for pattern matching."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(_flatten_to_text(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return " ".join(_flatten_to_text(v) for v in obj)
    return str(obj)


async def _check_velocity(agent_id: str, tool_name: str, read_only: bool = False) -> tuple[int, list[str]]:
    """Track call rate and penalize high velocity. Returns (penalty, factors).

    If read_only=True, only reads the current count without adding a new entry.
    """
    key = f"{RISK_KEY_PREFIX}{agent_id}:{tool_name}"
    now = time.time()
    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, now - VELOCITY_WINDOW_SECONDS)
    if not read_only:
        pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, VELOCITY_WINDOW_SECONDS + 10)
    results = await pipe.execute()
    count = results[2] if not read_only else results[1]

    if count > VELOCITY_THRESHOLD:
        penalty = min(VELOCITY_PENALTY * ((count - VELOCITY_THRESHOLD) // 5 + 1), 40)
        return penalty, [f"velocity:{count} calls in {VELOCITY_WINDOW_SECONDS}s (+{penalty})"]

    return 0, []


async def score_tool_call(
    agent_id: str,
    tool_name: str,
    risk_classification: str,
    server_trust_level: str,
    arguments: dict | None = None,
    dry_run: bool = False,
) -> RiskResult:
    """Compute a risk score for a tool call."""
    factors = []

    # 1. Base score from tool classification
    base = BASE_SCORES.get(risk_classification, 30)
    factors.append(f"base:{risk_classification}={base}")

    # 2. Trust multiplier
    multiplier = TRUST_MULTIPLIERS.get(server_trust_level, 1.0)
    if multiplier != 1.0:
        factors.append(f"trust:{server_trust_level} (x{multiplier})")

    adjusted = int(base * multiplier)

    # 3. Argument sensitivity
    arg_penalty, arg_factors = _scan_arguments(arguments)
    adjusted += arg_penalty
    factors.extend(arg_factors)

    # 4. Call velocity
    vel_penalty, vel_factors = await _check_velocity(agent_id, tool_name, read_only=dry_run)
    adjusted += vel_penalty
    factors.extend(vel_factors)

    # Clamp to 0-100
    score = max(0, min(100, adjusted))
    level = _score_to_level(score)

    logger.debug(
        "RISK | agent=%s | tool=%s | score=%d | level=%s | factors=%s",
        agent_id[:8], tool_name, score, level, factors,
    )

    return RiskResult(score=score, level=level, factors=factors)
