"""Tool execution and parallelization functionality."""

import asyncio
import os
from collections.abc import Awaitable, Callable
from typing import Any

from tunacode.core.logging.logger import get_logger

logger = get_logger(__name__)

ToolCallback = Callable[[Any, Any], Awaitable[Any]]


async def execute_tools_parallel(
    tool_calls: list[tuple[Any, Any]], callback: ToolCallback
) -> list[Any]:
    """
    Execute multiple tool calls in parallel using asyncio.

    Args:
        tool_calls: List of (part, node) tuples
        callback: The tool callback function to execute

    Returns:
        List of results in the same order as input

    Raises:
        Exception: Re-raises the first exception encountered during tool execution
    """
    # Get max parallel from environment or default to CPU count
    max_parallel = int(os.environ.get("TUNACODE_MAX_PARALLEL", os.cpu_count() or 4))
    errors: list[Exception] = []

    async def execute_with_error_handling(part, node):
        tool_name = getattr(part, "tool_name", "<unknown>")
        try:
            return await callback(part, node)
        except Exception as e:
            logger.error(f"Error executing parallel tool {tool_name}: {e}", exc_info=True)
            errors.append(e)
            raise  # Re-raise to fail fast
        finally:
            logger.debug(
                "Parallel tool execution completed (success or failure): tool=%s",
                tool_name,
            )

    # If we have more tools than max_parallel, execute in batches
    if len(tool_calls) > max_parallel:
        results = []
        for i in range(0, len(tool_calls), max_parallel):
            batch = tool_calls[i : i + max_parallel]
            batch_tasks = [execute_with_error_handling(part, node) for part, node in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            results.extend(batch_results)
            # Check for errors after each batch - fail fast
            for result in batch_results:
                if isinstance(result, Exception):
                    raise result
        return results
    else:
        tasks = [execute_with_error_handling(part, node) for part, node in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Check for errors - fail fast, raise the first one
        for result in results:
            if isinstance(result, Exception):
                raise result
        return results
