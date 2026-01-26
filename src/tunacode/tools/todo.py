"""Todo list tools for tracking task progress during complex operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic_ai.exceptions import ModelRetry

from tunacode.types import StateManagerProtocol, TodoItem, TodoStatus

from tunacode.tools.xml_helper import load_prompt_from_xml

# Heavily yoinked from https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/todo.ts
# and adapted for python.

TODO_FIELD_ACTIVE_FORM = "activeForm"
TODO_FIELD_ACTIVE_FORM_ALT = "active_form"
TODO_FIELD_CONTENT = "content"
TODO_FIELD_STATUS = "status"

TODO_STATUS_COMPLETED = "completed"
TODO_STATUS_IN_PROGRESS = "in_progress"
TODO_STATUS_PENDING = "pending"

MAX_IN_PROGRESS_TODOS = 1
NO_TODOS_MESSAGE = "No todos in list."
TODO_LIST_CLEARED_MESSAGE = "Todo list cleared."

# Valid status values
VALID_STATUSES = frozenset({TODO_STATUS_PENDING, TODO_STATUS_IN_PROGRESS, TODO_STATUS_COMPLETED})

# Status display symbols
STATUS_SYMBOLS = {
    TODO_STATUS_PENDING: "[ ]",
    TODO_STATUS_IN_PROGRESS: "[>]",
    TODO_STATUS_COMPLETED: "[x]",
}


def _validate_todo(todo: Any, index: int) -> TodoItem:
    """Validate a single todo item has required fields.

    Args:
        todo: The todo dictionary to validate.
        index: The index of the todo in the list (for error messages).

    Raises:
        ModelRetry: If validation fails.
    """
    if isinstance(todo, TodoItem):
        return todo

    if not isinstance(todo, dict):
        todo_type = type(todo).__name__
        raise ModelRetry(f"Todo at index {index} must be a dictionary, got {todo_type}")

    required_fields = (TODO_FIELD_CONTENT, TODO_FIELD_STATUS)
    missing = [f for f in required_fields if f not in todo]
    if missing:
        raise ModelRetry(f"Todo at index {index} missing required fields: {', '.join(missing)}")

    status = todo[TODO_FIELD_STATUS]
    if not isinstance(status, str) or not status:
        raise ModelRetry(f"Todo at index {index} must have non-empty string '{TODO_FIELD_STATUS}'")
    if status not in VALID_STATUSES:
        raise ModelRetry(
            f"Todo at index {index} has invalid status '{status}'. "
            f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )

    content = todo[TODO_FIELD_CONTENT]
    if not isinstance(content, str) or not content:
        raise ModelRetry(f"Todo at index {index} must have non-empty string '{TODO_FIELD_CONTENT}'")

    active_form = todo.get(TODO_FIELD_ACTIVE_FORM, todo.get(TODO_FIELD_ACTIVE_FORM_ALT, ""))
    if not isinstance(active_form, str) or not active_form:
        raise ModelRetry(
            f"Todo at index {index} must have non-empty string '{TODO_FIELD_ACTIVE_FORM}'"
        )

    status_enum = TodoStatus(status)
    return TodoItem(content=content, status=status_enum, active_form=active_form)


def _validate_todos(todos: Any) -> list[TodoItem]:
    if not isinstance(todos, list):
        raise ModelRetry(f"todos must be a list, got {type(todos).__name__}")

    validated = [_validate_todo(todo, index) for index, todo in enumerate(todos)]

    in_progress_count = sum(1 for todo in validated if todo.status == TodoStatus.IN_PROGRESS)
    if in_progress_count > MAX_IN_PROGRESS_TODOS:
        raise ModelRetry(
            f"Only {MAX_IN_PROGRESS_TODOS} todo may be '{TODO_STATUS_IN_PROGRESS}' at a time, "
            f"got {in_progress_count}"
        )

    return validated


def _format_todos(todos: list[TodoItem]) -> str:
    """Format todos for display output.

    Args:
        todos: List of todo dictionaries.

    Returns:
        Formatted string representation of the todo list.
    """
    if not todos:
        return NO_TODOS_MESSAGE

    lines = []
    for i, todo in enumerate(todos, 1):
        status_value = todo.status.value
        symbol = STATUS_SYMBOLS[status_value]
        content = todo.content
        active_form = todo.active_form

        if todo.status == TodoStatus.IN_PROGRESS:
            lines.append(f"{i}. {symbol} {content} ({active_form})")
        else:
            lines.append(f"{i}. {symbol} {content}")

    return "\n".join(lines)


def create_todowrite_tool(state_manager: StateManagerProtocol) -> Callable:
    # Heavily yoinked from https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/todo.ts
    # and adapted for python.
    """Factory to create a todowrite tool bound to a state manager.

    Args:
        state_manager: The state manager instance to use.

    Returns:
        An async function that implements the todowrite tool.
    """

    async def todowrite(todos: list[dict[str, Any]]) -> str:
        """Create or update the todo list for tracking task progress.

        Use this tool to manage and display tasks during complex multi-step operations.
        The entire todo list is replaced with each call.

        Args:
            todos: List of todo items. Each item must have:
                - content: Task description in imperative form (e.g., "Fix the bug")
                - status: One of "pending", "in_progress", or "completed"
                - activeForm: Present continuous form for display (e.g., "Fixing the bug")

        Returns:
            Formatted display of the updated todo list.
        """
        validated = _validate_todos(todos)

        state_manager.set_todos(validated)
        return _format_todos(validated)

    # Load prompt from XML if available
    prompt = load_prompt_from_xml("todowrite")
    if prompt:
        todowrite.__doc__ = prompt

    return todowrite


def create_todoread_tool(state_manager: StateManagerProtocol) -> Callable:
    # Heavily yoinked from https://github.com/sst/opencode/blob/dev/packages/opencode/src/tool/todo.ts
    # and adapted for python.
    """Factory to create a todoread tool bound to a state manager.

    Args:
        state_manager: The state manager instance to use.

    Returns:
        An async function that implements the todoread tool.
    """

    async def todoread() -> str:
        """Read the current todo list.

        Use this tool to check the current state of all tasks.

        Returns:
            Formatted display of the current todo list, or a message if empty.
        """
        todos = state_manager.get_todos()
        validated = _validate_todos(todos)
        return _format_todos(validated)

    # Load prompt from XML if available
    prompt = load_prompt_from_xml("todoread")
    if prompt:
        todoread.__doc__ = prompt

    return todoread


def create_todoclear_tool(state_manager: StateManagerProtocol) -> Callable:
    """Factory to create a todoclear tool bound to a state manager.

    Args:
        state_manager: The state manager instance to use.

    Returns:
        An async function that implements the todoclear tool.
    """

    async def todoclear() -> str:
        """Clear the entire todo list.

        Use this tool when starting fresh or when all tasks are complete.

        Returns:
            Confirmation message.
        """
        state_manager.clear_todos()
        return TODO_LIST_CLEARED_MESSAGE

    # Load prompt from XML if available
    prompt = load_prompt_from_xml("todoclear")
    if prompt:
        todoclear.__doc__ = prompt

    return todoclear
