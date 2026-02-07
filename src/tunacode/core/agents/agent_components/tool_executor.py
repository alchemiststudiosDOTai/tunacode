"""Tool execution and parallelization functionality with automatic retry."""

import asyncio
import os
import random
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai.messages import ToolCallPart
    from pydantic_ai.result import StreamedRunResult

from tunacode.constants import (
    TOOL_MAX_RETRIES,
    TOOL_RETRY_BASE_DELAY,
    TOOL_RETRY_MAX_DELAY,
)
from tunacode.exceptions import (
    ConfigurationError,
    FileOperationError,
    ToolExecutionError,
    ToolRetryError,
    UserAbortError,
    ValidationError,
)
from tunacode.types import ToolCallback

from tunacode.core.logging import get_logger

# Errors that should NOT be retried - they represent user intent or unrecoverable states
NON_RETRYABLE_ERRORS = (
    UserAbortError,
    ToolRetryError,
    KeyboardInterrupt,
    SystemExit,
    ValidationError,
    ConfigurationError,
    ToolExecutionError,
    FileOperationError,
)

ToolFailureCallback = Callable[["ToolCallPart", BaseException], None]


def _calculate_backoff(attempt: int) -> float:
    """Exponential backoff with jitter."""
    delay = min(TOOL_RETRY_BASE_DELAY * (2 ** (attempt - 1)), TOOL_RETRY_MAX_DELAY)
    jitter = random.uniform(0, delay * 0.1)  # nosec B311 - not for crypto
    return float(delay + jitter)


def _report_tool_failure(
    logger: Any,
    tool_name: str,
    start: float,
    error: BaseException,
    failure_cb: ToolFailureCallback | None,
    part: "ToolCallPart",
    status: str,
    detail: str,
) -> None:
    """Log a tool failure and invoke the optional failure callback."""
    duration_ms = (time.perf_counter() - start) * 1000
    logger.tool(tool_name, status, duration_ms=duration_ms)
    logger.lifecycle(detail)
    if failure_cb:
        failure_cb(part, error)


def _gather_results(gathered: list[None | BaseException]) -> list[None]:
    """Extract results from gather output, raising the first exception if any."""
    results: list[None] = []
    for result in gathered:
        if isinstance(result, BaseException):
            raise result
        results.append(result)
    return results


async def _execute_with_retry(
    part: "ToolCallPart",
    node: "StreamedRunResult[None, str]",
    callback: ToolCallback,
    failure_cb: ToolFailureCallback | None,
) -> None:
    """Execute a single tool call with retry logic."""
    logger = get_logger()
    tool_name = getattr(part, "tool_name", "unknown")
    start = time.perf_counter()
    logger.lifecycle(f"Tool start (tool={tool_name})")

    for attempt in range(1, TOOL_MAX_RETRIES + 1):
        try:
            await callback(part, node)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.tool(tool_name, "completed", duration_ms=duration_ms)
            return
        except NON_RETRYABLE_ERRORS as e:
            err_type = type(e).__name__
            _report_tool_failure(
                logger,
                tool_name,
                start,
                e,
                failure_cb,
                part,
                "failed (non-retryable)",
                f"Error: {tool_name} failed - {err_type}: {e}",
            )
            raise
        except Exception as e:
            if attempt == TOOL_MAX_RETRIES:
                err_type = type(e).__name__
                _report_tool_failure(
                    logger,
                    tool_name,
                    start,
                    e,
                    failure_cb,
                    part,
                    f"failed ({attempt} attempts)",
                    f"Error: {tool_name} failed after {attempt} retries - {err_type}: {e}",
                )
                raise
            backoff = _calculate_backoff(attempt)
            logger.lifecycle(
                f"Retry: {tool_name} attempt {attempt}/{TOOL_MAX_RETRIES} ({type(e).__name__})"
            )
            await asyncio.sleep(backoff)


async def execute_tools_parallel(
    tool_calls: list[tuple["ToolCallPart", "StreamedRunResult[None, str]"]],
    callback: ToolCallback,
    tool_failure_callback: ToolFailureCallback | None = None,
) -> list[None]:
    """
    Execute multiple tool calls in parallel using asyncio with automatic retry.

    Each tool gets up to TOOL_MAX_RETRIES attempts before failing.
    Non-retryable errors (user abort, validation, etc.) propagate immediately.

    Args:
        tool_calls: List of (part, node) tuples
        callback: The tool callback function to execute
        tool_failure_callback: Optional callback invoked after a tool ultimately fails

    Returns:
        List of results in the same order as input

    Raises:
        Exception: Re-raises after all retry attempts exhausted
    """
    logger = get_logger()
    max_parallel = int(os.environ.get("TUNACODE_MAX_PARALLEL", os.cpu_count() or 4))
    tool_count = len(tool_calls)
    logger.lifecycle(f"Tool execution start (count={tool_count}, max_parallel={max_parallel})")

    # Execute in batches if we have more tools than max_parallel
    results: list[None] = []
    if len(tool_calls) > max_parallel:
        for i in range(0, len(tool_calls), max_parallel):
            batch = tool_calls[i : i + max_parallel]
            batch_tasks = [
                _execute_with_retry(part, node, callback, tool_failure_callback)
                for part, node in batch
            ]
            batch_gathered = await asyncio.gather(*batch_tasks, return_exceptions=True)
            results.extend(_gather_results(batch_gathered))
    else:
        tasks = [
            _execute_with_retry(part, node, callback, tool_failure_callback)
            for part, node in tool_calls
        ]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        results = _gather_results(gathered)

    logger.lifecycle(f"Tool execution complete (count={tool_count})")
    return results
