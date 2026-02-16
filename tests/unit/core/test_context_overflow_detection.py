"""Unit tests for context overflow error classification."""

from __future__ import annotations

import pytest

from tunacode.core.agents.helpers import is_context_overflow_error


@pytest.mark.parametrize(
    "error_text",
    [
        "provider_error(code=context_length_exceeded, message='limit reached')",
        "Maximum Context Length is 128000 tokens for this model",
    ],
)
def test_is_context_overflow_error_accepts_supported_error_forms(error_text: str) -> None:
    assert is_context_overflow_error(error_text)


@pytest.mark.parametrize(
    "error_text",
    [
        "rate_limit_exceeded",
        "authentication failed",
        "",
    ],
)
def test_is_context_overflow_error_rejects_non_overflow_errors(error_text: str) -> None:
    assert not is_context_overflow_error(error_text)
