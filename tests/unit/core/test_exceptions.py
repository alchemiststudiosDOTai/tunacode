"""Tests for exception message formatting."""

from typing import Final

from tunacode.exceptions import (
    BULLET_PREFIX,
    SECTION_SEPARATOR,
    ConfigurationError,
    ContextOverflowError,
    ToolExecutionError,
    ValidationError,
)

BASE_MESSAGE: Final[str] = "Bad input"
SUGGESTED_FIX: Final[str] = "Use a valid value"
HELP_URL: Final[str] = "https://example.com/help"
EXAMPLE_ONE: Final[str] = "tunacode --help"
EXAMPLE_TWO: Final[str] = "tunacode --setup"
RECOVERY_COMMAND: Final[str] = "tunacode --retry"
TOOL_NAME: Final[str] = "formatter"
TOOL_MESSAGE: Final[str] = "tool failed"

SUGGESTED_FIX_SECTION: Final[str] = f"Suggested fix:\n{SUGGESTED_FIX}"
HELP_SECTION: Final[str] = f"More help:\n{HELP_URL}"
VALID_EXAMPLES_SECTION: Final[str] = (
    f"Valid examples:\n{BULLET_PREFIX}{EXAMPLE_ONE}\n{BULLET_PREFIX}{EXAMPLE_TWO}"
)
RECOVERY_SECTION: Final[str] = f"Recovery commands:\n{BULLET_PREFIX}{RECOVERY_COMMAND}"


def test_validation_error_formats_sections() -> None:
    """ValidationError should include suggested fixes and examples in order."""
    error = ValidationError(
        BASE_MESSAGE,
        suggested_fix=SUGGESTED_FIX,
        valid_examples=[EXAMPLE_ONE, EXAMPLE_TWO],
    )

    base_line = f"Validation failed: {BASE_MESSAGE}"
    expected_message = SECTION_SEPARATOR.join(
        [
            base_line,
            SUGGESTED_FIX_SECTION,
            VALID_EXAMPLES_SECTION,
        ]
    )

    assert str(error) == expected_message


def test_tool_execution_error_formats_recovery() -> None:
    """ToolExecutionError should include recovery commands when present."""
    error = ToolExecutionError(
        tool_name=TOOL_NAME,
        message=TOOL_MESSAGE,
        suggested_fix=SUGGESTED_FIX,
        recovery_commands=[RECOVERY_COMMAND],
    )

    base_line = f"Tool '{TOOL_NAME}' failed: {TOOL_MESSAGE}"
    expected_message = SECTION_SEPARATOR.join(
        [
            base_line,
            SUGGESTED_FIX_SECTION,
            RECOVERY_SECTION,
        ]
    )

    assert str(error) == expected_message


def test_configuration_error_formats_help_url() -> None:
    """ConfigurationError should include suggested fix and help link."""
    error = ConfigurationError(
        BASE_MESSAGE,
        suggested_fix=SUGGESTED_FIX,
        help_url=HELP_URL,
    )

    expected_message = SECTION_SEPARATOR.join(
        [
            BASE_MESSAGE,
            SUGGESTED_FIX_SECTION,
            HELP_SECTION,
        ]
    )

    assert str(error) == expected_message


def test_validation_error_without_optional_sections() -> None:
    """ValidationError should include only the base line when optional fields are empty."""
    error = ValidationError("missing value")

    assert str(error) == "Validation failed: missing value"


def test_context_overflow_error_includes_recovery_commands() -> None:
    """ContextOverflowError should expose model/token metadata and recovery guidance."""
    error = ContextOverflowError(
        estimated_tokens=250_000,
        max_tokens=200_000,
        model="openrouter:openai/gpt-4.1",
    )

    assert error.estimated_tokens == 250_000
    assert error.max_tokens == 200_000
    assert error.model == "openrouter:openai/gpt-4.1"
    assert "Context window exceeded" in str(error)
    assert "Recovery commands:" in str(error)
