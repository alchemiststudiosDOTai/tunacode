"""
Characterization tests for agent creation functionality.
These tests capture the CURRENT behavior of get_or_create_agent().
"""

from unittest.mock import MagicMock, Mock, mock_open, patch

from tunacode.core.agents.agent_components import get_or_create_agent

# No async tests in this file, so no pytestmark needed


class TestAgentCreation:
    """Golden-master tests for agent creation behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = Mock()
        self.state_manager.session = Mock()
        self.state_manager.session.agents = {}
        self.state_manager.session.user_config = {"settings": {"max_retries": 3}}
        self.state_manager.is_plan_mode = Mock(return_value=False)
        self.state_manager.todos = []

    def test_get_or_create_agent_first_time(self):
        """Capture behavior when creating agent for first time."""
        # Arrange
        model = "openai:gpt-4"
        mock_agent_class = MagicMock()
        mock_tool_class = MagicMock()

        # Mock the system prompt file reading
        system_prompt = "You are a helpful AI assistant."

        with patch(
            "tunacode.core.agents.agent_components.agent_config.get_agent_tool",
            return_value=(mock_agent_class, mock_tool_class),
        ):
            with patch("builtins.open", mock_open(read_data=system_prompt)):
                with patch(
                    "tunacode.core.agents.agent_components.agent_config.get_mcp_servers",
                    return_value=[],
                ):
                    # Mock TUNACODE.md not existing to get predictable system prompt
                    with patch("pathlib.Path.exists", return_value=False):
                        # Act
                        get_or_create_agent(model, self.state_manager)

                        # Assert - Golden master
                        assert model in self.state_manager.session.agents
                        assert (
                            self.state_manager.session.agents[model]
                            == mock_agent_class.return_value
                        )

                        # Verify agent was created with correct parameters
                        mock_agent_class.assert_called_once()
                        call_kwargs = mock_agent_class.call_args.kwargs
                        assert call_kwargs["model"] == model
                        assert call_kwargs["system_prompt"] == system_prompt
                        assert len(call_kwargs["tools"]) == 10  # All 10 tools registered
                        assert call_kwargs["mcp_servers"] == []

    def test_get_or_create_agent_cached(self):
        """Capture behavior when agent already exists."""
        # Arrange
        model = "openai:gpt-4"
        existing_agent = Mock()
        self.state_manager.session.agents[model] = existing_agent

        # Act
        result = get_or_create_agent(model, self.state_manager)

        # Assert - Golden master
        assert result == existing_agent
        assert len(self.state_manager.session.agents) == 1

    def test_get_or_create_agent_system_prompt_fallback(self):
        """Capture behavior when system.md not found, falls back to system.txt."""
        # Arrange
        model = "anthropic:claude-3"
        mock_agent_class = MagicMock()
        mock_tool_class = MagicMock()
        fallback_prompt = "Fallback system prompt from txt file."

        def mock_open_side_effect(filename, *args, **kwargs):
            if str(filename).endswith("system.md"):
                raise FileNotFoundError()
            return mock_open(read_data=fallback_prompt)()

        with patch(
            "tunacode.core.agents.agent_components.agent_config.get_agent_tool",
            return_value=(mock_agent_class, mock_tool_class),
        ):
            with patch("builtins.open", side_effect=mock_open_side_effect):
                with patch(
                    "tunacode.core.agents.agent_components.agent_config.get_mcp_servers",
                    return_value=[],
                ):
                    # Mock TUNACODE.md not existing
                    with patch("pathlib.Path.exists", return_value=False):
                        # Act
                        get_or_create_agent(model, self.state_manager)

                        # Assert - Golden master
                        call_kwargs = mock_agent_class.call_args.kwargs
                        assert call_kwargs["system_prompt"] == "You are a helpful AI assistant."

    def test_get_or_create_agent_default_prompt(self):
        """Capture behavior when neither prompt file exists."""
        # Arrange
        model = "google:gemini-pro"
        mock_agent_class = MagicMock()
        mock_tool_class = MagicMock()

        with patch(
            "tunacode.core.agents.agent_components.agent_config.get_agent_tool",
            return_value=(mock_agent_class, mock_tool_class),
        ):
            with patch("builtins.open", side_effect=FileNotFoundError):
                with patch(
                    "tunacode.core.agents.agent_components.agent_config.get_mcp_servers",
                    return_value=[],
                ):
                    # Mock TUNACODE.md not existing
                    with patch("pathlib.Path.exists", return_value=False):
                        # Act
                        get_or_create_agent(model, self.state_manager)

                        # Assert - Golden master
                        call_kwargs = mock_agent_class.call_args.kwargs
                        assert call_kwargs["system_prompt"] == "You are a helpful AI assistant."

    def test_get_or_create_agent_tools_registered(self):
        """Capture behavior of tool registration with max_retries."""
        # Arrange
        model = "openai:gpt-4"
        self.state_manager.session.user_config["settings"]["max_retries"] = 5
        mock_agent_class = MagicMock()
        mock_tool_class = MagicMock()

        with patch(
            "tunacode.core.agents.agent_components.agent_config.get_agent_tool",
            return_value=(mock_agent_class, mock_tool_class),
        ):
            with patch("builtins.open", mock_open(read_data="prompt")):
                with patch(
                    "tunacode.core.agents.agent_components.agent_config.get_mcp_servers",
                    return_value=[],
                ):
                    # Act
                    get_or_create_agent(model, self.state_manager)

                    # Assert - Golden master
                    call_kwargs = mock_agent_class.call_args.kwargs
                    tools = call_kwargs["tools"]

                    # Verify all 10 tools are registered
                    assert len(tools) == 10

                    # Verify each tool has max_retries set
                    for tool in tools:
                        assert mock_tool_class.call_args_list[0].kwargs["max_retries"] == 5

    def test_get_or_create_agent_with_mcp_servers(self):
        """Capture behavior when MCP servers are available."""
        # Arrange
        model = "openai:gpt-4"
        mock_agent_class = MagicMock()
        mock_tool_class = MagicMock()
        mock_mcp_servers = [Mock(), Mock()]

        with patch(
            "tunacode.core.agents.agent_components.agent_config.get_agent_tool",
            return_value=(mock_agent_class, mock_tool_class),
        ):
            with patch("builtins.open", mock_open(read_data="prompt")):
                with patch(
                    "tunacode.core.agents.agent_components.agent_config.get_mcp_servers",
                    return_value=mock_mcp_servers,
                ):
                    # Act
                    get_or_create_agent(model, self.state_manager)

                    # Assert - Golden master
                    call_kwargs = mock_agent_class.call_args.kwargs
                    assert call_kwargs["mcp_servers"] == mock_mcp_servers
