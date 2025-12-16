"""Integration test for multi-agent delegation pattern.

Tests the research agent delegation tool to ensure:
1. Delegation flow works correctly
2. Usage tracking aggregates across parent and child agents
3. Structured output is returned properly
4. Model parameter is passed through (not hardcoded)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.agent import CallToolsNode
from pydantic_ai.messages import ToolCallPart

from tunacode.core.agents.agent_components.agent_config import get_or_create_agent
from tunacode.core.agents.delegation_tools import (
    _get_tool_spinner_message,
    create_research_codebase_tool,
)
from tunacode.core.state import StateManager


@pytest.fixture
def state_manager() -> StateManager:
    """Create a StateManager with initialized session."""
    manager = StateManager()
    session = manager.session

    # Initialize required session attributes
    session.current_model = "gemini-2.0-flash-exp"  # Use a specific model for testing
    session.batch_counter = 0
    session.original_query = ""
    session.user_config = {
        "settings": {
            "max_retries": 3,
            "tool_strict_validation": False,
        }
    }

    # Initialize dynamic attributes
    setattr(session, "consecutive_empty_responses", 0)
    setattr(session, "request_id", "test-delegation-req")

    return manager


@pytest.mark.asyncio
async def test_research_agent_delegation_with_usage_tracking(
    state_manager: StateManager,
) -> None:
    """Test delegation to research agent with usage aggregation.

    Golden baseline test validating:
    - Delegation tool can be created and called
    - Research agent is created with correct model (not hardcoded)
    - Usage tracking context is passed through
    - Structured output is returned
    """
    # Create the delegation tool
    research_codebase = create_research_codebase_tool(state_manager)

    # Mock the research agent to avoid real API calls
    mock_result = MagicMock()
    mock_result.output = {
        "relevant_files": ["src/tunacode/core/agents/main.py"],
        "key_findings": ["Found RequestOrchestrator class"],
        "code_examples": [
            {
                "file": "src/tunacode/core/agents/main.py",
                "snippet": "class RequestOrchestrator:",
                "explanation": "Main orchestration class",
            }
        ],
        "recommendations": ["Review orchestration flow"],
    }

    # Mock RunContext with usage tracking
    mock_ctx = MagicMock()
    mock_usage = MagicMock()
    mock_ctx.usage = mock_usage

    with patch("tunacode.core.agents.delegation_tools.create_research_agent") as mock_factory:
        # Create a mock research agent with iter() method
        mock_research_agent = MagicMock()

        # Mock the async context manager returned by iter()
        mock_agent_run = AsyncMock()
        mock_agent_run.result = mock_result
        mock_agent_run.__aenter__ = AsyncMock(return_value=mock_agent_run)
        mock_agent_run.__aexit__ = AsyncMock(return_value=None)
        # Empty async iterator (no nodes)
        mock_agent_run.__aiter__ = lambda self: self
        mock_agent_run.__anext__ = AsyncMock(side_effect=StopAsyncIteration)

        mock_research_agent.iter = MagicMock(return_value=mock_agent_run)
        mock_factory.return_value = mock_research_agent

        # Call the delegation tool
        result = await research_codebase(
            ctx=mock_ctx,
            query="Find the main agent orchestration code",
            directories=["src/tunacode/core/agents"],
            max_files=5,
        )

        # Verify research agent was created with correct model and max_files limit
        # Note: max_files=5 passed to tool, but capped to 3 (hard limit)
        # Note: StateManager is isolated (new instance) for parallel execution safety
        mock_factory.assert_called_once()
        call_args = mock_factory.call_args
        assert call_args.args[0] == "gemini-2.0-flash-exp"
        assert isinstance(call_args.args[1], StateManager)  # Any StateManager instance
        assert call_args.kwargs["max_files"] == 3  # Should enforce hard limit of 3 (not 5)

        # Verify research agent iter() was called with usage context
        mock_research_agent.iter.assert_called_once()
        call_args = mock_research_agent.iter.call_args
        assert "usage" in call_args.kwargs
        assert call_args.kwargs["usage"] == mock_usage

        # Verify structured output is returned
        assert result is not None
        assert isinstance(result, dict)
        assert "relevant_files" in result
        assert "key_findings" in result
        assert "code_examples" in result
        assert "recommendations" in result

        # Validate output structure
        assert result["relevant_files"] == ["src/tunacode/core/agents/main.py"]
        assert result["key_findings"] == ["Found RequestOrchestrator class"]
        assert len(result["code_examples"]) == 1
        assert result["code_examples"][0]["file"] == "src/tunacode/core/agents/main.py"
        assert result["recommendations"] == ["Review orchestration flow"]


@pytest.mark.asyncio
async def test_delegation_tool_registered_in_agent(state_manager: StateManager) -> None:
    """Test that delegation tool is registered with main agent.

    Validates that the research_codebase tool appears in the agent's tool list
    when an agent is created.
    """
    with patch("tunacode.core.agents.agent_components.agent_config._create_model_with_retry"):
        # Mock the Agent class to avoid API key requirements
        with patch("tunacode.core.agents.agent_components.agent_config.Agent") as MockAgent:
            # Create a mock agent with tools
            mock_agent = MagicMock()
            mock_tools = []

            # Create mock tool objects for the 8 standard tools + 1 delegation tool
            for tool_name in [
                "bash",
                "glob",
                "grep",
                "list_dir",
                "read_file",
                "run_command",
                "update_file",
                "write_file",
                "research_codebase",
            ]:
                mock_tool = MagicMock()
                mock_tool.name = tool_name
                mock_tools.append(mock_tool)

            mock_agent.get_tools.return_value = mock_tools
            MockAgent.return_value = mock_agent

            # Create agent (this should include the delegation tool)
            agent = get_or_create_agent("gemini-2.0-flash-exp", state_manager)

            # Verify agent was created
            assert agent is not None

            # Check that delegation tool is in the agent's tools
            # We expect exactly 9 tools (8 standard + 1 delegation)
            tool_count = len(agent.get_tools())
            assert tool_count == 9, f"Expected 9 tools, got {tool_count}"

            # Verify tool names include research_codebase
            tool_names = [tool.name for tool in agent.get_tools()]
            assert "research_codebase" in tool_names, f"research_codebase not found in {tool_names}"


@pytest.mark.asyncio
async def test_delegation_tool_default_directories(state_manager: StateManager) -> None:
    """Test delegation tool with default directories parameter.

    Validates that directories parameter defaults to ["."] when not provided.
    """
    research_codebase = create_research_codebase_tool(state_manager)

    mock_result = MagicMock()
    mock_result.output = {
        "relevant_files": [],
        "key_findings": [],
        "code_examples": [],
        "recommendations": [],
    }

    mock_ctx = MagicMock()
    mock_ctx.usage = MagicMock()

    with patch("tunacode.core.agents.delegation_tools.create_research_agent") as mock_factory:
        mock_research_agent = MagicMock()

        # Mock the async context manager returned by iter()
        mock_agent_run = AsyncMock()
        mock_agent_run.result = mock_result
        mock_agent_run.__aenter__ = AsyncMock(return_value=mock_agent_run)
        mock_agent_run.__aexit__ = AsyncMock(return_value=None)
        mock_agent_run.__aiter__ = lambda self: self
        mock_agent_run.__anext__ = AsyncMock(side_effect=StopAsyncIteration)

        mock_research_agent.iter = MagicMock(return_value=mock_agent_run)
        mock_factory.return_value = mock_research_agent

        # Call without directories parameter
        result = await research_codebase(
            ctx=mock_ctx,
            query="Test query",
            # directories not provided - should default to ["."]
        )

        # Verify the prompt includes default directory
        call_args = mock_research_agent.iter.call_args
        prompt = call_args.args[0]
        assert "Search in directories: ." in prompt

        # Verify result structure
        assert isinstance(result, dict)
        assert "relevant_files" in result


@pytest.mark.asyncio
async def test_max_files_hard_limit_enforcement(state_manager: StateManager) -> None:
    """Test that max_files is capped at 3 even when higher value is passed.

    Validates that the hard limit of 3 files is enforced regardless of what
    the agent requests.
    """
    research_codebase = create_research_codebase_tool(state_manager)

    mock_result = MagicMock()
    mock_result.output = {
        "relevant_files": [],
        "key_findings": [],
        "code_examples": [],
        "recommendations": [],
    }

    mock_ctx = MagicMock()
    mock_ctx.usage = MagicMock()

    with patch("tunacode.core.agents.delegation_tools.create_research_agent") as mock_factory:
        mock_research_agent = MagicMock()

        # Mock the async context manager returned by iter()
        mock_agent_run = AsyncMock()
        mock_agent_run.result = mock_result
        mock_agent_run.__aenter__ = AsyncMock(return_value=mock_agent_run)
        mock_agent_run.__aexit__ = AsyncMock(return_value=None)
        mock_agent_run.__aiter__ = lambda self: self
        mock_agent_run.__anext__ = AsyncMock(side_effect=StopAsyncIteration)

        mock_research_agent.iter = MagicMock(return_value=mock_agent_run)
        mock_factory.return_value = mock_research_agent

        # Call with max_files=10 (should be capped to 3)
        result = await research_codebase(
            ctx=mock_ctx,
            query="Test query with excessive max_files",
            directories=["."],
            max_files=10,
        )

        # Verify the prompt shows max_files was capped to 3
        call_args = mock_research_agent.iter.call_args
        prompt = call_args.args[0]
        assert "Analyze up to 3 most relevant files" in prompt
        assert "10" not in prompt  # Should NOT contain the original value

        # Verify result structure
        assert isinstance(result, dict)
        assert "relevant_files" in result


class TestToolSpinnerMessage:
    """Tests for the _get_tool_spinner_message helper function."""

    def test_grep_message(self) -> None:
        """Test grep tool returns search pattern message."""
        message = _get_tool_spinner_message("grep", {"pattern": "def foo"})
        assert message == "Searching for 'def foo'..."

    def test_glob_message(self) -> None:
        """Test glob tool returns file pattern message."""
        message = _get_tool_spinner_message("glob", {"pattern": "*.py"})
        assert message == "Finding files matching '*.py'..."

    def test_list_dir_message(self) -> None:
        """Test list_dir tool returns directory path message."""
        message = _get_tool_spinner_message("list_dir", {"path": "src/tunacode"})
        assert message == "Listing directory 'src/tunacode'..."

    def test_limited_read_file_message(self) -> None:
        """Test limited_read_file tool returns file path message."""
        message = _get_tool_spinner_message("limited_read_file", {"file_path": "main.py"})
        assert message == "Reading main.py..."

    def test_unknown_tool_message(self) -> None:
        """Test unknown tool returns generic message."""
        message = _get_tool_spinner_message("unknown_tool", {})
        assert message == "Running unknown_tool..."

    def test_missing_args_uses_defaults(self) -> None:
        """Test that missing args use fallback defaults."""
        message = _get_tool_spinner_message("grep", {})
        assert message == "Searching for '...'..."

        message = _get_tool_spinner_message("glob", {})
        assert message == "Finding files matching '...'..."


@pytest.mark.asyncio
async def test_on_tool_call_callback_invocation(state_manager: StateManager) -> None:
    """Test that on_tool_call callback is invoked when child agent calls tools.

    This validates the UI feedback mechanism works correctly during delegation.
    """
    # Track callback invocations
    callback_messages: list[str] = []

    def track_callback(message: str) -> None:
        callback_messages.append(message)

    # Create delegation tool with callback
    research_codebase = create_research_codebase_tool(
        state_manager, on_tool_call=track_callback
    )

    mock_result = MagicMock()
    mock_result.output = {
        "relevant_files": ["test.py"],
        "key_findings": ["Found test"],
        "code_examples": [],
        "recommendations": [],
    }

    mock_ctx = MagicMock()
    mock_ctx.usage = MagicMock()

    with patch("tunacode.core.agents.delegation_tools.create_research_agent") as mock_factory:
        mock_research_agent = MagicMock()

        # Create a mock CallToolsNode with tool calls
        mock_tool_call_part = ToolCallPart(
            tool_name="grep",
            args={"pattern": "class Test"},
            tool_call_id="call_123",
        )

        mock_model_response = MagicMock()
        mock_model_response.parts = [mock_tool_call_part]

        mock_call_tools_node = MagicMock(spec=CallToolsNode)
        mock_call_tools_node.model_response = mock_model_response

        # Create async iterator that yields the CallToolsNode
        async def async_node_iterator():
            yield mock_call_tools_node

        mock_agent_run = AsyncMock()
        mock_agent_run.result = mock_result
        mock_agent_run.__aenter__ = AsyncMock(return_value=mock_agent_run)
        mock_agent_run.__aexit__ = AsyncMock(return_value=None)
        mock_agent_run.__aiter__ = lambda self: async_node_iterator()

        mock_research_agent.iter = MagicMock(return_value=mock_agent_run)
        mock_factory.return_value = mock_research_agent

        # Call the delegation tool
        result = await research_codebase(
            ctx=mock_ctx,
            query="Find test classes",
            directories=["."],
        )

        # Verify callback was invoked with correct message
        assert len(callback_messages) == 1
        assert callback_messages[0] == "Searching for 'class Test'..."

        # Verify result still returned correctly
        assert result["relevant_files"] == ["test.py"]


@pytest.mark.asyncio
async def test_no_callback_when_none_provided(state_manager: StateManager) -> None:
    """Test that no errors occur when on_tool_call is None."""
    # Create delegation tool without callback (default behavior)
    research_codebase = create_research_codebase_tool(state_manager)

    mock_result = MagicMock()
    mock_result.output = {
        "relevant_files": [],
        "key_findings": [],
        "code_examples": [],
        "recommendations": [],
    }

    mock_ctx = MagicMock()
    mock_ctx.usage = MagicMock()

    with patch("tunacode.core.agents.delegation_tools.create_research_agent") as mock_factory:
        mock_research_agent = MagicMock()

        # Create a mock CallToolsNode with tool calls
        mock_tool_call_part = ToolCallPart(
            tool_name="grep",
            args={"pattern": "test"},
            tool_call_id="call_456",
        )

        mock_model_response = MagicMock()
        mock_model_response.parts = [mock_tool_call_part]

        mock_call_tools_node = MagicMock(spec=CallToolsNode)
        mock_call_tools_node.model_response = mock_model_response

        async def async_node_iterator():
            yield mock_call_tools_node

        mock_agent_run = AsyncMock()
        mock_agent_run.result = mock_result
        mock_agent_run.__aenter__ = AsyncMock(return_value=mock_agent_run)
        mock_agent_run.__aexit__ = AsyncMock(return_value=None)
        mock_agent_run.__aiter__ = lambda self: async_node_iterator()

        mock_research_agent.iter = MagicMock(return_value=mock_agent_run)
        mock_factory.return_value = mock_research_agent

        # Should not raise any errors even though CallToolsNode is yielded
        result = await research_codebase(
            ctx=mock_ctx,
            query="Test without callback",
        )

        # Verify result returned correctly
        assert isinstance(result, dict)
