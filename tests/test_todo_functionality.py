"""Comprehensive tests for todo functionality."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from tunacode.cli.commands.implementations.todo import TodoCommand
from tunacode.core.state import StateManager
from tunacode.tools.todo import TodoTool
from tunacode.types import CommandContext, TodoItem


class TestTodoItem:
    """Test TodoItem data model."""

    def test_todo_item_creation(self):
        """Test TodoItem can be created with all required fields."""
        todo = TodoItem(
            id="1",
            content="Test task",
            status="pending",
            priority="high",
            created_at=datetime.now(),
        )

        assert todo.id == "1"
        assert todo.content == "Test task"
        assert todo.status == "pending"
        assert todo.priority == "high"
        assert todo.completed_at is None
        assert todo.tags == []

    def test_todo_item_with_all_fields(self):
        """Test TodoItem with all optional fields."""
        created = datetime.now()
        completed = datetime.now()

        todo = TodoItem(
            id="2",
            content="Complete task",
            status="completed",
            priority="medium",
            created_at=created,
            completed_at=completed,
            tags=["urgent", "work"],
        )

        assert todo.completed_at == completed
        assert todo.tags == ["urgent", "work"]


class TestStateManagerTodos:
    """Test StateManager todo management methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = StateManager()

    def test_add_todo(self):
        """Test adding a todo to state manager."""
        todo = TodoItem(
            id="1",
            content="Test task",
            status="pending",
            priority="medium",
            created_at=datetime.now(),
        )

        self.state_manager.add_todo(todo)
        assert len(self.state_manager.session.todos) == 1
        assert self.state_manager.session.todos[0] == todo

    def test_update_todo_status(self):
        """Test updating todo status."""
        todo = TodoItem(
            id="1",
            content="Test task",
            status="pending",
            priority="medium",
            created_at=datetime.now(),
        )
        self.state_manager.add_todo(todo)

        self.state_manager.update_todo("1", "completed")
        assert self.state_manager.session.todos[0].status == "completed"

    def test_remove_todo(self):
        """Test removing a todo."""
        todo = TodoItem(
            id="1",
            content="Test task",
            status="pending",
            priority="medium",
            created_at=datetime.now(),
        )
        self.state_manager.add_todo(todo)

        self.state_manager.remove_todo("1")
        assert len(self.state_manager.session.todos) == 0

    def test_clear_todos(self):
        """Test clearing all todos."""
        todo1 = TodoItem(
            id="1", content="Task 1", status="pending", priority="medium", created_at=datetime.now()
        )
        todo2 = TodoItem(
            id="2", content="Task 2", status="pending", priority="high", created_at=datetime.now()
        )

        self.state_manager.add_todo(todo1)
        self.state_manager.add_todo(todo2)

        self.state_manager.clear_todos()
        assert len(self.state_manager.session.todos) == 0


