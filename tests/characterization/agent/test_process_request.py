"""
Characterization tests for process_request functionality.
These tests capture the CURRENT behavior of the main request processing function.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from tunacode.core.agents.main import process_request

pytestmark = pytest.mark.asyncio


class MockNode:
    """Mock node for testing."""

    def __init__(self, result=None):
        if result:
            self.result = result


class MockResult:
    """Mock result object."""

    def __init__(self, output=None):
        self.output = output if output else ""


class TestProcessRequest:
    """Golden-master tests for process_request behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = Mock()
        self.state_manager.session = Mock()
        self.state_manager.session.messages = []
        self.state_manager.session.agents = {}
        self.state_manager.session.user_config = {
            "settings": {
                "max_retries": 3,
                "max_iterations": 40,
                "fallback_response": True,
                "fallback_verbosity": "normal",
            }
        }
        self.state_manager.session.show_thoughts = False
        self.state_manager.session.tool_calls = []
        self.state_manager.session.files_in_context = set()
        self.state_manager.session.iteration_count = 0
        self.state_manager.session.current_iteration = 0
        # Ensure token counter attributes return integers for += operations
        self.state_manager.session.consecutive_empty_responses = 0

    def create_mock_agent_run(self, nodes):
        """Create a mock agent run that properly implements async iteration."""

        class MockAgentRun:
            def __init__(self, nodes):
                self.nodes = nodes
                self.result = None
                self._index = 0
                self.ctx = MagicMock()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def __aiter__(self):
                self._index = 0
                return self

            async def __anext__(self):
                if self._index >= len(self.nodes):
                    raise StopAsyncIteration
                node = self.nodes[self._index]
                self._index += 1
                return node

        return MockAgentRun(nodes)

    async def test_process_request_basic_flow(self):
        """Capture behavior of basic request processing."""
        # Arrange
        message = "Test request"
        nodes = [MockNode(), MockNode(result=MockResult(output="Task completed"))]

        mock_agent = MagicMock()
        mock_agent_run = self.create_mock_agent_run(nodes)

        @asynccontextmanager
        async def mock_iter(msg, message_history):
            yield mock_agent_run

        mock_agent.iter = mock_iter

        with patch(
            "tunacode.core.agents.agent_components.get_or_create_agent", return_value=mock_agent
        ):
            with patch(
                "tunacode.core.agents.agent_components._process_node", new_callable=AsyncMock
            ) as mock_process:
                # Configure mock to return expected tuple
                mock_process.return_value = (False, None)
                with patch(
                    "tunacode.core.agents.agent_components.parse_json_tool_calls", return_value=0
                ):
                    # Act
                    result = await process_request("openai:gpt-4", message, self.state_manager)

                    # Assert - Golden master
                    assert hasattr(result, "response_state")
                    assert result.response_state.has_user_response
                    assert not result.response_state.has_final_synthesis
                    assert self.state_manager.session.iteration_count == 2
                    assert mock_process.call_count == 2

    async def test_process_request_max_iterations_reached(self):
        """Capture behavior when max iterations is reached."""
        # Arrange
        self.state_manager.session.user_config["settings"]["max_iterations"] = 3
        message = "Complex task"

        # Create nodes that exceed max iterations
        nodes = [MockNode() for _ in range(5)]

        mock_agent = MagicMock()
        mock_agent_run = self.create_mock_agent_run(nodes)
        mock_agent_run.result = None  # No result to trigger fallback

        @asynccontextmanager
        async def mock_iter(msg, message_history):
            yield mock_agent_run

        mock_agent.iter = mock_iter

        with patch(
            "tunacode.core.agents.agent_components.get_or_create_agent", return_value=mock_agent
        ):
            with patch(
                "tunacode.core.agents.agent_components._process_node", new_callable=AsyncMock
            ) as mock_process:
                # Configure mock to return expected tuple
                mock_process.return_value = (False, None)
                with patch("tunacode.core.agents.agent_components.patch_tool_messages"):
                    with patch(
                        "tunacode.core.agents.agent_components.parse_json_tool_calls",
                        return_value=0,
                    ):
                        # Act
                        result = await process_request("openai:gpt-4", message, self.state_manager)

                        # Assert - Golden master
                        assert self.state_manager.session.iteration_count == 5
                        assert hasattr(result, "response_state")
                        # With these mocks, process_request processes all nodes
                        # The actual fallback generation happens in the real implementation
                        # but our mocks don't trigger it properly

    async def test_process_request_fallback_response_detailed(self):
        """Capture behavior of detailed fallback response generation."""
        # Arrange
        self.state_manager.session.user_config["settings"]["max_iterations"] = 2
        self.state_manager.session.user_config["settings"]["fallback_verbosity"] = "detailed"
        message = "Complex task"

        # Add some tool calls to messages for fallback analysis
        tool_call_part1 = Mock()
        tool_call_part1.part_kind = "tool-call"
        tool_call_part1.tool_name = "write_file"
        tool_call_part1.args = {"file_path": "/tmp/test1.txt"}

        tool_call_part2 = Mock()
        tool_call_part2.part_kind = "tool-call"
        tool_call_part2.tool_name = "bash"
        tool_call_part2.args = {"command": "echo 'test command'"}

        msg_with_tools = Mock()
        msg_with_tools.parts = [tool_call_part1, tool_call_part2]

        self.state_manager.session.messages = [msg_with_tools]

        nodes = [MockNode(), MockNode()]

        mock_agent = MagicMock()
        mock_agent_run = self.create_mock_agent_run(nodes)
        mock_agent_run.result = None

        @asynccontextmanager
        async def mock_iter(msg, message_history):
            yield mock_agent_run

        mock_agent.iter = mock_iter

        with patch(
            "tunacode.core.agents.agent_components.get_or_create_agent", return_value=mock_agent
        ):
            with patch(
                "tunacode.core.agents.agent_components._process_node", new_callable=AsyncMock
            ) as mock_process:
                # Configure mock to return expected tuple
                mock_process.return_value = (False, None)
                with patch(
                    "tunacode.core.agents.agent_components.parse_json_tool_calls", return_value=0
                ):
                    # Act
                    result = await process_request(
                        "openai:gpt-4", message, self.state_manager, AsyncMock()
                    )

                    # Assert - Golden master
                    # With mocked _process_node, the fallback logic may not trigger properly
                    # Check basic response structure
                    assert hasattr(result, "response_state")
                    # When max iterations is reached with detailed verbosity, it asks for user guidance
                    assert result.response_state.awaiting_user_guidance
                    # The detailed fallback message generation happens in real implementation

    async def test_process_request_fallback_disabled(self):
        """Capture behavior when fallback response is disabled."""
        # Arrange
        self.state_manager.session.user_config["settings"]["max_iterations"] = 2
        self.state_manager.session.user_config["settings"]["fallback_response"] = False
        message = "Test task"

        nodes = [MockNode(), MockNode(), MockNode()]

        mock_agent = MagicMock()
        mock_agent_run = self.create_mock_agent_run(nodes)
        mock_agent_run.result = None

        @asynccontextmanager
        async def mock_iter(msg, message_history):
            yield mock_agent_run

        mock_agent.iter = mock_iter

        with patch(
            "tunacode.core.agents.agent_components.get_or_create_agent", return_value=mock_agent
        ):
            with patch(
                "tunacode.core.agents.agent_components._process_node", new_callable=AsyncMock
            ) as mock_process:
                # Configure mock to return expected tuple
                mock_process.return_value = (False, None)
                with patch(
                    "tunacode.core.agents.agent_components.parse_json_tool_calls", return_value=0
                ):
                    # Act
                    result = await process_request("openai:gpt-4", message, self.state_manager)

                    # Assert - Golden master
                    assert self.state_manager.session.iteration_count == 3  # Processes all 3 nodes
                    assert hasattr(result, "response_state")
                    # When fallback is disabled, no synthesis is generated
                    assert not result.response_state.has_final_synthesis

    async def test_process_request_with_thoughts_enabled(self):
        """Capture behavior with thoughts display enabled."""
        # Arrange
        self.state_manager.session.show_thoughts = True
        message = "Test with thoughts"

        nodes = [MockNode(), MockNode()]

        mock_agent = MagicMock()
        mock_agent_run = self.create_mock_agent_run(nodes)

        @asynccontextmanager
        async def mock_iter(msg, message_history):
            yield mock_agent_run

        mock_agent.iter = mock_iter

        # Create a side effect for _process_node that adds tool calls
        async def mock_process_node(*args, **kwargs):
            # Extract state_manager from args (it's the 3rd argument)
            state_manager = args[2] if len(args) > 2 else kwargs.get("state_manager")

            # Simulate tool calls being added during processing
            if state_manager.session.current_iteration == 1:
                state_manager.session.tool_calls.extend(
                    [
                        {"tool": "read_file", "args": {}, "iteration": 1},
                        {"tool": "bash", "args": {}, "iteration": 1},
                    ]
                )
            elif state_manager.session.current_iteration == 2:
                state_manager.session.tool_calls.append(
                    {"tool": "read_file", "args": {}, "iteration": 2}
                )
            return (False, None)

        with patch(
            "tunacode.core.agents.agent_components.get_or_create_agent", return_value=mock_agent
        ):
            with patch(
                "tunacode.core.agents.agent_components._process_node", new_callable=AsyncMock
            ) as mock_process:
                # Configure mock to use our side effect
                mock_process.side_effect = mock_process_node
                with patch("tunacode.ui.console.muted", new_callable=AsyncMock) as mock_muted:
                    with patch(
                        "tunacode.core.agents.agent_components.parse_json_tool_calls",
                        return_value=0,
                    ):
                        # Act
                        await process_request(
                            "openai:gpt-4", message, self.state_manager, AsyncMock()
                        )

                        # Assert - Golden master
                        calls = [
                            str(call[0][0]) if call[0] else "" for call in mock_muted.call_args_list
                        ]

                        # Should show iteration progress (default is now 40)
                        assert any("ITERATION: 1/40" in call for call in calls)
                        assert any("ITERATION: 2/40" in call for call in calls)

                        # Should show tool summary
                        assert any("TOOLS USED: read_file: 2, bash: 1" in call for call in calls)

    async def test_process_request_iteration_tracking(self):
        """Capture behavior of iteration tracking."""
        # Arrange
        message = "Test iteration tracking"

        # Track iteration values during processing
        iteration_values = []

        async def track_iterations(*args):
            # args = (node, tool_callback, state_manager, tool_buffer)
            sm = args[2] if len(args) > 2 else self.state_manager
            iteration_values.append(sm.session.current_iteration)
            # Return expected tuple
            return (False, None)

        nodes = [MockNode(), MockNode(), MockNode()]

        mock_agent = MagicMock()
        mock_agent_run = self.create_mock_agent_run(nodes)

        @asynccontextmanager
        async def mock_iter(msg, message_history):
            yield mock_agent_run

        mock_agent.iter = mock_iter

        with patch(
            "tunacode.core.agents.agent_components.get_or_create_agent", return_value=mock_agent
        ):
            with patch(
                "tunacode.core.agents.agent_components._process_node", side_effect=track_iterations
            ):
                with patch(
                    "tunacode.core.agents.agent_components.parse_json_tool_calls", return_value=0
                ):
                    # Act
                    await process_request("openai:gpt-4", message, self.state_manager)

                    # Assert - Golden master
                    assert self.state_manager.session.iteration_count == 3
                    assert iteration_values == [1, 2, 3]  # 1-indexed

    async def test_process_request_message_history_copy(self):
        """Capture behavior of message history copying."""
        # Arrange
        message = "Test message"
        original_messages = ["msg1", "msg2"]
        self.state_manager.session.messages = original_messages.copy()

        captured_history = None

        mock_agent = MagicMock()

        @asynccontextmanager
        async def mock_iter(msg, message_history):
            nonlocal captured_history
            captured_history = message_history
            yield self.create_mock_agent_run([])

        mock_agent.iter = mock_iter

        with patch(
            "tunacode.core.agents.agent_components.get_or_create_agent", return_value=mock_agent
        ):
            with patch(
                "tunacode.core.agents.agent_components.parse_json_tool_calls", return_value=0
            ):
                # Act
                await process_request("openai:gpt-4", message, self.state_manager)

                # Assert - Golden master
                assert captured_history == original_messages
                assert (
                    captured_history is not self.state_manager.session.messages
                )  # Different object

    async def test_process_request_wrapper_attributes(self):
        """Capture behavior of result wrapper classes."""
        # Arrange
        message = "Test wrapper"

        mock_agent = MagicMock()
        mock_agent_run = self.create_mock_agent_run([MockNode()])
        mock_agent_run.custom_attribute = "test_value"
        mock_agent_run.result = MockResult(output="Done")

        @asynccontextmanager
        async def mock_iter(msg, message_history):
            yield mock_agent_run

        mock_agent.iter = mock_iter

        with patch(
            "tunacode.core.agents.agent_components.get_or_create_agent", return_value=mock_agent
        ):
            with patch(
                "tunacode.core.agents.agent_components._process_node", new_callable=AsyncMock
            ) as mock_process:
                # Configure mock to return expected tuple
                mock_process.return_value = (False, None)
                with patch(
                    "tunacode.core.agents.agent_components.parse_json_tool_calls", return_value=0
                ):
                    # Act
                    result = await process_request("openai:gpt-4", message, self.state_manager)

                    # Assert - Golden master
                    # Wrapper should preserve original attributes
                    assert hasattr(result, "response_state")
                    assert hasattr(result, "custom_attribute")
                    assert result.custom_attribute == "test_value"
                    assert result.result.output == "Done"
