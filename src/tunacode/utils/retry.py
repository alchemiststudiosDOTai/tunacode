"""Retry utilities for handling transient failures."""

import asyncio
import functools
import json
import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def retry_on_json_error(
    max_retries: int = 10,
    base_delay: float = 0.1,
    max_delay: float = 5.0,
    logger_name: Optional[str] = None,
) -> Callable:
    """Decorator to retry function calls that fail with JSON parsing errors.

    Implements exponential backoff with configurable parameters.

    Args:
        max_retries: Maximum number of retry attempts (default: 10)
        base_delay: Initial delay between retries in seconds (default: 0.1)
        max_delay: Maximum delay between retries in seconds (default: 5.0)
        logger_name: Logger name for retry logging (default: uses module logger)

    Returns:
        Decorated function that retries on JSONDecodeError
    """
    retry_logger = logging.getLogger(logger_name) if logger_name else logger

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except json.JSONDecodeError as e:
                    last_exception = e

                    if attempt == max_retries:
                        # Final attempt failed
                        retry_logger.error(f"JSON parsing failed after {max_retries} retries: {e}")
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2**attempt), max_delay)

                    retry_logger.warning(
                        f"JSON parsing error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    await asyncio.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except json.JSONDecodeError as e:
                    last_exception = e

                    if attempt == max_retries:
                        # Final attempt failed
                        retry_logger.error(f"JSON parsing failed after {max_retries} retries: {e}")
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2**attempt), max_delay)

                    retry_logger.warning(
                        f"JSON parsing error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    time.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def retry_json_parse(
    json_string: str,
    max_retries: int = 10,
    base_delay: float = 0.1,
    max_delay: float = 5.0,
) -> Any:
    """Parse JSON with automatic retry on failure.

    Args:
        json_string: JSON string to parse
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds

    Returns:
        Parsed JSON object

    Raises:
        json.JSONDecodeError: If parsing fails after all retries
    """

    @retry_on_json_error(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
    )
    def _parse():
        return json.loads(json_string)

    return _parse()


async def retry_json_parse_async(
    json_string: str,
    max_retries: int = 10,
    base_delay: float = 0.1,
    max_delay: float = 5.0,
) -> Any:
    """Asynchronously parse JSON with automatic retry on failure.

    Args:
        json_string: JSON string to parse
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds

    Returns:
        Parsed JSON object

    Raises:
        json.JSONDecodeError: If parsing fails after all retries
    """

    @retry_on_json_error(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
    )
    async def _parse():
        return json.loads(json_string)

    return await _parse()
