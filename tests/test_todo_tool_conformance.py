"""Conformance tests for todo tools created via factory functions."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum

import pytest

from tunacode.core.state import StateManager
from tunacode.tools.todo import (
    create_todoclear_tool,
    create_todoread_tool,
    create_todowrite_tool,
)
from tunacode.tools.xml_helper import load_prompt_from_xml

EXPECTED_NO_PARAMS = 0
EXPECTED_SINGLE_PARAM = 1
FIRST_PARAM_INDEX = 0
MIN_DOCSTRING_LENGTH = 10
RETURN_TYPE_NAME = "str"
TODO_PARAM_NAME = "todos"


class TodoToolName(str, Enum):
    CLEAR = "todoclear"
    READ = "todoread"
    WRITE = "todowrite"


@dataclass(frozen=True)
class TodoToolSpec:
    name: str
    factory: Callable[[StateManager], Callable[..., Awaitable[str]]]
    expected_param_count: int
    expected_first_param_name: str | None


@dataclass(frozen=True)
class TodoTool:
    name: str
    func: Callable[..., Awaitable[str]]
    expected_param_count: int
    expected_first_param_name: str | None


def _build_todo_tool_specs() -> tuple[TodoToolSpec, ...]:
    return (
        TodoToolSpec(
            name=TodoToolName.WRITE.value,
            factory=create_todowrite_tool,
            expected_param_count=EXPECTED_SINGLE_PARAM,
            expected_first_param_name=TODO_PARAM_NAME,
        ),
        TodoToolSpec(
            name=TodoToolName.READ.value,
            factory=create_todoread_tool,
            expected_param_count=EXPECTED_NO_PARAMS,
            expected_first_param_name=None,
        ),
        TodoToolSpec(
            name=TodoToolName.CLEAR.value,
            factory=create_todoclear_tool,
            expected_param_count=EXPECTED_NO_PARAMS,
            expected_first_param_name=None,
        ),
    )


def _create_todo_tools(
    state_manager: StateManager, specs: tuple[TodoToolSpec, ...]
) -> tuple[TodoTool, ...]:
    tools: list[TodoTool] = []
    for spec in specs:
        tool_func = spec.factory(state_manager)
        tools.append(
            TodoTool(
                name=spec.name,
                func=tool_func,
                expected_param_count=spec.expected_param_count,
                expected_first_param_name=spec.expected_first_param_name,
            )
        )
    return tuple(tools)


@pytest.fixture()
def state_manager() -> StateManager:
    return StateManager()


@pytest.fixture()
def todo_tools(state_manager: StateManager) -> tuple[TodoTool, ...]:
    specs = _build_todo_tool_specs()
    return _create_todo_tools(state_manager, specs)


def test_todo_tools_are_async(todo_tools: tuple[TodoTool, ...]) -> None:
    tools = todo_tools
    for tool in tools:
        assert inspect.iscoroutinefunction(tool.func), f"{tool.name} is not async"


def test_todo_tools_have_docstrings(todo_tools: tuple[TodoTool, ...]) -> None:
    for tool in todo_tools:
        xml_prompt = load_prompt_from_xml(tool.name)
        assert xml_prompt is not None, f"{tool.name} is missing an XML prompt"
        docstring = tool.func.__doc__
        assert docstring, f"{tool.name} has no docstring"
        matches_xml_prompt = docstring == xml_prompt
        assert matches_xml_prompt, f"{tool.name} docstring does not match XML prompt"
        assert len(docstring) > MIN_DOCSTRING_LENGTH, (
            f"{tool.name} docstring too short: {docstring!r}"
        )


def test_todo_tools_are_decorated(todo_tools: tuple[TodoTool, ...]) -> None:
    for tool in todo_tools:
        unwrapped = inspect.unwrap(tool.func)
        assert unwrapped is not tool.func, f"{tool.name} is not wrapped by a tool decorator"


def test_todo_tool_signatures(todo_tools: tuple[TodoTool, ...]) -> None:
    for tool in todo_tools:
        signature = inspect.signature(tool.func)
        params = list(signature.parameters.values())
        param_count = len(params)
        expected_param_count = tool.expected_param_count
        assert param_count == expected_param_count, (
            f"{tool.name} has {param_count} params, expected {expected_param_count}"
        )

        if expected_param_count == EXPECTED_SINGLE_PARAM:
            first_param = params[FIRST_PARAM_INDEX]
            expected_first_param_name = tool.expected_first_param_name
            assert first_param.name == expected_first_param_name, (
                f"{tool.name} first param is '{first_param.name}', "
                f"expected '{expected_first_param_name}'"
            )
            annotation = first_param.annotation
            assert annotation is not inspect.Parameter.empty, (
                f"{tool.name} parameter '{first_param.name}' is missing type annotation"
            )


def test_todo_tool_return_annotations(todo_tools: tuple[TodoTool, ...]) -> None:
    for tool in todo_tools:
        signature = inspect.signature(tool.func)
        return_annotation = signature.return_annotation
        assert return_annotation is not inspect.Parameter.empty, (
            f"{tool.name} missing return type annotation"
        )
        valid_return = return_annotation is str or RETURN_TYPE_NAME in str(return_annotation)
        assert valid_return, f"{tool.name} return annotation is {return_annotation}"
