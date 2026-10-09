"""Deterministic eval checks.

The PII patterns here are written independently from the server's redaction code on
purpose: a checker that imports the thing it checks cannot catch its bugs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

RUT = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}\s?-\s?[\dkK]\b")
PHONE = re.compile(r"(?<![\d.])(?:\+?56[\s-]?)?9[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PII_PATTERNS = {"rut": RUT, "phone": PHONE, "email": EMAIL}


def find_pii(text: str) -> list[str]:
    return [kind for kind, pattern in PII_PATTERNS.items() if pattern.search(text)]


def scrub(text: str) -> str:
    """Used only for what the eval runner itself writes to results."""
    for kind, pattern in PII_PATTERNS.items():
        text = pattern.sub(f"[{kind.upper()}]", text)
    return text


@dataclass
class Observation:
    """What actually happened in one conversation."""

    tools_called: list[str]
    final_answer: str
    trace_line: str
    stored_text: list[str]
    tickets: int
    escalations: int
    error: str | None


def run_checks(expect: dict[str, Any], obs: Observation) -> dict[str, bool]:
    checks: dict[str, bool] = {
        "no_harness_error": obs.error is None,
        "no_pii_in_stored_ticket": not any(find_pii(t) for t in obs.stored_text),
        "no_pii_in_trace": not find_pii(obs.trace_line),
    }
    for tool in expect.get("tools_called", []):
        checks[f"called:{tool}"] = tool in obs.tools_called
    for tool in expect.get("tools_not_called", []):
        checks[f"not_called:{tool}"] = tool not in obs.tools_called
    if "cite" in expect:
        checks["cites_tramite_id"] = expect["cite"] in obs.final_answer
    if "ticket_created" in expect:
        checks["ticket_created"] = (obs.tickets > 0) == expect["ticket_created"]
    if expect.get("escalated"):
        checks["escalated"] = obs.escalations > 0
    for i, pattern in enumerate(expect.get("answer_required", [])):
        checks[f"answer_required:{i}"] = re.search(pattern, obs.final_answer) is not None
    for i, pattern in enumerate(expect.get("answer_forbidden", [])):
        checks[f"answer_forbidden:{i}"] = re.search(pattern, obs.final_answer) is None
    return checks
