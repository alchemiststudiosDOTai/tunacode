"""Tool decorators providing error handling.

This module provides decorators that wrap tool functions with:
- Consistent error handling (converts exceptions to ToolExecutionError)
- Logging of tool invocations
- File-specific error handling for file operations
- LSP diagnostic integration for file modifications
"""

import asyncio
import inspect
import logging
from collections.abc import Callable, Coroutine
from functools import wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar, overload

from pydantic_ai.exceptions import ModelRetry

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.exceptions import FileOperationError, ToolExecutionError
from tunacode.tools.xml_helper import load_prompt_from_xml
from tunacode.utils.config.user_configuration import load_config

P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger(__name__)

LSP_ORCHESTRATION_OVERHEAD_SECONDS = 1.0
LSP_DIAGNOSTICS_TIMEOUT_WARNING: str = "LSP diagnostics timed out for %s (no type errors shown)"

DEFAULT_LSP_CONFIG: dict[str, Any] = {
    "enabled": False,
    "timeout": 5.0,
    "max_diagnostics": 20,
}


def _merge_lsp_config(*configs: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for config in configs:
        merged.update(config)
    return merged


def _get_lsp_config() -> dict[str, Any]:
    """Get LSP configuration from user config (merged with defaults)."""
    default_settings = DEFAULT_USER_CONFIG.get("settings", {})
    default_lsp_config = default_settings.get("lsp", {})

    user_config = load_config() or {}
    user_settings = user_config.get("settings", {})
    user_lsp_config = user_settings.get("lsp", {})

    return _merge_lsp_config(DEFAULT_LSP_CONFIG, default_lsp_config, user_lsp_config)


async def _get_lsp_diagnostics(filepath: str) -> str:
    """Get LSP diagnostics for a file if LSP is enabled.

    Args:
        filepath: Path to the file to check

    Returns:
        Formatted diagnostics string or empty string
    """
    config = _get_lsp_config()
    if not config.get("enabled", False):
        return ""

    try:
        from tunacode.lsp import format_diagnostics, get_diagnostics

        timeout = config.get("timeout", 5.0)
        diagnostics = await asyncio.wait_for(
            get_diagnostics(Path(filepath), timeout=timeout),
            timeout=timeout + LSP_ORCHESTRATION_OVERHEAD_SECONDS,
        )
        return format_diagnostics(diagnostics)
    except TimeoutError:
        logger.warning(LSP_DIAGNOSTICS_TIMEOUT_WARNING, filepath)
        return ""
    except Exception as e:
        logger.debug("LSP diagnostics failed for %s: %s", filepath, e)
        return ""


def base_tool(
    func: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    """Wrap tool with error handling.

    Converts uncaught exceptions to ToolExecutionError while preserving
    ModelRetry and ToolExecutionError pass-through.

    Args:
        func: Async tool function to wrap

    Returns:
        Wrapped function with error handling
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        except ModelRetry:
            raise
        except ToolExecutionError:
            raise
        except FileOperationError:
            raise
        except Exception as e:
            raise ToolExecutionError(
                tool_name=func.__name__, message=str(e), original_error=e
            ) from e

    xml_prompt = load_prompt_from_xml(func.__name__)
    if xml_prompt:
        wrapper.__doc__ = xml_prompt

    wrapper.__signature__ = inspect.signature(func)  # type: ignore[attr-defined]

    return wrapper  # type: ignore[return-value]


@overload
def file_tool(
    func: Callable[..., Coroutine[Any, Any, str]],
) -> Callable[..., Coroutine[Any, Any, str]]: ...


@overload
def file_tool(
    *,
    writes: bool = False,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, str]]],
    Callable[..., Coroutine[Any, Any, str]],
]: ...


def file_tool(
    func: Callable[..., Coroutine[Any, Any, str]] | None = None,
    *,
    writes: bool = False,
) -> (
    Callable[..., Coroutine[Any, Any, str]]
    | Callable[
        [Callable[..., Coroutine[Any, Any, str]]],
        Callable[..., Coroutine[Any, Any, str]],
    ]
):
    """Wrap file tool with path-specific error handling and optional LSP diagnostics.

    Provides specialized handling for common file operation errors:
    - FileNotFoundError -> ModelRetry (allows LLM to correct path)
    - PermissionError -> FileOperationError
    - UnicodeDecodeError -> FileOperationError
    - IOError/OSError -> FileOperationError

    When writes=True, also fetches LSP diagnostics after successful file modification.

    Args:
        func: Async file tool function to wrap. First argument must be filepath.
        writes: If True, fetch LSP diagnostics after successful operation.

    Returns:
        Wrapped function with file-specific error handling

    Usage:
        @file_tool  # Read-only, no LSP
        async def read_file(filepath: str) -> str: ...

        @file_tool(writes=True)  # Write operation, LSP diagnostics enabled
        async def update_file(filepath: str, ...) -> str: ...
    """

    def decorator(
        fn: Callable[..., Coroutine[Any, Any, str]],
    ) -> Callable[..., Coroutine[Any, Any, str]]:
        @wraps(fn)
        async def wrapper(filepath: str, *args: Any, **kwargs: Any) -> str:
            try:
                result = await fn(filepath, *args, **kwargs)

                # Add LSP diagnostics for write operations
                if writes:
                    diagnostics_output = await _get_lsp_diagnostics(filepath)
                    if diagnostics_output:
                        diagnostics_first_result = f"{diagnostics_output}\n\n{result}"
                        result = diagnostics_first_result

                return result
            except FileNotFoundError as err:
                raise ModelRetry(f"File not found: {filepath}. Check the path.") from err
            except PermissionError as e:
                raise FileOperationError(
                    operation="access", path=filepath, message=str(e), original_error=e
                ) from e
            except UnicodeDecodeError as e:
                raise FileOperationError(
                    operation="decode", path=filepath, message=str(e), original_error=e
                ) from e
            except OSError as e:
                raise FileOperationError(
                    operation="read/write", path=filepath, message=str(e), original_error=e
                ) from e

        wrapper.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]

        return base_tool(wrapper)  # type: ignore[arg-type]

    # Handle both @file_tool and @file_tool(writes=True)
    if func is not None:
        return decorator(func)
    return decorator
