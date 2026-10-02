"""Cedar policy engine.

Evaluates every tool call against the active Cedar policies.
Returns ALLOW, DENY, or APPROVAL_REQUIRED.

Cedar semantics:
- `permit(...)` allows the request
- `forbid(...)` denies the request (overrides permit)
- No matching policy → default-deny

APPROVAL_REQUIRED convention:
A Policy with metadata {"decision": "approval"} is an approval policy.
Its Cedar text is a normal permit/forbid — if it would match, the engine
returns APPROVAL_REQUIRED instead of ALLOW. Approval policies are excluded
from the regular allow/deny evaluation to prevent them from accidentally
granting access.
"""

import logging
from dataclasses import dataclass
from enum import Enum

import cedarpy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.policy import Policy

logger = logging.getLogger(__name__)


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


@dataclass
class EvaluationResult:
    decision: PolicyDecision
    policy_id: str | None = None
    policy_name: str | None = None
    reasons: list[str] | None = None


class PolicyEngine:

    def __init__(self) -> None:
        self._policy_cache: list[Policy] | None = None

    def invalidate_cache(self) -> None:
        self._policy_cache = None

    async def _load_policies(self, db: AsyncSession | None = None) -> list[Policy]:
        if self._policy_cache is not None:
            return self._policy_cache

        if db is None:
            async with async_session() as db:
                return await self._load_policies(db)

        result = await db.execute(
            select(Policy)
            .where(Policy.enabled == True)  # noqa: E712
            .order_by(Policy.priority.desc())
        )
        policies = list(result.scalars().all())
        self._policy_cache = policies
        logger.info("Loaded %d active policies", len(policies))
        return policies

    async def evaluate(
        self,
        agent_id: str,
        agent_name: str,
        tool_name: str,
        server_name: str,
        risk_classification: str,
        server_trust_level: str,
        arguments: dict | None = None,
        risk_score: int = 0,
        risk_level: str = "LOW",
    ) -> EvaluationResult:
        policies = await self._load_policies()

        if not policies:
            logger.info("DENY (default) | no policies loaded | tool=%s agent=%s", tool_name, agent_id)
            return EvaluationResult(decision=PolicyDecision.DENY, reasons=["no policies configured"])

        request = {
            "principal": f'User::"{agent_name}"',
            "action": 'Action::"call"',
            "resource": f'Tool::"{tool_name}"',
            "context": {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "tool_name": tool_name,
                "server_name": server_name,
                "risk_classification": risk_classification,
                "server_trust_level": server_trust_level,
                "risk_score": risk_score,
                "risk_level": risk_level,
            },
        }

        approval_policies = [p for p in policies if p.metadata_.get("decision") == "approval"]
        regular_policies = [p for p in policies if p.metadata_.get("decision") != "approval"]

        # Pass 1: Check approval-tagged policies first
        for policy in approval_policies:
            try:
                result = cedarpy.is_authorized(request, policy.cedar_policy, [])
            except Exception:
                continue

            if result.decision == cedarpy.Decision.Allow:
                logger.info(
                    "APPROVAL_REQUIRED | agent=%s | tool=%s | policy=%s",
                    agent_name, tool_name, policy.name,
                )
                return EvaluationResult(
                    decision=PolicyDecision.APPROVAL_REQUIRED,
                    policy_id=policy.id,
                    policy_name=policy.name,
                    reasons=["approval required by policy"],
                )

        # Pass 2: Evaluate regular policies (excludes approval policies)
        if not regular_policies:
            logger.info("DENY | agent=%s | tool=%s | no regular policies", agent_name, tool_name)
            return EvaluationResult(
                decision=PolicyDecision.DENY,
                reasons=["no matching permit policy (default-deny)"],
            )

        combined_cedar = "\n\n".join(p.cedar_policy for p in regular_policies)

        try:
            result = cedarpy.is_authorized(request, combined_cedar, [])
        except Exception as e:
            logger.error("Cedar evaluation error: %s", e)
            return EvaluationResult(
                decision=PolicyDecision.DENY,
                reasons=[f"policy evaluation error: {e}"],
            )

        reasons = list(result.diagnostics.reasons) if result.diagnostics.reasons else []

        if result.decision == cedarpy.Decision.Allow:
            matched = self._find_matching_policy(regular_policies, reasons)
            logger.info(
                "ALLOW | agent=%s | tool=%s | policy=%s",
                agent_name, tool_name, matched.name if matched else "unknown",
            )
            return EvaluationResult(
                decision=PolicyDecision.ALLOW,
                policy_id=matched.id if matched else None,
                policy_name=matched.name if matched else None,
                reasons=reasons,
            )

        logger.info("DENY | agent=%s | tool=%s | reasons=%s", agent_name, tool_name, reasons)
        matched = self._find_matching_policy(regular_policies, reasons)
        return EvaluationResult(
            decision=PolicyDecision.DENY,
            policy_id=matched.id if matched else None,
            policy_name=matched.name if matched else None,
            reasons=reasons if reasons else ["no matching permit policy (default-deny)"],
        )

    def _find_matching_policy(
        self, policies: list[Policy], reasons: list[str]
    ) -> Policy | None:
        if not reasons:
            return None
        for i, policy in enumerate(policies):
            if f"policy{i}" in reasons:
                return policy
        return None


policy_engine = PolicyEngine()
