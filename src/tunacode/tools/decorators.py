"""Tool decorators and adapters.

This module provides:

- Decorators that wrap tool functions with consistent error handling.
- XML-prompt injection (tool docstrings) for LLM tool descriptions.
- Adapters for exposing TunaCode tools as tinyAgent ``AgentTool`` objects.

Important migration note:

Historically, TunaCode tools raised ``ToolRetryError`` which the decorator converted to
``pydantic_ai.ModelRetry``. During the tinyAgent migration, the tool layer no longer
depends on pydantic-ai.

``ToolRetryError`` now propagates to the agent loop, which can decide how to
surface the hint to the model.
"""

from __future__ import annotations

import asyncio
import inspect
import types
import typing
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast, get_args, get_origin

from tunacode.exceptions import (
    FileOperationError,
    ToolExecutionError,
    ToolRetryError,
    UserAbortError,
)

from tunacode.tools.xml_helper import load_prompt_from_xml

if TYPE_CHECKING:
    from tinyagent import AgentTool

P = ParamSpec("P")
R = TypeVar("R")


def base_tool(
    func: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    """Wrap an async tool with consistent error handling.

    - ``ToolRetryError`` pass-through (signals that the model should try again).
    - ``ToolExecutionError`` pass-through.
    - ``FileOperationError`` pass-through.
    - Any other exception is wrapped into ``ToolExecutionError``.

    The wrapper also attempts to load an XML prompt for the tool name and, if
    present, replaces the function docstring.
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        except (ToolRetryError, ToolExecutionError, FileOperationError):
            raise
        except Exception as e:  # noqa: BLE001
            raise ToolExecutionError(
                tool_name=func.__name__,
                message=str(e),
                original_error=e,
            ) from e

    xml_prompt = load_prompt_from_xml(func.__name__)
    if xml_prompt:
        wrapper.__doc__ = xml_prompt

    # Preserve original signature for frameworks that introspect it.
    wrapper.__signature__ = inspect.signature(func)  # type: ignore[attr-defined]

    return wrapper  # type: ignore[return-value]


def file_tool(
    func: Callable[..., Coroutine[Any, Any, str]],
) -> Callable[..., Coroutine[Any, Any, str]]:
    """Wrap a file tool with path-specific error handling.

    Specialized handling for common file operation errors:

    - ``FileNotFoundError`` -> ``ToolRetryError`` (allows the model to correct the path)
    - ``PermissionError`` -> ``FileOperationError``
    - ``UnicodeDecodeError`` -> ``FileOperationError``
    - ``OSError`` -> ``FileOperationError``

    The resulting wrapper is also passed through :func:`base_tool`.

    Usage:
        @file_tool
        async def read_file(filepath: str) -> str: ...
    """

    @wraps(func)
    async def wrapper(filepath: str, *args: Any, **kwargs: Any) -> str:
        try:
            return await func(filepath, *args, **kwargs)
        except FileNotFoundError as err:
            raise ToolRetryError(f"File not found: {filepath}. Check the path.") from err
        except PermissionError as e:
            raise FileOperationError(
                operation="access",
                path=filepath,
                message=str(e),
                original_error=e,
            ) from e
        except UnicodeDecodeError as e:
            raise FileOperationError(
                operation="decode",
                path=filepath,
                message=str(e),
                original_error=e,
            ) from e
        except OSError as e:
            raise FileOperationError(
                operation="read/write",
                path=filepath,
                message=str(e),
                original_error=e,
            ) from e

    wrapper.__signature__ = inspect.signature(func)  # type: ignore[attr-defined]

    return base_tool(wrapper)  # type: ignore[arg-type]


def to_tinyagent_tool(
    func: Callable[..., Coroutine[Any, Any, Any]],
    *,
    name: str | None = None,
    label: str | None = None,
) -> AgentTool:
    """Convert a TunaCode async tool function to a tinyAgent ``AgentTool``.

    tinyAgent expects an ``AgentTool`` with an ``execute`` coroutine function with
    the signature:

        execute(tool_call_id, args, signal, on_update)

    Args:
        func: The async tool function (typically decorated with :func:`base_tool` or
            :func:`file_tool`).
        name: Optional override for the tool name (defaults to ``func.__name__``).
        label: Optional human label (defaults to ``name``).

    Returns:
        A tinyAgent ``AgentTool``.
    """

    from tinyagent import AgentTool, AgentToolResult

    tool_name = name or func.__name__
    tool_label = label or tool_name

    sig = inspect.signature(func)
    parameters_schema = _build_openai_parameters_schema(func)
    description = inspect.getdoc(func) or ""

    async def execute(
        tool_call_id: str,
        args: dict[str, Any],
        signal: asyncio.Event | None,
        on_update: Callable[[AgentToolResult], None],
    ) -> AgentToolResult:
        _ = tool_call_id
        _ = on_update

        if signal is not None and signal.is_set():
            raise UserAbortError(f"Tool execution aborted: {tool_name}")

        if not isinstance(args, dict):
            raise ToolRetryError(f"Tool arguments must be an object, got {type(args).__name__}")

        try:
            bound = sig.bind(**args)
            bound.apply_defaults()
        except TypeError as exc:
            raise ToolRetryError(
                f"Invalid arguments for tool '{tool_name}': {exc}. "
                f"Expected schema: {parameters_schema}"
            ) from exc

        result = await func(**cast(dict[str, Any], bound.arguments))

        if isinstance(result, AgentToolResult):
            return result
        if result is None:
            return AgentToolResult(content=[], details={})

        # Tools in this codebase typically return ``str``.
        return AgentToolResult(content=[{"type": "text", "text": str(result)}], details={})

    return AgentTool(
        name=tool_name,
        label=tool_label,
        description=description,
        parameters=parameters_schema,
        execute=execute,
    )


def _build_openai_parameters_schema(func: Callable[..., object]) -> dict[str, object]:
    """Build a minimal OpenAI-function JSON schema from a function signature."""

    sig = inspect.signature(func)

    properties: dict[str, object] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in {"self", "cls"}:
            # Reason: allow instance/class methods in future without breaking schema.
            continue

        if param.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
            raise ValueError(
                f"Tool '{func.__name__}' uses variadic parameters which are unsupported"
            )

        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            raise ValueError(
                f"Tool '{func.__name__}' has positional-only parameter '{param_name}', unsupported"
            )

        annotation = param.annotation
        schema = _python_type_to_json_schema(annotation)

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

        properties[param_name] = schema

    parameters: dict[str, object] = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required
    return parameters


_PRIMITIVE_JSON_SCHEMAS: dict[object, dict[str, object]] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
}


def _schema_for_list_args(args: tuple[object, ...]) -> dict[str, object]:
    if len(args) != 1:
        return {"type": "array"}
    return {"type": "array", "items": _python_type_to_json_schema(args[0])}


def _schema_for_dict_args(args: tuple[object, ...]) -> dict[str, object]:
    schema: dict[str, object] = {"type": "object"}
    if len(args) != 2:
        return schema

    key_t, value_t = args
    if key_t is not str:
        return schema

    additional = _python_type_to_json_schema(value_t)
    if additional:
        schema["additionalProperties"] = additional
    return schema


def _schema_for_union_args(args: tuple[object, ...]) -> dict[str, object]:
    non_none = [a for a in args if a is not type(None)]  # noqa: E721
    if len(non_none) == 1:
        return _python_type_to_json_schema(non_none[0])
    return {"anyOf": [_python_type_to_json_schema(a) for a in non_none]}


def _schema_for_literal_args(args: tuple[object, ...]) -> dict[str, object]:
    literals = list(args)
    schema: dict[str, object] = {"enum": literals}
    if literals and all(isinstance(v, str) for v in literals):
        schema["type"] = "string"
    return schema


def _python_type_to_json_schema(annotation: object) -> dict[str, object]:
    """Best-effort conversion of a Python type annotation to JSON schema.

    We intentionally keep this conservative: if we don't recognize a type, we
    return an empty schema so the provider still accepts the tool.
    """

    if annotation in (inspect.Parameter.empty, Any):
        return {}

    if annotation in (None, type(None)):  # noqa: E721
        return {"type": "null"}

    primitive = _PRIMITIVE_JSON_SCHEMAS.get(annotation)
    if primitive is not None:
        return dict(primitive)

    origin = get_origin(annotation)
    if origin is None:
        return {}

    args = get_args(annotation)

    if origin is list:
        return _schema_for_list_args(args)

    if origin is dict:
        return _schema_for_dict_args(args)

    if origin in (typing.Union, types.UnionType):
        return _schema_for_union_args(args)

    if origin is typing.Literal:
        return _schema_for_literal_args(args)

    return {}
