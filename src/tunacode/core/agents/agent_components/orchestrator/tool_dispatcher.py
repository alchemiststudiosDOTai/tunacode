"""Tool call collection, registration, and execution.

Responsibilities:
  1. Collect tool calls from response parts (structured or fallback)
  2. Register/normalize them in the tool registry
  3. Execute them in parallel with failure tracking

Does NOT own state transitions — the orchestrator drives those.
"""

import time
from dataclasses import dataclass
from typing import Any

from tunacode.types.callbacks import ToolCallback, ToolStartCallback

from tunacode.core.logging import get_logger
from tunacode.core.types import StateManagerProtocol

from . import _tool_dispatcher_collection as _collection
from . import _tool_dispatcher_constants as _constants
from . import _tool_dispatcher_execution as _execution
from . import _tool_dispatcher_logging as _logging
from . import _tool_dispatcher_names as _names
from . import _tool_dispatcher_registry as _registry

PART_KIND_TEXT = _constants.PART_KIND_TEXT
PART_KIND_TOOL_CALL = _constants.PART_KIND_TOOL_CALL
UNKNOWN_TOOL_NAME = _constants.UNKNOWN_TOOL_NAME

TEXT_PART_JOINER = _constants.TEXT_PART_JOINER
TOOL_NAME_JOINER = _constants.TOOL_NAME_JOINER
TOOL_NAME_SUFFIX = _constants.TOOL_NAME_SUFFIX

TOOL_BATCH_PREVIEW_COUNT = _constants.TOOL_BATCH_PREVIEW_COUNT
TOOL_NAMES_DISPLAY_LIMIT = _constants.TOOL_NAMES_DISPLAY_LIMIT

INVALID_TOOL_NAME_CHARS = _constants.INVALID_TOOL_NAME_CHARS
MAX_TOOL_NAME_LENGTH = _constants.MAX_TOOL_NAME_LENGTH

DEBUG_PREVIEW_MAX_LENGTH = _constants.DEBUG_PREVIEW_MAX_LENGTH
MS_PER_SECOND = _constants.MS_PER_SECOND

TOOL_FAILURE_TEMPLATE = _constants.TOOL_FAILURE_TEMPLATE

normalize_tool_args = _registry.normalize_tool_args
record_tool_call_args = _registry.record_tool_call_args
consume_tool_call_args = _registry.consume_tool_call_args

_is_suspicious_tool_name = _names._is_suspicious_tool_name
_normalize_tool_name = _names._normalize_tool_name

_collect_structured_tool_calls = _collection._collect_structured_tool_calls
_collect_fallback_tool_calls = _collection._collect_fallback_tool_calls

_execute_tool_batch = _execution._execute_tool_batch
_log_dispatch_summary = _logging._log_dispatch_summary


def has_tool_calls(parts: list[Any]) -> bool:
    """Check for structured tool call parts."""
    return any(getattr(part, "part_kind", None) == PART_KIND_TOOL_CALL for part in parts)


@dataclass(frozen=True, slots=True)
class ToolDispatchResult:
    """Summary of tool dispatch work."""

    has_tool_calls: bool
    used_fallback: bool


async def dispatch_tools(
    parts: list[Any],
    node: Any,
    state_manager: StateManagerProtocol,
    tool_callback: ToolCallback | None,
    tool_start_callback: ToolStartCallback | None,
    response_state_transition: Any | None = None,
) -> ToolDispatchResult:
    """Collect, register, and execute tool calls from response parts."""
    logger = get_logger()
    dispatch_start = time.perf_counter()

    records = await _collect_structured_tool_calls(parts, state_manager)

    used_fallback = False
    if not records and tool_callback:
        fallback_records = await _collect_fallback_tool_calls(parts, state_manager)
        if fallback_records:
            used_fallback = True
            records = fallback_records
            logger.lifecycle(f"Fallback tool parsing used (count={len(records)})")

    has_tools = bool(records)
    if has_tools and response_state_transition:
        response_state_transition()

    if records and tool_callback:
        await _execute_tool_batch(
            records,
            node,
            state_manager,
            tool_callback,
            tool_start_callback,
        )

    elapsed_ms = (time.perf_counter() - dispatch_start) * MS_PER_SECOND
    _log_dispatch_summary(records, elapsed_ms)

    return ToolDispatchResult(has_tool_calls=has_tools, used_fallback=used_fallback)
