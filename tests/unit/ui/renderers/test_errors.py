"""Tests for error panel rendering pure functions.

Source: src/tunacode/ui/renderers/errors.py
"""

from __future__ import annotations

from rich.panel import Panel

from tunacode.ui.renderers.errors import (
    _extract_exception_context,
    render_catastrophic_error,
    render_user_abort,
    render_validation_error,
)

# ---------------------------------------------------------------------------
# Custom exception classes for testing _extract_exception_context
# ---------------------------------------------------------------------------


class ToolException(Exception):
    """Exception with a tool_name attribute."""

    def __init__(self, message: str, tool_name: str) -> None:
        super().__init__(message)
        self.tool_name = tool_name


class PathException(Exception):
    """Exception with a path attribute."""

    def __init__(self, message: str, path: str) -> None:
        super().__init__(message)
        self.path = path


class OperationException(Exception):
    """Exception with an operation attribute."""

    def __init__(self, message: str, operation: str) -> None:
        super().__init__(message)
        self.operation = operation


class MultiAttrException(Exception):
    """Exception with multiple recognized attributes."""

    def __init__(
        self,
        message: str,
        tool_name: str,
        path: str,
    ) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.path = path


class NoneAttrException(Exception):
    """Exception with a recognized attribute set to None."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.tool_name: str | None = None


# ---------------------------------------------------------------------------
# _extract_exception_context
# ---------------------------------------------------------------------------


class TestExtractExceptionContext:
    """Extract labelled context dict from exception attributes."""

    def test_tool_name_attr(self) -> None:
        exc = ToolException("failed", tool_name="bash")
        context = _extract_exception_context(exc)
        assert context == {"Tool": "bash"}

    def test_path_attr(self) -> None:
        exc = PathException("not found", path="/tmp/missing.py")
        context = _extract_exception_context(exc)
        assert context == {"Path": "/tmp/missing.py"}

    def test_operation_attr(self) -> None:
        exc = OperationException("timeout", operation="read")
        context = _extract_exception_context(exc)
        assert context == {"Operation": "read"}

    def test_no_matching_attrs_returns_empty(self) -> None:
        exc = Exception("plain error")
        context = _extract_exception_context(exc)
        assert context == {}

    def test_none_attr_value_excluded(self) -> None:
        exc = NoneAttrException("oops")
        context = _extract_exception_context(exc)
        assert "Tool" not in context
        assert context == {}

    def test_multiple_attrs_all_included(self) -> None:
        exc = MultiAttrException("fail", tool_name="grep", path="/src/main.py")
        context = _extract_exception_context(exc)
        assert context == {"Tool": "grep", "Path": "/src/main.py"}


# ---------------------------------------------------------------------------
# render_validation_error
# ---------------------------------------------------------------------------


class TestRenderValidationError:
    """render_validation_error returns a Panel for field validation failures."""

    def test_returns_panel(self) -> None:
        result = render_validation_error("model", "invalid model name")
        assert isinstance(result, Panel)

    def test_without_valid_examples(self) -> None:
        result = render_validation_error("timeout", "must be positive")
        assert isinstance(result, Panel)

    def test_with_valid_examples(self) -> None:
        result = render_validation_error(
            "model",
            "unknown model",
            valid_examples=["gpt-4", "claude-3", "gemini"],
        )
        assert isinstance(result, Panel)

    def test_valid_examples_truncated_to_three(self) -> None:
        """The implementation joins up to 3 examples, so 4+ should still work."""
        result = render_validation_error(
            "color",
            "invalid color",
            valid_examples=["red", "green", "blue", "yellow"],
        )
        assert isinstance(result, Panel)


# ---------------------------------------------------------------------------
# render_user_abort
# ---------------------------------------------------------------------------


class TestRenderUserAbort:
    """render_user_abort returns a Panel with cancellation info."""

    def test_returns_panel(self) -> None:
        result = render_user_abort()
        assert isinstance(result, Panel)

    def test_title_contains_operation_cancelled(self) -> None:
        result = render_user_abort()
        assert isinstance(result, Panel)
        # The Panel title is set to "Operation Cancelled" via ErrorDisplayData.error_type
        title = result.title
        assert title is not None
        assert "Operation Cancelled" in str(title)


# ---------------------------------------------------------------------------
# render_catastrophic_error
# ---------------------------------------------------------------------------


class TestRenderCatastrophicError:
    """render_catastrophic_error returns a Panel for unexpected failures."""

    def test_returns_panel(self) -> None:
        exc = RuntimeError("something broke")
        result = render_catastrophic_error(exc)
        assert isinstance(result, Panel)

    def test_with_empty_message(self) -> None:
        exc = RuntimeError("")
        result = render_catastrophic_error(exc)
        assert isinstance(result, Panel)

    def test_with_long_message_truncated(self) -> None:
        exc = RuntimeError("x" * 500)
        result = render_catastrophic_error(exc)
        assert isinstance(result, Panel)

    def test_with_context_parameter(self) -> None:
        exc = ValueError("bad value")
        result = render_catastrophic_error(exc, context="during model call")
        assert isinstance(result, Panel)

    def test_title_contains_something_went_wrong(self) -> None:
        exc = RuntimeError("oops")
        result = render_catastrophic_error(exc)
        assert isinstance(result, Panel)
        title = result.title
        assert title is not None
        assert "Something Went Wrong" in str(title)
