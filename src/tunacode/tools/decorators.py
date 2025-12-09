"""Tool decorators providing error handling.

This module provides decorators that wrap tool functions with:
- Consistent error handling (converts exceptions to ToolExecutionError)
- Logging of tool invocations
- File-specific error handling for file operations
"""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from pydantic_ai.exceptions import ModelRetry

from tunacode.exceptions import FileOperationError, ToolExecutionError
from tunacode.tools.xml_helper import load_prompt_from_xml

P = ParamSpec("P")
R = TypeVar("R")


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

    return wrapper  # type: ignore[return-value]


def file_tool(
    func: Callable[..., Coroutine[Any, Any, R]],
) -> Callable[..., Coroutine[Any, Any, R]]:
    """Wrap file tool with path-specific error handling.

    Provides specialized handling for common file operation errors:
    - FileNotFoundError -> ModelRetry (allows LLM to correct path)
    - PermissionError -> FileOperationError
    - UnicodeDecodeError -> FileOperationError
    - IOError/OSError -> FileOperationError

    Args:
        func: Async file tool function to wrap. First argument must be filepath.

    Returns:
        Wrapped function with file-specific error handling
    """

    @wraps(func)
    async def wrapper(filepath: str, *args: Any, **kwargs: Any) -> R:
        try:
            return await func(filepath, *args, **kwargs)
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

    return base_tool(wrapper)  # type: ignore[arg-type]
