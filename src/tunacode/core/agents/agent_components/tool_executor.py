"""Tool execution and parallelization functionality."""

import asyncio
import os
from typing import Any, Awaitable, Callable, List, Tuple

from tunacode.core.logging.logger import get_logger

logger = get_logger(__name__)

ToolCallback = Callable[[Any, Any], Awaitable[Any]]


async def execute_tools_parallel(
    tool_calls: List[Tuple[Any, Any]], callback: ToolCallback, return_exceptions: bool = True
) -> List[Any]:
    """
    Execute multiple tool calls in parallel using asyncio.

    Args:
        tool_calls: List of (part, node) tuples
        callback: The tool callback function to execute
        return_exceptions: Whether to return exceptions or raise them

    Returns:
        List of results in the same order as input, with exceptions for failed calls
    """
    # Get max parallel from environment or default to CPU count
    max_parallel = int(os.environ.get("TUNACODE_MAX_PARALLEL", os.cpu_count() or 4))

    async def execute_with_error_handling(part, node):
        try:
            return await callback(part, node)
        except Exception as e:
            logger.error(f"Error executing parallel tool: {e}", exc_info=True)
            return e
        finally:
            # Tool execution completed - resource cleanup handled by BaseTool.execute()
            # Each tool's cleanup() method is called automatically in its execute()
            # finally block. This ensures resources (file handles, connections,
            # processes) are freed regardless of success or failure.
            tool_name = getattr(part, "tool_name", "<unknown>")
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
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=return_exceptions)
            results.extend(batch_results)
        return results
    else:
        tasks = [execute_with_error_handling(part, node) for part, node in tool_calls]
        return await asyncio.gather(*tasks, return_exceptions=return_exceptions)
