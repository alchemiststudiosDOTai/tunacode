"""Todo management tool for agent integration.

This tool allows the AI agent to manage todo items during task execution.
It provides functionality for creating, updating, and tracking tasks.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import defusedxml.ElementTree as ET
from pydantic_ai.exceptions import ModelRetry

from tunacode.constants import (
    MAX_TODO_CONTENT_LENGTH,
    MAX_TODOS_PER_SESSION,
    TODO_PRIORITIES,
    TodoPriority,
    TodoStatus,
)
from tunacode.types import TodoItem, ToolResult, UILogger

from .base import BaseTool

logger = logging.getLogger(__name__)


class TodoTool(BaseTool):
    """Tool for managing todo items from the AI agent."""

    def _get_base_prompt(self) -> str:
        """Load and return the base prompt from XML file.

        Returns:
            str: The loaded prompt from XML or a default prompt
        """
        try:
            # Load prompt from XML file
            prompt_file = Path(__file__).parent / "prompts" / "todo_prompt.xml"
            if prompt_file.exists():
                tree = ET.parse(prompt_file)
                root = tree.getroot()
                description = root.find("description")
                if description is not None:
                    return description.text.strip()
        except Exception as e:
            logger.warning(f"Failed to load XML prompt for todo: {e}")

        # Fallback to default prompt
        return """Use this tool to create and manage a structured task list"""

    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get the parameters schema for todo tool.

        Returns:
            Dict containing the JSON schema for tool parameters
        """
        # Try to load from XML first
        try:
            prompt_file = Path(__file__).parent / "prompts" / "todo_prompt.xml"
            if prompt_file.exists():
                tree = ET.parse(prompt_file)
                root = tree.getroot()
                parameters = root.find("parameters")
                if parameters is not None:
                    schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
                    required_fields: List[str] = []

                    for param in parameters.findall("parameter"):
                        name = param.get("name")
                        required = param.get("required", "false").lower() == "true"
                        param_type = param.find("type")
                        description = param.find("description")

                        if name and param_type is not None:
                            prop = {
                                "type": param_type.text.strip(),
                                "description": description.text.strip()
                                if description is not None
                                else "",
                            }

                            # Handle array types and nested objects
                            if param_type.text.strip() == "array":
                                items = param.find("items")
                                if items is not None:
                                    item_type = items.find("type")
                                    if item_type is not None and item_type.text.strip() == "object":
                                        # Handle object items
                                        item_props = {}
                                        item_properties = items.find("properties")
                                        if item_properties is not None:
                                            for item_prop in item_properties.findall("property"):
                                                prop_name = item_prop.get("name")
                                                prop_type_elem = item_prop.find("type")
                                                if prop_name and prop_type_elem is not None:
                                                    item_props[prop_name] = {
                                                        "type": prop_type_elem.text.strip()
                                                    }
                                        prop["items"] = {"type": "object", "properties": item_props}
                                    else:
                                        prop["items"] = {"type": items.text.strip()}

                            schema["properties"][name] = prop
                            if required:
                                required_fields.append(name)

                    schema["required"] = required_fields
                    return schema
        except Exception as e:
            logger.warning(f"Failed to load parameters from XML for todo: {e}")

        # Fallback to hardcoded schema
        return {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "The updated todo list",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "content": {"type": "string"},
                            "status": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["todos"],
        }

    def __init__(self, state_manager, ui_logger: UILogger | None = None):
        """Initialize the todo tool.

        Args:
            state_manager: StateManager instance for accessing todos
            ui_logger: UI logger instance for displaying messages
        """
        super().__init__(ui_logger)
        self.state_manager = state_manager

    @property
    def tool_name(self) -> str:
        return "todo"

    async def _execute(
        self,
        action: Literal["add", "add_multiple", "update", "complete", "list", "remove"],
        content: Optional[Union[str, List[str]]] = None,
        todo_id: Optional[str] = None,
        status: Optional[Literal["pending", "in_progress", "completed"]] = None,
        priority: Optional[Literal["high", "medium", "low"]] = None,
        todos: Optional[List[dict]] = None,
    ) -> ToolResult:
        """Execute todo management actions.

        Args:
            action: The action to perform (add, add_multiple, update, complete, list, remove)
            content: Content for new todos or updates (can be string or list for add_multiple)
            todo_id: ID of existing todo for updates/completion
            status: Status to set for updates
            priority: Priority to set for new/updated todos
            todos: List of todo dictionaries for add_multiple action
                  (format: [{"content": "...", "priority": "..."}])

        Returns:
            str: Result message describing what was done

        Raises:
            ModelRetry: When invalid parameters are provided
        """
        if action == "add":
            if isinstance(content, list):
                raise ModelRetry("Use 'add_multiple' action for adding multiple todos")
            return await self._add_todo(content, priority)
        elif action == "add_multiple":
            return await self._add_multiple_todos(content, todos, priority)
        elif action == "update":
            if isinstance(content, list):
                raise ModelRetry("Cannot update with list content")
            return await self._update_todo(todo_id, status, priority, content)
        elif action == "complete":
            return await self._complete_todo(todo_id)
        elif action == "list":
            return await self._list_todos()
        elif action == "remove":
            return await self._remove_todo(todo_id)
        else:
            raise ModelRetry(
                f"Invalid action '{action}'. Must be one of: "
                "add, add_multiple, update, complete, list, remove"
            )

    async def _add_todo(self, content: Optional[str], priority: Optional[str]) -> ToolResult:
        """Add a new todo item."""
        if not content:
            raise ModelRetry("Content is required when adding a todo")

        # Validate content length
        if len(content) > MAX_TODO_CONTENT_LENGTH:
            raise ModelRetry(
                f"Todo content is too long. Maximum length is {MAX_TODO_CONTENT_LENGTH} characters"
            )

        # Check todo limit
        if len(self.state_manager.session.todos) >= MAX_TODOS_PER_SESSION:
            raise ModelRetry(
                f"Cannot add more todos. Maximum of {MAX_TODOS_PER_SESSION} "
                "todos allowed per session"
            )

        # Generate UUID for guaranteed uniqueness
        new_id = f"todo_{uuid.uuid4().hex[:8]}"

        # Default priority if not specified
        todo_priority = priority or TodoPriority.MEDIUM
        if todo_priority not in [p.value for p in TodoPriority]:
            raise ModelRetry(
                f"Invalid priority '{todo_priority}'. Must be one of: "
                f"{', '.join([p.value for p in TodoPriority])}"
            )

        new_todo = TodoItem(
            id=new_id,
            content=content,
            status=TodoStatus.PENDING,
            priority=todo_priority,
            created_at=datetime.now(),
        )

        self.state_manager.add_todo(new_todo)
        return f"Added todo {new_id}: {content} (priority: {todo_priority})"

    async def _add_multiple_todos(
        self,
        content: Optional[Union[str, List[str]]],
        todos: Optional[List[dict]],
        priority: Optional[str],
    ) -> ToolResult:
        """Add multiple todo items at once."""

        # Handle different input formats
        todos_to_add = []

        if todos:
            # Structured format: [{"content": "...", "priority": "..."}, ...]
            for todo_data in todos:
                if not isinstance(todo_data, dict) or "content" not in todo_data:
                    raise ModelRetry("Each todo must be a dict with 'content' field")
                todo_content = todo_data["content"]
                todo_priority = todo_data.get("priority", priority or TodoPriority.MEDIUM)
                if todo_priority not in TODO_PRIORITIES:
                    raise ModelRetry(
                        f"Invalid priority '{todo_priority}'. Must be one of: "
                        f"{', '.join(TODO_PRIORITIES)}"
                    )
                todos_to_add.append((todo_content, todo_priority))
        elif isinstance(content, list):
            # List of strings format: ["task1", "task2", ...]
            default_priority = priority or TodoPriority.MEDIUM
            if default_priority not in TODO_PRIORITIES:
                raise ModelRetry(
                    f"Invalid priority '{default_priority}'. Must be one of: "
                    f"{', '.join(TODO_PRIORITIES)}"
                )
            for task_content in content:
                if not isinstance(task_content, str):
                    raise ModelRetry("All content items must be strings")
                todos_to_add.append((task_content, default_priority))
        else:
            raise ModelRetry(
                "For add_multiple, provide either 'todos' list or 'content' as list of strings"
            )

        if not todos_to_add:
            raise ModelRetry("No todos to add")

        # Check todo limit
        current_count = len(self.state_manager.session.todos)
        if current_count + len(todos_to_add) > MAX_TODOS_PER_SESSION:
            available = MAX_TODOS_PER_SESSION - current_count
            raise ModelRetry(
                f"Cannot add {len(todos_to_add)} todos. Only {available} slots available "
                f"(max {MAX_TODOS_PER_SESSION} per session)"
            )

        # Add all todos
        added_ids = []
        for task_content, task_priority in todos_to_add:
            # Validate content length
            if len(task_content) > MAX_TODO_CONTENT_LENGTH:
                raise ModelRetry(
                    f"Todo content is too long: '{task_content[:50]}...'. "
                    f"Maximum length is {MAX_TODO_CONTENT_LENGTH} characters"
                )

            # Generate UUID for guaranteed uniqueness
            new_id = f"todo_{uuid.uuid4().hex[:8]}"

            new_todo = TodoItem(
                id=new_id,
                content=task_content,
                status=TodoStatus.PENDING,
                priority=task_priority,
                created_at=datetime.now(),
            )

            self.state_manager.add_todo(new_todo)
            added_ids.append(new_id)

        count = len(added_ids)
        return f"Added {count} todos (IDs: {', '.join(added_ids)})"

    async def _update_todo(
        self,
        todo_id: Optional[str],
        status: Optional[str],
        priority: Optional[str],
        content: Optional[str],
    ) -> ToolResult:
        """Update an existing todo item."""
        if not todo_id:
            raise ModelRetry("Todo ID is required for updates")

        # Find the todo
        todo = None
        for t in self.state_manager.session.todos:
            if t.id == todo_id:
                todo = t
                break

        if not todo:
            raise ModelRetry(f"Todo with ID '{todo_id}' not found")

        changes = []

        # Update status if provided
        if status:
            if status not in [s.value for s in TodoStatus]:
                raise ModelRetry(
                    f"Invalid status '{status}'. Must be one of: "
                    f"{', '.join([s.value for s in TodoStatus])}"
                )
            todo.status = status
            if status == TodoStatus.COMPLETED.value and not todo.completed_at:
                todo.completed_at = datetime.now()
            changes.append(f"status to {status}")

        # Update priority if provided
        if priority:
            if priority not in [p.value for p in TodoPriority]:
                raise ModelRetry(
                    f"Invalid priority '{priority}'. Must be one of: "
                    f"{', '.join([p.value for p in TodoPriority])}"
                )
            todo.priority = priority
            changes.append(f"priority to {priority}")

        # Update content if provided
        if content:
            todo.content = content
            changes.append(f"content to '{content}'")

        if not changes:
            raise ModelRetry(
                "At least one of status, priority, or content must be provided for updates"
            )

        change_summary = ", ".join(changes)
        return f"Updated todo {todo_id}: {change_summary}"

    async def _complete_todo(self, todo_id: Optional[str]) -> ToolResult:
        """Mark a todo as completed."""
        if not todo_id:
            raise ModelRetry("Todo ID is required to mark as complete")

        # Find and update the todo
        for todo in self.state_manager.session.todos:
            if todo.id == todo_id:
                todo.status = TodoStatus.COMPLETED.value
                todo.completed_at = datetime.now()
                return f"Marked todo {todo_id} as completed: {todo.content}"

        raise ModelRetry(f"Todo with ID '{todo_id}' not found")

    async def _list_todos(self) -> ToolResult:
        """List all current todos."""
        todos = self.state_manager.session.todos
        if not todos:
            return "No todos found"

        # Group by status for better organization
        pending = [t for t in todos if t.status == TodoStatus.PENDING.value]
        in_progress = [t for t in todos if t.status == TodoStatus.IN_PROGRESS.value]
        completed = [t for t in todos if t.status == TodoStatus.COMPLETED.value]

        lines = []

        if in_progress:
            lines.append("IN PROGRESS:")
            for todo in in_progress:
                lines.append(f"  {todo.id}: {todo.content} (priority: {todo.priority})")

        if pending:
            lines.append("\nPENDING:")
            for todo in pending:
                lines.append(f"  {todo.id}: {todo.content} (priority: {todo.priority})")

        if completed:
            lines.append("\nCOMPLETED:")
            for todo in completed:
                lines.append(f"  {todo.id}: {todo.content}")

        return "\n".join(lines)

    async def _remove_todo(self, todo_id: Optional[str]) -> ToolResult:
        """Remove a todo item."""
        if not todo_id:
            raise ModelRetry("Todo ID is required to remove a todo")

        # Find the todo first to get its content for the response
        todo_content = None
        for todo in self.state_manager.session.todos:
            if todo.id == todo_id:
                todo_content = todo.content
                break

        if not todo_content:
            raise ModelRetry(f"Todo with ID '{todo_id}' not found")

        self.state_manager.remove_todo(todo_id)
        return f"Removed todo {todo_id}: {todo_content}"

    def get_current_todos_sync(self) -> str:
        """Get current todos synchronously for system prompt inclusion."""
        todos = self.state_manager.session.todos

        if not todos:
            return "No todos found"

        # Group by status for better organization
        pending = [t for t in todos if t.status == TodoStatus.PENDING.value]
        in_progress = [t for t in todos if t.status == TodoStatus.IN_PROGRESS.value]
        completed = [t for t in todos if t.status == TodoStatus.COMPLETED.value]

        lines = []

        if in_progress:
            lines.append("IN PROGRESS:")
            for todo in in_progress:
                lines.append(f"  {todo.id}: {todo.content} (priority: {todo.priority})")

        if pending:
            lines.append("\nPENDING:")
            for todo in pending:
                lines.append(f"  {todo.id}: {todo.content} (priority: {todo.priority})")

        if completed:
            lines.append("\nCOMPLETED:")
            for todo in completed:
                lines.append(f"  {todo.id}: {todo.content}")

        return "\n".join(lines)
