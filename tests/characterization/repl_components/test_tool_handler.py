"""Golden baseline tests for `tool_handler` behavior."""

from __future__ import annotations

from asyncio.exceptions import CancelledError
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import tunacode.cli.repl_components.tool_executor as tool_executor

TOOL_NAME = "read_file"
TOOL_ARGS: Dict[str, Any] = {"file_path": "example.py"}

# CLAUDE_ANCHOR[key=8f5a4d92] Golden baseline for tool_handler cancellation and handler creation


@pytest.mark.asyncio
async def test_tool_handler_raises_cancelled_error_when_operation_flagged() -> None:
    """Ensure tool handler fails fast when the session has been cancelled."""
    state_manager = MagicMock()
    state_manager.session = SimpleNamespace(operation_cancelled=True)

    part = SimpleNamespace(tool_name=TOOL_NAME, args=TOOL_ARGS)

    with (
        patch.object(tool_executor, "parse_args", autospec=True) as parse_args,
        patch.object(tool_executor, "ToolHandler", autospec=True) as tool_handler_cls,
    ):
        with pytest.raises(CancelledError):
            await tool_executor.tool_handler(part, state_manager)

        parse_args.assert_not_called()
        tool_handler_cls.assert_not_called()


@pytest.mark.asyncio
async def test_tool_handler_creates_handler_without_confirmation() -> None:
    """Verify handler instantiation path when confirmation dialog is skipped."""
    state_manager = MagicMock()
    state_manager.session = SimpleNamespace(
        operation_cancelled=False,
        is_streaming_active=False,
    )
    state_manager.tool_handler = None
    state_manager.set_tool_handler = MagicMock()

    part = SimpleNamespace(tool_name=TOOL_NAME, args=TOOL_ARGS)

    mock_handler = MagicMock()
    mock_handler.should_confirm.return_value = False
    mock_handler.is_tool_blocked_in_plan_mode.return_value = False

    async def run_in_terminal_stub(callback: Callable[[], bool]) -> bool:
        return bool(callback())

    with (
        patch.object(
            tool_executor, "ToolHandler", autospec=True, return_value=mock_handler
        ) as tool_handler_cls,
        patch.object(
            tool_executor, "parse_args", autospec=True, return_value=TOOL_ARGS
        ) as parse_args,
        patch.object(
            tool_executor, "run_in_terminal", new=AsyncMock(side_effect=run_in_terminal_stub)
        ) as run_terminal,
    ):
        await tool_executor.tool_handler(part, state_manager)

    tool_handler_cls.assert_called_once_with(state_manager)
    state_manager.set_tool_handler.assert_called_once_with(mock_handler)
    parse_args.assert_called_once_with(part.args)
    run_terminal.assert_awaited_once()
