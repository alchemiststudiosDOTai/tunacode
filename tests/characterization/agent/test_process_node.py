"""
Characterization tests for _process_node functionality.
These tests capture the CURRENT behavior of node processing.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from tunacode.core.agents.agent_components import ResponseState, ToolBuffer, _process_node

pytestmark = pytest.mark.asyncio


class MockNode:
    """Mock node for testing."""

    def __init__(self, request=None, thought=None, model_response=None, result=None):
        if request:
            self.request = request
        if thought:
            self.thought = thought
        if model_response:
            self.model_response = model_response
        if result:
            self.result = result


class MockPart:
    """Mock message part."""

    def __init__(self, content=None, part_kind=None, tool_name=None, args=None, tool_call_id=None):
        self.part_kind = part_kind  # Always set part_kind, even if None
        if content is not None:
            self.content = content
        if tool_name:
            self.tool_name = tool_name
        if args is not None:
            self.args = args
        if tool_call_id:
            self.tool_call_id = tool_call_id


class MockModelResponse:
    """Mock model response."""

    def __init__(self, parts):
        self.parts = parts


class TestProcessNode:
    """Golden-master tests for _process_node behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = Mock()
        self.state_manager.session = Mock()
        self.state_manager.session.messages = []
        self.state_manager.session.show_thoughts = False
        self.state_manager.session.tool_calls = []
        self.state_manager.session.files_in_context = set()
        self.state_manager.session.current_iteration = 1
        self.state_manager.session.spinner = None
        self.state_manager.session.batch_counter = 0
        self.state_manager.session.consecutive_empty_responses = 0
        self.state_manager.is_plan_mode = Mock(return_value=False)

    async def test_process_node_with_request(self):
        """Capture behavior when node has request."""
        # Arrange
        request = {"role": "user", "content": "Test request"}
        node = MockNode(request=request)

        # Act
        await _process_node(node, None, self.state_manager)

        # Assert - Golden master
        assert len(self.state_manager.session.messages) == 1
        assert self.state_manager.session.messages[0] == request

    async def test_process_node_with_thought(self):
        """Capture behavior when node has thought."""
        # Arrange
        thought = "Thinking about the problem..."
        node = MockNode(thought=thought)

        # Act
        await _process_node(node, None, self.state_manager)

        # Assert - Golden master
        assert len(self.state_manager.session.messages) == 1
        assert self.state_manager.session.messages[0] == {"thought": thought}

    async def test_process_node_with_thought_display_enabled(self):
        """Capture behavior when thoughts display is enabled."""
        # Arrange
        self.state_manager.session.show_thoughts = True
        thought = "Planning the approach..."
        node = MockNode(thought=thought)

        with patch("tunacode.ui.console.muted", new_callable=AsyncMock) as mock_muted:
            # Act
            await _process_node(node, None, self.state_manager)

            # Assert - Golden master
            mock_muted.assert_called_with(f"THOUGHT: {thought}")

    async def test_process_node_with_tool_calls(self):
        """Capture behavior processing tool calls."""
        # Arrange
        tool_call = MockPart(
            part_kind="tool-call",
            tool_name="read_file",
            args={"file_path": "/tmp/test.txt"},
            tool_call_id="tool_123",
        )
        response = MockModelResponse([tool_call])
        node = MockNode(model_response=response)
        tool_callback = AsyncMock()

        # Act
        await _process_node(node, tool_callback, self.state_manager)

        # Assert - Golden master
        assert len(self.state_manager.session.messages) == 1
        assert self.state_manager.session.messages[0] == response

        # Tool call tracked
        assert len(self.state_manager.session.tool_calls) == 1
        assert self.state_manager.session.tool_calls[0] == {
            "tool": "read_file",
            "args": {"file_path": "/tmp/test.txt"},
            "timestamp": None,
        }

        # Note: File tracking in files_in_context was removed in refactoring

        # Callback invoked
        tool_callback.assert_called_once_with(tool_call, node)

    async def test_process_node_tool_call_with_string_args(self):
        """Capture behavior when tool args is string instead of dict."""
        # Arrange
        self.state_manager.session.show_thoughts = True
        tool_call = MockPart(
            part_kind="tool-call",
            tool_name="bash",
            args="echo 'string args'",  # String instead of dict
            tool_call_id="tool_456",
        )
        response = MockModelResponse([tool_call])
        node = MockNode(model_response=response)
        tool_callback = AsyncMock()

        # Enable thoughts to see the warning
        self.state_manager.session.show_thoughts = True

        with patch("tunacode.ui.console.warning", new_callable=AsyncMock) as mock_warning:
            # Act
            await _process_node(node, tool_callback, self.state_manager)

            # Assert - Golden master
            # Should log the tool collection line for bash even when args is a raw string
            calls = [c.args[0] for c in mock_warning.call_args_list]
            assert any("SEQUENTIAL: bash" in line for line in calls)

    async def test_process_node_tool_return(self):
        """Capture behavior processing tool returns."""
        # Arrange
        tool_return = MockPart(
            part_kind="tool-return", tool_name="grep", content="Found 5 matches in 3 files"
        )
        response = MockModelResponse([tool_return])
        node = MockNode(model_response=response)

        # Act
        await _process_node(node, None, self.state_manager)

        # Assert - Golden master
        # Tool returns are now part of the model response, not separate messages
        assert len(self.state_manager.session.messages) == 1
        assert self.state_manager.session.messages[0] == response

    async def test_process_node_model_response_thoughts_enabled(self):
        """Capture behavior extracting thoughts from model response."""
        # Arrange
        self.state_manager.session.show_thoughts = True

        # Multiple thought patterns
        content_with_thoughts = """
        Let me think about this problem.
        {"thought": "Need to check the file first"}
        I'll read the file to understand the context.
        {"thought": "File might contain configuration data"}
        """

        part = MockPart(content=content_with_thoughts)
        response = MockModelResponse([part])
        node = MockNode(model_response=response)

        with patch("tunacode.ui.console.muted", new_callable=AsyncMock) as mock_muted:
            with patch("tunacode.utils.token_counter.estimate_tokens", return_value=150):
                # Act
                await _process_node(node, None, self.state_manager)

                # Assert - Golden master
                # MODEL RESPONSE is only shown when there are tool calls
                # Since this response has no tool calls, it won't be displayed
                # Check that the response was processed (muted was called for content)
                assert mock_muted.called

    async def test_process_node_fallback_json_parsing(self):
        """Capture behavior when no structured tool calls but JSON in content."""
        # Arrange
        content_with_json_tool = (
            'I need to read a file: {"tool": "read_file", "args": {"file_path": "config.json"}}'
        )
        part = MockPart(content=content_with_json_tool)
        response = MockModelResponse([part])
        node = MockNode(model_response=response)
        tool_callback = AsyncMock()

        # Act
        await _process_node(node, tool_callback, self.state_manager)

        # Assert - Fallback JSON parsing was removed in refactoring
        # Tool callback should not be called for JSON in text content
        tool_callback.assert_not_called()

    async def test_process_node_tool_display_formatting(self):
        """Capture behavior of special tool display formatting."""
        # Arrange
        self.state_manager.session.show_thoughts = True

        # Various tool types
        tools = [
            MockPart(
                part_kind="tool-call",
                tool_name="read_file",
                args={"file_path": "/very/long/path/to/some/file.txt"},
                tool_call_id="1",
            ),
            MockPart(
                part_kind="tool-call",
                tool_name="write_file",
                args={"file_path": "output.txt", "content": "data"},
                tool_call_id="2",
            ),
            MockPart(
                part_kind="tool-call",
                tool_name="update_file",
                args={"file_path": "main.py", "pattern": "old", "replacement": "new"},
                tool_call_id="3",
            ),
            MockPart(
                part_kind="tool-call",
                tool_name="bash",
                args={"command": "find . -name '*.py' | xargs grep -l 'import os' | head -20"},
                tool_call_id="4",
            ),
            MockPart(
                part_kind="tool-call",
                tool_name="list_dir",
                args={"directory": "/home/user/projects"},
                tool_call_id="5",
            ),
            MockPart(
                part_kind="tool-call",
                tool_name="grep",
                args={"pattern": "TODO", "directory": ".", "include_files": "*.py"},
                tool_call_id="6",
            ),
        ]

        response = MockModelResponse(tools)
        node = MockNode(model_response=response)
        tool_callback = AsyncMock()

        with patch("tunacode.ui.console.warning", new_callable=AsyncMock) as mock_warning:
            # Act
            await _process_node(node, tool_callback, self.state_manager)

            # Assert - Golden master
            calls = [call[0][0] for call in mock_warning.call_args_list]

            # Verify that each tool name was logged with warning
            expected_tools = [
                "read_file",
                "write_file",
                "update_file",
                "bash",
                "list_dir",
                "grep",
            ]
            for tool_name in expected_tools:
                assert any(f"SEQUENTIAL: {tool_name}" in line for line in calls)

    async def test_process_node_edge_cases(self):
        """Capture behavior with edge cases."""
        # Arrange
        # Tool with no args attribute
        tool_no_args = MockPart(
            part_kind="tool-call", tool_name="custom_tool", tool_call_id="no_args"
        )

        # Tool with None args
        tool_none_args = MockPart(
            part_kind="tool-call", tool_name="another_tool", args=None, tool_call_id="none_args"
        )

        response = MockModelResponse([tool_no_args, tool_none_args])
        node = MockNode(model_response=response)
        tool_callback = AsyncMock()

        # Act
        await _process_node(node, tool_callback, self.state_manager)

        # Assert - Golden master
        assert len(self.state_manager.session.tool_calls) == 2

        # No args becomes empty dict
        assert self.state_manager.session.tool_calls[0]["args"] == {}

        # None args becomes empty dict
        assert self.state_manager.session.tool_calls[1]["args"] == {}

    async def test_buffer_persists_after_truncation_guard(self):
        """Capture current behavior when truncated guard triggers with buffered tools."""
        # Arrange
        tool_call = MockPart(
            part_kind="tool-call",
            tool_name="grep",
            args={"pattern": "TODO"},
            tool_call_id="tool-buffered",
        )
        tool_node = MockNode(model_response=MockModelResponse([tool_call]))
        truncated_text = MockPart(content="the<|tool_call_argument_begin|>")
        truncated_node = MockNode(model_response=MockModelResponse([truncated_text]))
        tool_buffer = ToolBuffer()
        response_state = ResponseState()
        tool_callback = AsyncMock()

        with (
            patch("tunacode.ui.console.update_spinner_message", new_callable=AsyncMock),
            patch(
                "tunacode.ui.console.muted",
                new_callable=AsyncMock,
            ),
            patch("tunacode.ui.console.warning", new_callable=AsyncMock),
        ):
            # Populate buffer with the read-only tool
            await _process_node(
                tool_node,
                tool_callback,
                self.state_manager,
                tool_buffer,
                response_state=response_state,
            )

            # Act - truncated content response
            empty_response, reason = await _process_node(
                truncated_node,
                tool_callback,
                self.state_manager,
                tool_buffer,
                response_state=response_state,
            )

        # Assert - Golden master captures current bug
        assert empty_response is True
        assert reason == "truncated"
        assert not tool_buffer.has_tasks()
        tool_callback.assert_awaited()
        assert tool_callback.await_count == 1
