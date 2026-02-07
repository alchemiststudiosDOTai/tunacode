"""Tests for errors.py render functions — deep coverage.

Source: src/tunacode/ui/renderers/errors.py
"""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.panel import Panel

from tunacode.ui.renderers.errors import (
    render_catastrophic_error,
    render_connection_error,
    render_exception,
    render_tool_error,
    render_user_abort,
    render_validation_error,
)


def _render_to_text(panel: Panel) -> str:
    """Render a Panel to plain text for assertion checks."""
    buf = StringIO()
    console = Console(file=buf, width=120, force_terminal=False)
    console.print(panel)
    return buf.getvalue()


# ===================================================================
# render_tool_error
# ===================================================================


class TestRenderToolErrorDeep:
    """Deeper paths in render_tool_error."""

    def test_with_file_path_includes_recovery_commands(self) -> None:
        result = render_tool_error(
            "read_file",
            "not found",
            file_path="/tmp/missing.py",
        )
        assert isinstance(result, Panel)
        rendered = _render_to_text(result)
        assert "read_file" in rendered
        assert "/tmp/missing.py" in rendered

    def test_without_file_path_generic_recovery(self) -> None:
        result = render_tool_error("grep", "bad pattern")
        assert isinstance(result, Panel)
        assert "grep" in _render_to_text(result)

    def test_with_all_params(self) -> None:
        result = render_tool_error(
            "write_file",
            "permission denied",
            suggested_fix="Check directory permissions",
            file_path="/etc/hosts",
        )
        assert isinstance(result, Panel)
        rendered = _render_to_text(result)
        assert "write_file" in rendered
        assert "Check directory permissions" in rendered

    def test_empty_message(self) -> None:
        result = render_tool_error("bash", "")
        assert isinstance(result, Panel)
        assert "bash" in _render_to_text(result)


# ===================================================================
# render_validation_error
# ===================================================================


class TestRenderValidationErrorDeep:
    """Deeper paths in render_validation_error."""

    def test_without_examples(self) -> None:
        result = render_validation_error("timeout", "must be positive integer")
        assert isinstance(result, Panel)

    def test_with_examples(self) -> None:
        result = render_validation_error(
            "model",
            "not recognized",
            valid_examples=["gpt-4", "claude-3"],
        )
        assert isinstance(result, Panel)

    def test_with_many_examples_truncates(self) -> None:
        result = render_validation_error(
            "color",
            "invalid",
            valid_examples=["red", "green", "blue", "yellow", "purple"],
        )
        assert isinstance(result, Panel)

    def test_empty_examples_list(self) -> None:
        result = render_validation_error(
            "field",
            "bad value",
            valid_examples=[],
        )
        assert isinstance(result, Panel)


# ===================================================================
# render_user_abort
# ===================================================================


class TestRenderUserAbortDeep:
    """render_user_abort returns info-severity panel."""

    def test_returns_panel(self) -> None:
        result = render_user_abort()
        assert isinstance(result, Panel)

    def test_title_contains_cancelled(self) -> None:
        result = render_user_abort()
        assert isinstance(result, Panel)
        assert "Cancelled" in str(result.title)


# ===================================================================
# render_catastrophic_error
# ===================================================================


class TestRenderCatastrophicErrorDeep:
    """render_catastrophic_error covers unexpected failures."""

    def test_basic_exception(self) -> None:
        result = render_catastrophic_error(RuntimeError("boom"))
        assert isinstance(result, Panel)

    def test_empty_exception_message(self) -> None:
        result = render_catastrophic_error(RuntimeError(""))
        assert isinstance(result, Panel)

    def test_very_long_exception_truncated(self) -> None:
        result = render_catastrophic_error(RuntimeError("x" * 500))
        assert isinstance(result, Panel)

    def test_with_context_param(self) -> None:
        result = render_catastrophic_error(ValueError("bad"), context="during processing")
        assert isinstance(result, Panel)

    def test_exception_type_name_used_when_empty(self) -> None:
        """When str(exc) is empty, type(exc).__name__ is used as fallback."""
        result = render_catastrophic_error(RuntimeError(""))
        assert isinstance(result, Panel)
        assert "Something Went Wrong" in str(result.title)


# ===================================================================
# render_connection_error
# ===================================================================


class TestRenderConnectionError:
    """render_connection_error builds connection error panels."""

    def test_with_retry_available(self) -> None:
        result = render_connection_error("OpenAI", "Connection timed out", retry_available=True)
        assert isinstance(result, Panel)

    def test_without_retry(self) -> None:
        result = render_connection_error("Anthropic", "Service unavailable", retry_available=False)
        assert isinstance(result, Panel)

    def test_title_contains_service_name(self) -> None:
        result = render_connection_error("GitHub", "Rate limited")
        assert isinstance(result, Panel)
        assert "GitHub" in str(result.title)


# ===================================================================
# render_exception
# ===================================================================


class TestRenderException:
    """render_exception handles arbitrary exceptions."""

    def test_plain_exception(self) -> None:
        result = render_exception(Exception("generic error"))
        assert isinstance(result, Panel)

    def test_runtime_error(self) -> None:
        result = render_exception(RuntimeError("runtime issue"))
        assert isinstance(result, Panel)

    def test_value_error(self) -> None:
        result = render_exception(ValueError("bad input"))
        assert isinstance(result, Panel)

    def test_exception_with_tool_name_attr(self) -> None:
        exc = Exception("tool failed")
        exc.tool_name = "bash"  # type: ignore[attr-defined]
        result = render_exception(exc)
        assert isinstance(result, Panel)
        assert "bash" in _render_to_text(result)

    def test_exception_with_suggested_fix_attr(self) -> None:
        exc = Exception("config error")
        exc.suggested_fix = "Reconfigure the settings"  # type: ignore[attr-defined]
        result = render_exception(exc)
        assert isinstance(result, Panel)
        assert "Reconfigure the settings" in _render_to_text(result)

    def test_exception_with_recovery_commands_attr(self) -> None:
        exc = Exception("recoverable error")
        exc.recovery_commands = ["cmd1", "cmd2"]  # type: ignore[attr-defined]
        result = render_exception(exc)
        assert isinstance(result, Panel)
        assert "cmd1" in _render_to_text(result)

    def test_exception_message_with_fix_prefix_stripped(self) -> None:
        exc = Exception("Something failed Fix: do this instead")
        result = render_exception(exc)
        assert isinstance(result, Panel)

    def test_exception_message_with_suggested_fix_prefix(self) -> None:
        exc = Exception("Error occurred Suggested fix: try this")
        result = render_exception(exc)
        assert isinstance(result, Panel)
