"""
Characterization tests for main.py refactoring.

These tests capture the current behavior of the main agent functionality
to ensure refactoring doesn't break existing functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tunacode.core.agents.agent_components import (
    ToolBuffer,
    check_task_completion,
    execute_tools_parallel,
    extract_and_execute_tool_calls,
    get_model_messages,
    get_or_create_agent,
    parse_json_tool_calls,
    patch_tool_messages,
)
from tunacode.types import StateManager


class TestMainAgentCharacterization:
    """Test suite capturing current main agent behavior."""

    @pytest.fixture
    def mock_state_manager(self):
        """Create a mock state manager with required attributes."""
        state_manager = MagicMock(spec=StateManager)

        # Setup session attributes
        state_manager.session = MagicMock()
        state_manager.session.current_iteration = 0
        state_manager.session.show_thoughts = False
        state_manager.session.messages = []
        state_manager.session.tool_calls = []
        state_manager.session.agents = {}
        state_manager.session.user_config = {"settings": {"max_retries": 3}}
        state_manager.session.current_model = "test-model"
        state_manager.session.files_in_context = set()
        state_manager.session.iteration_count = 0
        state_manager.session.error_count = 0
        state_manager.session.consecutive_empty_responses = 0

        # Add is_plan_mode mock for plan mode UI
        state_manager.is_plan_mode = MagicMock(return_value=False)

        return state_manager

    def test_check_task_completion_with_marker(self):
        """Test detecting task completion marker."""
        content = "TUNACODE DONE:\nTask has been completed successfully."

        is_complete, cleaned = check_task_completion(content)

        assert is_complete is True
        assert cleaned == "Task has been completed successfully."

    def test_check_task_completion_without_marker(self):
        """Test content without completion marker."""
        content = "This is regular content without a marker."

        is_complete, cleaned = check_task_completion(content)

        assert is_complete is False
        assert cleaned == content

    def test_check_task_completion_empty_content(self):
        """Test empty content handling."""
        is_complete, cleaned = check_task_completion("")

        assert is_complete is False
        assert cleaned == ""

    def test_tool_buffer_operations(self):
        """Test ToolBuffer functionality."""
        buffer = ToolBuffer()

        # Test empty buffer
        assert not buffer.has_tasks()
        assert buffer.flush() == []

        # Add tasks
        mock_part1 = MagicMock()
        mock_node1 = MagicMock()
        buffer.add(mock_part1, mock_node1)

        assert buffer.has_tasks()

        # Add another task
        mock_part2 = MagicMock()
        mock_node2 = MagicMock()
        buffer.add(mock_part2, mock_node2)

        # Flush and verify
        tasks = buffer.flush()
        assert len(tasks) == 2
        assert tasks[0] == (mock_part1, mock_node1)
        assert tasks[1] == (mock_part2, mock_node2)

        # Buffer should be empty after flush
        assert not buffer.has_tasks()
        assert buffer.flush() == []

    @pytest.mark.asyncio
    async def test_execute_tools_parallel_basic(self):
        """Test parallel tool execution."""
        # Create mock tool calls
        tool_calls = []
        results = []

        for i in range(3):
            part = MagicMock()
            part.tool_name = f"tool_{i}"
            node = MagicMock()
            tool_calls.append((part, node))
            results.append(f"result_{i}")

        # Mock callback that returns different results
        call_count = 0

        async def mock_callback(part, node):
            nonlocal call_count
            result = results[call_count]
            call_count += 1
            return result

        # Execute in parallel
        actual_results = await execute_tools_parallel(tool_calls, mock_callback)

        assert actual_results == results
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_execute_tools_parallel_with_exception(self):
        """Test parallel execution with exceptions."""
        tool_calls = [(MagicMock(), MagicMock()), (MagicMock(), MagicMock())]

        async def mock_callback(part, node):
            if part == tool_calls[0][0]:
                raise Exception("Test error")
            return "success"

        results = await execute_tools_parallel(tool_calls, mock_callback, return_exceptions=True)

        assert len(results) == 2
        assert isinstance(results[0], Exception)
        assert results[1] == "success"

    def test_get_model_messages(self):
        """Test getting model message classes."""
        ModelRequest, ToolReturnPart, SystemPromptPart = get_model_messages()

        # Should return classes (or mocks if in test environment)
        assert ModelRequest is not None
        assert ToolReturnPart is not None
        assert SystemPromptPart is not None

    @pytest.mark.asyncio
    async def test_parse_json_tool_calls_valid(self, mock_state_manager):
        """Test parsing valid JSON tool calls."""
        text = '{"tool": "read_file", "args": {"file_path": "test.py"}}'

        mock_callback = AsyncMock()

        result = await parse_json_tool_calls(text, mock_callback, mock_state_manager)

        assert result == 1  # One tool executed
        mock_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_json_tool_calls_no_tools(self, mock_state_manager):
        """Test parsing text without tool calls."""
        text = "This is just regular text without any JSON."

        mock_callback = AsyncMock()

        result = await parse_json_tool_calls(text, mock_callback, mock_state_manager)

        assert result == 0  # No tools found
        mock_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_and_execute_tool_calls_basic(self, mock_state_manager):
        """Test extracting and executing tool calls from text."""
        text = 'Some text with {"tool": "grep", "args": {"pattern": "test"}} in it.'

        mock_callback = AsyncMock()

        result = await extract_and_execute_tool_calls(text, mock_callback, mock_state_manager)

        assert result >= 1  # At least one tool found
        mock_callback.assert_called()

    @pytest.mark.asyncio
    async def test_extract_and_execute_tool_calls_code_block(self, mock_state_manager):
        """Test extracting tool calls from code blocks."""
        text = """
        Here's a tool call:
        ```json
        {"tool": "write_file", "args": {"file_path": "new.py", "content": "print('hello')"}}
        ```
        """

        mock_callback = AsyncMock()

        result = await extract_and_execute_tool_calls(text, mock_callback, mock_state_manager)

        assert result >= 1
        mock_callback.assert_called()

    def test_patch_tool_messages_no_orphans(self, mock_state_manager):
        """Test patching when all tools have responses."""
        # Create messages with matching tool call and return
        tool_call_part = MagicMock()
        tool_call_part.part_kind = "tool-call"
        tool_call_part.tool_call_id = "123"
        tool_call_part.tool_name = "test_tool"

        tool_return_part = MagicMock()
        tool_return_part.part_kind = "tool-return"
        tool_return_part.tool_call_id = "123"

        msg1 = MagicMock()
        msg1.parts = [tool_call_part]

        msg2 = MagicMock()
        msg2.parts = [tool_return_part]

        mock_state_manager.session.messages = [msg1, msg2]

        # Should not add any messages since tool has a response
        initial_count = len(mock_state_manager.session.messages)
        patch_tool_messages("Error", mock_state_manager)

        assert len(mock_state_manager.session.messages) == initial_count

    def test_patch_tool_messages_with_orphans(self, mock_state_manager):
        """Test patching orphaned tool calls."""
        # Create message with tool call but no return
        tool_call_part = MagicMock()
        tool_call_part.part_kind = "tool-call"
        tool_call_part.tool_call_id = "456"
        tool_call_part.tool_name = "orphaned_tool"

        msg = MagicMock()
        msg.parts = [tool_call_part]

        mock_state_manager.session.messages = [msg]

        # Mock the model message classes
        with patch("tunacode.core.agents.agent_components.get_model_messages") as mock_get_messages:
            mock_model_request = MagicMock()
            mock_tool_return = MagicMock()
            mock_get_messages.return_value = (mock_model_request, mock_tool_return, MagicMock())

            initial_count = len(mock_state_manager.session.messages)
            patch_tool_messages("Tool failed", mock_state_manager)

            # Should add one message for the orphaned tool
            assert len(mock_state_manager.session.messages) == initial_count + 1

    @pytest.mark.asyncio
    async def test_get_or_create_agent_new(self, mock_state_manager):
        """Test creating a new agent instance."""
        model_name = "test-model"

        with patch(
            "tunacode.core.agents.agent_components.agent_config.get_agent_tool"
        ) as mock_get_tool:
            mock_agent_class = MagicMock()
            mock_tool_class = MagicMock()
            mock_get_tool.return_value = (mock_agent_class, mock_tool_class)

            # Mock system prompt loading
            with patch("builtins.open", create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = "System prompt"

                # Mock AGENTS.md loading
                with patch("pathlib.Path.exists", return_value=False):
                    # Mock TodoTool
                    with patch(
                        "tunacode.core.agents.agent_components.agent_config.TodoTool"
                    ) as mock_todo:
                        mock_todo.return_value.get_current_todos_sync.return_value = (
                            "No todos found"
                        )

                        get_or_create_agent(model_name, mock_state_manager)

                        # Should create and store agent
                        mock_agent_class.assert_called_once()
                        assert model_name in mock_state_manager.session.agents

    @pytest.mark.asyncio
    async def test_get_or_create_agent_existing(self, mock_state_manager):
        """Test retrieving existing agent instance."""
        model_name = "test-model"
        existing_agent = MagicMock()
        mock_state_manager.session.agents[model_name] = existing_agent

        agent = get_or_create_agent(model_name, mock_state_manager)

        assert agent is existing_agent

    def test_imports_available(self):
        """Test that all required imports are available."""
        # Test key classes and functions can be imported
        from tunacode.core.agents.agent_components import (
            ResponseState,
            SimpleResult,
            _process_node,
        )
        from tunacode.core.agents.main import (
            check_query_satisfaction,
            process_request,
        )

        # Verify they exist
        assert ResponseState is not None
        assert SimpleResult is not None
        assert _process_node is not None
        assert check_query_satisfaction is not None
        assert process_request is not None
