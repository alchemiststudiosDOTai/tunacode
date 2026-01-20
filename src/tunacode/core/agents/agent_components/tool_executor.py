"""Tool execution and parallelization functionality with automatic retry."""

import asyncio
import os
import random
import time
from typing import Any

from pydantic_ai import ModelRetry

from tunacode.constants import (
    TOOL_MAX_RETRIES,
    TOOL_RETRY_BASE_DELAY,
    TOOL_RETRY_MAX_DELAY,
)
from tunacode.core.logging import get_logger
from tunacode.exceptions import (
    ConfigurationError,
    FileOperationError,
    ToolExecutionError,
    UserAbortError,
    ValidationError,
)
from tunacode.types import ToolCallback

# Errors that should NOT be retried - they represent user intent or unrecoverable states
NON_RETRYABLE_ERRORS = (
    UserAbortError,
    ModelRetry,
    KeyboardInterrupt,
    SystemExit,
    ValidationError,
    ConfigurationError,
    ToolExecutionError,
    FileOperationError,
)


def _calculate_backoff(attempt: int) -> float:
    """Exponential backoff with jitter."""
    delay = min(TOOL_RETRY_BASE_DELAY * (2 ** (attempt - 1)), TOOL_RETRY_MAX_DELAY)
    jitter = random.uniform(0, delay * 0.1)  # nosec B311 - not for crypto
    return delay + jitter


async def execute_tools_parallel(
    tool_calls: list[tuple[Any, Any]], callback: ToolCallback
) -> list[Any]:
    """
    Execute multiple tool calls in parallel using asyncio with automatic retry.

    Each tool gets up to TOOL_MAX_RETRIES attempts before failing.
    Non-retryable errors (user abort, validation, etc.) propagate immediately.

    Args:
        tool_calls: List of (part, node) tuples
        callback: The tool callback function to execute

    Returns:
        List of results in the same order as input

    Raises:
        Exception: Re-raises after all retry attempts exhausted
    """
    logger = get_logger()
    max_parallel = int(os.environ.get("TUNACODE_MAX_PARALLEL", os.cpu_count() or 4))
    tool_count = len(tool_calls)
    logger.lifecycle(f"Tool execution start (count={tool_count}, max_parallel={max_parallel})")

    async def execute_with_retry(part, node):
        tool_name = getattr(part, "tool_name", "unknown")
        start = time.perf_counter()
        logger.lifecycle(f"Tool start (tool={tool_name})")

        for attempt in range(1, TOOL_MAX_RETRIES + 1):
            try:
                result = await callback(part, node)
                duration_ms = (time.perf_counter() - start) * 1000
                logger.tool(tool_name, "completed", duration_ms=duration_ms)
                return result
            except NON_RETRYABLE_ERRORS:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.tool(tool_name, "failed (non-retryable)", duration_ms=duration_ms)
                raise
            except Exception:
                if attempt == TOOL_MAX_RETRIES:
                    ms = (time.perf_counter() - start) * 1000
                    logger.tool(tool_name, f"failed ({attempt} attempts)", duration_ms=ms)
                    raise
                backoff = _calculate_backoff(attempt)
                logger.warning(f"{tool_name} retry {attempt}/{TOOL_MAX_RETRIES}")
                await asyncio.sleep(backoff)

        raise AssertionError("unreachable")

    # Execute in batches if we have more tools than max_parallel
    if len(tool_calls) > max_parallel:
        results: list[Any] = []
        for i in range(0, len(tool_calls), max_parallel):
            batch = tool_calls[i : i + max_parallel]
            batch_tasks = [execute_with_retry(part, node) for part, node in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            results.extend(batch_results)
            # Check for errors after each batch
            for result in batch_results:
                if isinstance(result, Exception):
                    raise result
    else:
        tasks = [execute_with_retry(part, node) for part, node in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Check for errors - raise the first one
        for result in results:
            if isinstance(result, Exception):
                raise result
    logger.lifecycle(f"Tool execution complete (count={tool_count})")
    return results
