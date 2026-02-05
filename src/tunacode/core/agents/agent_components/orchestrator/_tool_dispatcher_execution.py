"""Tool execution helpers for tool_dispatcher."""

from typing import Any

from tunacode.types import ToolArgs
from tunacode.types.callbacks import ToolCallback, ToolStartCallback

from tunacode.core.types import StateManagerProtocol

from ._tool_dispatcher_constants import (
    TOOL_BATCH_PREVIEW_COUNT,
    TOOL_NAME_JOINER,
    TOOL_NAME_SUFFIX,
    UNKNOWN_TOOL_NAME,
)
from ._tool_dispatcher_registry import _mark_tool_calls_running, _record_tool_failure


async def _execute_tool_batch(
    records: list[tuple[Any, ToolArgs]],
    node: Any,
    state_manager: StateManagerProtocol,
    tool_callback: ToolCallback,
    tool_start_callback: ToolStartCallback | None,
) -> None:
    """Mark tools running, notify start callback, execute in parallel."""
    from ..tool_executor import execute_tools_parallel

    tasks = [(part, node) for part, _args in records]
    _mark_tool_calls_running(state_manager, tasks)

    runtime = state_manager.session.runtime
    runtime.batch_counter += 1

    if tool_start_callback:
        preview_names = [
            getattr(part, "tool_name", UNKNOWN_TOOL_NAME)
            for part, _ in tasks[:TOOL_BATCH_PREVIEW_COUNT]
        ]
        suffix = TOOL_NAME_SUFFIX if len(tasks) > TOOL_BATCH_PREVIEW_COUNT else ""
        tool_start_callback(TOOL_NAME_JOINER.join(preview_names) + suffix)

    def tool_failure_callback(part: Any, error: BaseException) -> None:
        _record_tool_failure(state_manager, part, error)

    await execute_tools_parallel(
        tasks,
        tool_callback,
        tool_failure_callback=tool_failure_callback,
    )
