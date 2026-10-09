"""PII redaction for Chilean identifiers (Ley 19.628). Applied before anything is persisted.

Covers RUT, phone numbers and email addresses. It does not claim to catch names or free
text street addresses (see docs/spec.md, non-goals).
"""

from __future__ import annotations

import re

from pydantic import BaseModel

_RUT = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}\s?-\s?[\dkK]\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Mobile (9 XXXX XXXX) and landline (2 XXXX XXXX), with or without the +56 country code.
_PHONE = re.compile(r"(?<![\d.])(?:\+?56[\s-]?)?[92][\s-]?\d{4}[\s-]?\d{4}(?!\d)")

# Order matters: RUT first so its digits are not consumed by the phone pattern.
_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("rut", _RUT, "[RUT]"),
    ("email", _EMAIL, "[EMAIL]"),
    ("phone", _PHONE, "[TELEFONO]"),
)


class RedactionCounts(BaseModel):
    rut: int = 0
    phone: int = 0
    email: int = 0

    def __add__(self, other: RedactionCounts) -> RedactionCounts:
        return RedactionCounts(
            rut=self.rut + other.rut, phone=self.phone + other.phone, email=self.email + other.email
        )


def redact(text: str) -> tuple[str, RedactionCounts]:
    counts: dict[str, int] = {}
    for kind, pattern, marker in _PATTERNS:
        text, counts[kind] = pattern.subn(marker, text)
    return text, RedactionCounts(**counts)


def redact_text(text: str) -> str:
    return redact(text)[0]
