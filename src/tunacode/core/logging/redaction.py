"""Redaction filter for scrubbing sensitive data from log output.

Implements path-based field redaction and regex-based message redaction,
inspired by Pino's redaction spec for path-based config.

Two redaction strategies:
1. Field-name matching: any key in structured extra data whose name contains
   a sensitive substring gets its value replaced with REDACTED_PLACEHOLDER.
2. Regex matching: known secret patterns (API keys, emails, bearer tokens)
   are scrubbed from free-text log messages.
"""

from __future__ import annotations

import logging
import re
from typing import Any

REDACTED_PLACEHOLDER: str = "[REDACTED]"

# ---------------------------------------------------------------------------
# Field-name redaction
# ---------------------------------------------------------------------------

# Any log kwarg/extra key containing one of these substrings (case-insensitive)
# will have its value replaced with REDACTED_PLACEHOLDER.
SENSITIVE_FIELD_PATTERNS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "token",
        "api_key",
        "apikey",
        "secret",
        "authorization",
        "credential",
        "private_key",
        "access_key",
        "session_key",
    }
)

# ---------------------------------------------------------------------------
# Regex-based value redaction
# ---------------------------------------------------------------------------

# Each entry is (compiled_pattern, replacement_string).
_SENSITIVE_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # OpenAI / Anthropic API keys: sk-... or sk-ant-...
    (re.compile(r"\bsk-[a-zA-Z0-9_-]{16,}\b"), REDACTED_PLACEHOLDER),
    # Bearer tokens in authorization headers
    (re.compile(r"Bearer\s+[a-zA-Z0-9._\-]{10,}"), f"Bearer {REDACTED_PLACEHOLDER}"),
    # Email addresses
    (
        re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
        REDACTED_PLACEHOLDER,
    ),
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_sensitive_field(field_name: str) -> bool:
    """Return True if *field_name* matches any sensitive-field pattern."""
    lowered = field_name.lower()
    return any(pattern in lowered for pattern in SENSITIVE_FIELD_PATTERNS)


def redact_message(message: str) -> str:
    """Apply regex-based redaction to a log message string."""
    if not isinstance(message, str):
        return message
    result = message
    for pattern, replacement in _SENSITIVE_VALUE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive fields in a dictionary."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if is_sensitive_field(key):
            result[key] = REDACTED_PLACEHOLDER
        elif isinstance(value, dict):
            result[key] = redact_dict(value)
        elif isinstance(value, str):
            result[key] = redact_message(value)
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# Stdlib logging filter
# ---------------------------------------------------------------------------

# Custom attribute name used by LogManager to attach structured extra data
# to stdlib LogRecord instances.
TUNACODE_EXTRA_ATTR: str = "tunacode_extra"


class RedactingFilter(logging.Filter):
    """Stdlib logging filter that scrubs sensitive data from log records.

    Redacts:
    1. ``record.msg`` — regex-based patterns (API keys, emails, bearer tokens).
    2. ``record.args`` — format-string arguments are individually scrubbed.
    3. ``record.tunacode_extra`` — field-name-based redaction for known
       sensitive keys plus regex scrub on string values.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_message(record.msg)

        # Redact format-string arguments
        if isinstance(record.args, dict):
            record.args = redact_dict(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(
                redact_message(arg) if isinstance(arg, str) else arg for arg in record.args
            )

        # Redact custom structured data attached by LogManager
        tunacode_extra = getattr(record, TUNACODE_EXTRA_ATTR, None)
        if isinstance(tunacode_extra, dict):
            setattr(record, TUNACODE_EXTRA_ATTR, redact_dict(tunacode_extra))

        return True
