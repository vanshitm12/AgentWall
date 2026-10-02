"""DLP (Data Loss Prevention) scanner.

Scans tool call arguments and responses for sensitive data:
- PII: SSN, credit card numbers, email addresses, phone numbers
- Secrets: AWS keys, JWT tokens, private keys, generic API keys/tokens
- Custom: configurable patterns

Each pattern has a default action:
  BLOCK  — deny the call or strip the response
  REDACT — mask sensitive data with [REDACTED:category]
  LOG    — allow but flag the finding in audit metadata

The scanner:
1. Scans all string values in arguments/responses
2. Returns a list of DlpFinding with the pattern name, category, action, and match location
3. For REDACT: can produce a deep copy with sensitive data masked
"""

import copy
import logging
import re
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DlpAction(str, Enum):
    BLOCK = "BLOCK"
    REDACT = "REDACT"
    LOG = "LOG"


class DlpCategory(str, Enum):
    PII = "PII"
    SECRET = "SECRET"
    CREDENTIAL = "CREDENTIAL"


@dataclass
class DlpPattern:
    name: str
    regex: re.Pattern
    category: DlpCategory
    action: DlpAction
    description: str


@dataclass
class DlpFinding:
    pattern_name: str
    category: str
    action: str
    matched_text_preview: str
    field_path: str = ""


BUILT_IN_PATTERNS: list[DlpPattern] = [
    DlpPattern(
        name="ssn",
        regex=re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        category=DlpCategory.PII,
        action=DlpAction.REDACT,
        description="US Social Security Number",
    ),
    DlpPattern(
        name="credit_card",
        regex=re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
        category=DlpCategory.PII,
        action=DlpAction.BLOCK,
        description="Credit card number (16 digits)",
    ),
    DlpPattern(
        name="email",
        regex=re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        category=DlpCategory.PII,
        action=DlpAction.LOG,
        description="Email address",
    ),
    DlpPattern(
        name="phone_us",
        regex=re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        category=DlpCategory.PII,
        action=DlpAction.LOG,
        description="US phone number",
    ),
    DlpPattern(
        name="aws_access_key",
        regex=re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        category=DlpCategory.SECRET,
        action=DlpAction.BLOCK,
        description="AWS access key ID",
    ),
    DlpPattern(
        name="jwt_token",
        regex=re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        category=DlpCategory.SECRET,
        action=DlpAction.REDACT,
        description="JWT token",
    ),
    DlpPattern(
        name="private_key",
        regex=re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+)?PRIVATE\s+KEY-----"),
        category=DlpCategory.SECRET,
        action=DlpAction.BLOCK,
        description="PEM private key header",
    ),
    DlpPattern(
        name="generic_secret",
        regex=re.compile(
            r"""(?:api[_-]?key|api[_-]?secret|auth[_-]?token|access[_-]?token|secret[_-]?key|private[_-]?key)"""
            r"""[\s]*[=:]\s*["']?([A-Za-z0-9+/=_-]{20,})["']?""",
            re.IGNORECASE,
        ),
        category=DlpCategory.CREDENTIAL,
        action=DlpAction.REDACT,
        description="Generic API key/secret assignment",
    ),
    DlpPattern(
        name="password_in_text",
        regex=re.compile(
            r"""(?:password|passwd|pwd)[\s]*[=:]\s*["']?(\S{4,})["']?""",
            re.IGNORECASE,
        ),
        category=DlpCategory.CREDENTIAL,
        action=DlpAction.REDACT,
        description="Password assignment in text",
    ),
]


def _preview(match_text: str, max_len: int = 20) -> str:
    """Create a safe preview of matched text (first/last chars only)."""
    if len(match_text) <= 8:
        return match_text[:2] + "***"
    return match_text[:4] + "..." + match_text[-4:]


def scan_text(text: str, field_path: str = "") -> list[DlpFinding]:
    """Scan a single string for all DLP patterns."""
    findings: list[DlpFinding] = []
    for pattern in BUILT_IN_PATTERNS:
        for match in pattern.regex.finditer(text):
            findings.append(DlpFinding(
                pattern_name=pattern.name,
                category=pattern.category.value,
                action=pattern.action.value,
                matched_text_preview=_preview(match.group()),
                field_path=field_path,
            ))
    return findings


def scan_dict(data: dict | None, path_prefix: str = "") -> list[DlpFinding]:
    """Recursively scan all string values in a dict."""
    if not data:
        return []
    findings: list[DlpFinding] = []
    for key, value in data.items():
        field_path = f"{path_prefix}.{key}" if path_prefix else key
        if isinstance(value, str):
            findings.extend(scan_text(value, field_path))
        elif isinstance(value, dict):
            findings.extend(scan_dict(value, field_path))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                item_path = f"{field_path}[{i}]"
                if isinstance(item, str):
                    findings.extend(scan_text(item, item_path))
                elif isinstance(item, dict):
                    findings.extend(scan_dict(item, item_path))
    return findings


def scan_content_list(content: list[dict], path_prefix: str = "response") -> list[DlpFinding]:
    """Scan MCP response content items (list of {type, text, ...})."""
    findings: list[DlpFinding] = []
    for i, item in enumerate(content):
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            findings.extend(scan_text(item["text"], f"{path_prefix}[{i}].text"))
    return findings


def redact_text(text: str) -> str:
    """Replace all REDACT-action pattern matches in text with [REDACTED:category]."""
    result = text
    for pattern in BUILT_IN_PATTERNS:
        if pattern.action in (DlpAction.REDACT, DlpAction.BLOCK):
            result = pattern.regex.sub(f"[REDACTED:{pattern.category.value}]", result)
    return result


def redact_dict(data: dict | None) -> dict | None:
    """Deep copy and redact all string values in a dict."""
    if not data:
        return data
    result = copy.deepcopy(data)
    _redact_dict_inplace(result)
    return result


def _redact_dict_inplace(data: dict) -> None:
    for key, value in data.items():
        if isinstance(value, str):
            data[key] = redact_text(value)
        elif isinstance(value, dict):
            _redact_dict_inplace(value)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str):
                    data[key][i] = redact_text(item)
                elif isinstance(item, dict):
                    _redact_dict_inplace(item)


def redact_content_list(content: list[dict]) -> list[dict]:
    """Deep copy and redact MCP response content items."""
    result = copy.deepcopy(content)
    for item in result:
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            item["text"] = redact_text(item["text"])
    return result


def has_block_finding(findings: list[DlpFinding]) -> bool:
    return any(f.action == DlpAction.BLOCK for f in findings)


def has_redact_finding(findings: list[DlpFinding]) -> bool:
    return any(f.action == DlpAction.REDACT for f in findings)


def findings_to_summary(findings: list[DlpFinding]) -> list[dict]:
    """Convert findings to a serializable summary for audit metadata."""
    return [
        {
            "pattern": f.pattern_name,
            "category": f.category,
            "action": f.action,
            "field": f.field_path,
            "preview": f.matched_text_preview,
        }
        for f in findings
    ]