class TestTodoCommand:
    """Test TodoCommand CLI implementation - focusing on state changes."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = StateManager()
        self.context = CommandContext(state_manager=self.state_manager)
        self.command = TodoCommand()

    @pytest.mark.asyncio
    async def test_add_todo(self):
        """Test adding a todo via command."""
        await self.command.add_todo(["Test", "task", "content"], self.context)

        assert len(self.state_manager.session.todos) == 1

        todo = self.state_manager.session.todos[0]
        assert todo.content == "Test task content"
        assert todo.status == "pending"
        assert todo.priority == "medium"

    @pytest.mark.asyncio
    async def test_mark_todo_done(self):
        """Test marking a todo as done."""
        # Add a todo first
        await self.command.add_todo(["Test", "task"], self.context)
        todo_id = self.state_manager.session.todos[0].id

        # Mark it done
        await self.command.mark_done([todo_id], self.context)
        assert self.state_manager.session.todos[0].status == "completed"

    @pytest.mark.asyncio
    async def test_update_todo_status(self):
        """Test updating todo status."""
        await self.command.add_todo(["Test", "task"], self.context)
        todo_id = self.state_manager.session.todos[0].id

        await self.command.update_todo([todo_id, "in_progress"], self.context)
        assert self.state_manager.session.todos[0].status == "in_progress"

    @pytest.mark.asyncio
    async def test_set_todo_priority(self):
        """Test setting todo priority."""
        await self.command.add_todo(["Test", "task"], self.context)
        todo_id = self.state_manager.session.todos[0].id

        await self.command.set_priority([todo_id, "high"], self.context)
        assert self.state_manager.session.todos[0].priority == "high"

    @pytest.mark.asyncio
    async def test_remove_todo(self):
        """Test removing a todo."""
        await self.command.add_todo(["Test", "task"], self.context)
        todo_id = self.state_manager.session.todos[0].id

        await self.command.remove_todo([todo_id], self.context)
        assert len(self.state_manager.session.todos) == 0

    @pytest.mark.asyncio
    async def test_clear_todos(self):
        """Test clearing all todos."""
        await self.command.add_todo(["Task", "1"], self.context)
        await self.command.add_todo(["Task", "2"], self.context)

        await self.command.clear_todos(self.context)
        assert len(self.state_manager.session.todos) == 0


class TestTodoTool:
    """Test TodoTool for agent integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = StateManager()
        self.ui_logger = Mock()
        self.tool = TodoTool(self.state_manager, self.ui_logger)

    @pytest.mark.asyncio
    async def test_add_todo(self):
        """Test adding todo via tool."""
        result = await self.tool._execute(action="add", content="Test task", priority="high")

        assert "Test task (priority: high)" in result
        assert len(self.state_manager.session.todos) == 1

        todo = self.state_manager.session.todos[0]
        assert todo.content == "Test task"
        assert todo.priority == "high"
        assert todo.status == "pending"

    @pytest.mark.asyncio
    async def test_add_todo_default_priority(self):
        """Test adding todo with default priority."""
        result = await self.tool._execute(action="add", content="Test task")

        assert "medium" in result
        assert self.state_manager.session.todos[0].priority == "medium"

    @pytest.mark.asyncio
    async def test_update_todo_status(self):
        """Test updating todo status via tool."""
        # Add a todo first
        await self.tool._execute(action="add", content="Test task")
        todo_id = self.state_manager.session.todos[0].id

        result = await self.tool._execute(action="update", todo_id=todo_id, status="in_progress")
        assert "status to in_progress" in result
        assert self.state_manager.session.todos[0].status == "in_progress"

    @pytest.mark.asyncio
    async def test_complete_todo(self):
        """Test completing todo via tool."""
        # Add a todo first
        await self.tool._execute(action="add", content="Test task")
        todo_id = self.state_manager.session.todos[0].id

        result = await self.tool._execute(action="complete", todo_id=todo_id)
        assert "as completed" in result

        todo = self.state_manager.session.todos[0]
        assert todo.status == "completed"
        assert todo.completed_at is not None

    @pytest.mark.asyncio
    async def test_list_todos_empty(self):
        """Test listing when no todos exist."""
        result = await self.tool._execute(action="list")
        assert result == "No todos found"

    @pytest.mark.asyncio
    async def test_list_todos_with_content(self):
        """Test listing todos with content."""
        # Add todos in different states
        await self.tool._execute(action="add", content="Pending task", priority="high")
        await self.tool._execute(action="add", content="In progress task", priority="medium")
        todo2_id = self.state_manager.session.todos[1].id
        await self.tool._execute(action="update", todo_id=todo2_id, status="in_progress")
        await self.tool._execute(action="add", content="Low priority pending task", priority="low")
        await self.tool._execute(action="add", content="Completed task", priority="medium")
        todo4_id = self.state_manager.session.todos[3].id
        await self.tool._execute(action="complete", todo_id=todo4_id)

        result = await self.tool._execute(action="list")

        # Check that all sections are present
        assert "IN PROGRESS:" in result
        assert "PENDING:" in result
        assert "COMPLETED:" in result

    @pytest.mark.asyncio
    async def test_remove_todo(self):
        """Test removing todo via tool."""
        await self.tool._execute(action="add", content="Test task")
        todo_id = self.state_manager.session.todos[0].id

        result = await self.tool._execute(action="remove", todo_id=todo_id)
        assert "Test task" in result
        assert len(self.state_manager.session.todos) == 0

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in tool."""
        from pydantic_ai.exceptions import ModelRetry

        # Test invalid action
        with pytest.raises(ModelRetry) as exc_info:
            await self.tool._execute(action="invalid")
        assert "Invalid action" in str(exc_info.value)

        # Test missing content for add
        with pytest.raises(ModelRetry) as exc_info:
            await self.tool._execute(action="add")
        assert "Content is required" in str(exc_info.value)

        # Test missing todo_id for update
        with pytest.raises(ModelRetry) as exc_info:
            await self.tool._execute(action="update")
        assert "Todo ID is required" in str(exc_info.value)

        # Test invalid todo_id
        with pytest.raises(ModelRetry) as exc_info:
            await self.tool._execute(action="update", todo_id="999", status="completed")
        assert "not found" in str(exc_info.value)


class TestTodoIntegration:
    """Integration tests for todo functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = StateManager()
        self.context = CommandContext(state_manager=self.state_manager)
        self.command = TodoCommand()
        self.tool = TodoTool(self.state_manager)

    @pytest.mark.asyncio
    async def test_command_and_tool_integration(self):
        """Test that command and tool work together on same state."""
        # Add todo via command
        await self.command.add_todo(["Command", "task"], self.context)

        # Add todo via tool
        await self.tool._execute(action="add", content="Tool task", priority="high")

        # Verify both are in state
        assert len(self.state_manager.session.todos) == 2
        assert self.state_manager.session.todos[0].content == "Command task"
        assert self.state_manager.session.todos[1].content == "Tool task"

        # Update via tool
        todo1_id = self.state_manager.session.todos[0].id
        await self.tool._execute(action="update", todo_id=todo1_id, status="in_progress")

        # Verify the state was updated correctly
        assert self.state_manager.session.todos[0].status == "in_progress"

    @pytest.mark.asyncio
    async def test_id_generation_consistency(self):
        """Test that IDs are generated consistently."""
        # Add via command
        await self.command.add_todo(["First", "task"], self.context)

        # Add via tool
        await self.tool._execute(action="add", content="Second task")

        # Verify IDs are unique timestamp-based strings
        id1 = self.state_manager.session.todos[0].id
        id2 = self.state_manager.session.todos[1].id
        assert id1 != id2
        assert len(id1) > 10  # Timestamp-based IDs are long
        assert id1.isdigit()  # Should be numeric
        assert id2.isdigit()  # Should be numeric

    @pytest.mark.asyncio
    async def test_add_multiple_todos_structured(self):
        """Test adding multiple todos with structured format."""
        todos_data = [
            {"content": "Task 1", "priority": "high"},
            {"content": "Task 2", "priority": "medium"},
            {"content": "Task 3", "priority": "low"},
        ]

        result = await self.tool._execute("add_multiple", todos=todos_data)

        assert "Added 3 todos" in result
        assert len(self.state_manager.session.todos) == 3

        # Verify content and priorities
        assert self.state_manager.session.todos[0].content == "Task 1"
        assert self.state_manager.session.todos[0].priority == "high"
        assert self.state_manager.session.todos[1].content == "Task 2"
        assert self.state_manager.session.todos[1].priority == "medium"
        assert self.state_manager.session.todos[2].content == "Task 3"
        assert self.state_manager.session.todos[2].priority == "low"

    @pytest.mark.asyncio
    async def test_add_multiple_todos_list_format(self):
        """Test adding multiple todos with list of strings."""
        content_list = ["Task A", "Task B", "Task C"]

        result = await self.tool._execute("add_multiple", content=content_list, priority="high")

        assert "Added 3 todos" in result
        assert len(self.state_manager.session.todos) == 3

        # Verify all have high priority and correct content
        for i, todo in enumerate(self.state_manager.session.todos):
            assert todo.content == content_list[i]
            assert todo.priority == "high"

    @pytest.mark.asyncio
    async def test_add_multiple_todos_error_handling(self):
        """Test error handling for add_multiple action."""
        # Test with no data
        with pytest.raises(Exception):
            await self.tool._execute("add_multiple")

        # Test with invalid priority in structured format
        invalid_todos = [{"content": "Task", "priority": "invalid"}]
        with pytest.raises(Exception):
            await self.tool._execute("add_multiple", todos=invalid_todos)

        # Test with missing content in structured format
        invalid_todos = [{"priority": "high"}]
        with pytest.raises(Exception):
            await self.tool._execute("add_multiple", todos=invalid_todos)

    def test_get_current_todos_sync(self):
        """Test synchronous todo listing for system prompt inclusion."""
        # Add some todos with different statuses
        todo1 = TodoItem(
            id="1", content="Task 1", status="pending", priority="high", created_at=datetime.now()
        )
        todo2 = TodoItem(
            id="2",
            content="Task 2",
            status="in_progress",
            priority="medium",
            created_at=datetime.now(),
        )
        todo3 = TodoItem(
            id="3", content="Task 3", status="completed", priority="low", created_at=datetime.now()
        )

        self.state_manager.add_todo(todo1)
        self.state_manager.add_todo(todo2)
        self.state_manager.add_todo(todo3)

        # Test synchronous listing
        result = self.tool.get_current_todos_sync()

        # Verify the format and content
        assert "IN PROGRESS:" in result
        assert "PENDING:" in result
        assert "COMPLETED:" in result
        assert "Task 1" in result
        assert "Task 2" in result
        assert "Task 3" in result

    def test_get_current_todos_sync_empty(self):
        """Test synchronous todo listing when no todos exist."""
        result = self.tool.get_current_todos_sync()
        assert result == "No todos found"
