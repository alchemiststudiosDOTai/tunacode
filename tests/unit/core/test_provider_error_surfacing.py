"""Tests that provider API errors are surfaced instead of silently swallowed."""

from __future__ import annotations

import pytest

from tunacode.exceptions import AgentError, ContextOverflowError, ToolExecutionError

from tunacode.core.agents.helpers import coerce_error_text, is_context_overflow_error


def test_non_overflow_error_is_not_context_overflow() -> None:
    error_text = "invalid api key"
    assert not is_context_overflow_error(error_text)


def test_coerce_error_text_returns_string() -> None:
    assert coerce_error_text("some error") == "some error"


def test_coerce_error_text_returns_empty_for_none() -> None:
    assert coerce_error_text(None) == ""


def test_agent_error_carries_message() -> None:
    with pytest.raises(AgentError, match="invalid api key"):
        raise AgentError("invalid api key")


def test_agent_error_is_in_error_severity_map() -> None:
    from tunacode.ui.renderers.errors import ERROR_SEVERITY_MAP

    assert "AgentError" in ERROR_SEVERITY_MAP
    assert ERROR_SEVERITY_MAP["AgentError"] == "error"


def test_agent_error_renders_via_render_exception() -> None:
    from rich.console import Console

    from tunacode.ui.renderers.errors import render_exception

    exc = AgentError("minimax returned: unauthorized")
    content, meta = render_exception(exc)

    assert meta.css_class == "error-panel"

    console = Console(record=True, width=120)
    console.print(content)
    rendered = console.export_text()
    assert "unauthorized" in rendered


def test_render_exception_surfaces_tool_execution_metadata() -> None:
    from rich.console import Console

    from tunacode.ui.renderers.errors import render_exception

    exc = ToolExecutionError(
        tool_name="formatter",
        message="tool failed",
        suggested_fix="Use valid arguments",
        recovery_commands=["tunacode --retry"],
    )

    content, _meta = render_exception(exc)

    console = Console(record=True, width=120)
    console.print(content)
    rendered = console.export_text()
    assert "formatter" in rendered
    assert "Use valid arguments" in rendered
    assert "tunacode --retry" in rendered


def test_render_exception_context_overflow_includes_model_context() -> None:
    from rich.console import Console

    from tunacode.ui.renderers.errors import render_exception

    exc = ContextOverflowError(
        estimated_tokens=250_000,
        max_tokens=200_000,
        model="openrouter:openai/gpt-4.1",
    )

    content, _meta = render_exception(exc)

    console = Console(record=True, width=120)
    console.print(content)
    rendered = console.export_text()
    assert "openrouter:openai/gpt-4.1" in rendered
    assert "Compact the session or reduce context size before retrying." in rendered
