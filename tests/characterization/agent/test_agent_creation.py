"""
Characterization tests for agent creation functionality.
These tests capture the CURRENT behavior of get_or_create_agent().
"""

from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, Mock, patch

from tunacode.core.agents.agent_components import get_or_create_agent
from tunacode.core.agents.agent_components.agent_config import clear_all_caches

# No async tests in this file, so no pytestmark needed


def _build_prompt_side_effects(file_contents: Dict[str, str]):
    """Create pathlib side-effect helpers for prompt files."""

    def exists_side_effect(*args, **_unused_kwargs) -> bool:
        if not args:
            return False
        path = args[0]
        if not isinstance(path, Path):
            raise AssertionError(f"Expected Path instance, received {type(path)!r}")
        path_str = str(path)
        return any(path_str.endswith(filename) for filename in file_contents)

    def stat_side_effect(*args, **_unused_kwargs):
        if not args:
            raise FileNotFoundError()
        path = args[0]
        if not isinstance(path, Path):
            raise AssertionError(f"Expected Path instance, received {type(path)!r}")
        path_str = str(path)
        for index, filename in enumerate(file_contents, start=1):
            if path_str.endswith(filename):
                stat_result = Mock()
                stat_result.st_mtime = float(index)
                return stat_result
        raise FileNotFoundError()

    def read_text_side_effect(*args, **_unused_kwargs) -> str:
        if not args:
            raise FileNotFoundError()
        path = args[0]
        if not isinstance(path, Path):
            raise AssertionError(f"Expected Path instance, received {type(path)!r}")
        path_str = str(path)
        for filename, content in file_contents.items():
            if path_str.endswith(filename):
                return content
        raise FileNotFoundError()

    return exists_side_effect, stat_side_effect, read_text_side_effect


@contextmanager
def patch_prompt_files(file_contents: Dict[str, str]):
    """Patch pathlib interfaces to simulate prompt files."""

    exists_side_effect, stat_side_effect, read_text_side_effect = _build_prompt_side_effects(
        file_contents
    )

    with ExitStack() as stack:
        stack.enter_context(patch("pathlib.Path.exists", side_effect=exists_side_effect))
        stack.enter_context(patch("pathlib.PosixPath.exists", side_effect=exists_side_effect))
        stack.enter_context(patch("pathlib.Path.stat", side_effect=stat_side_effect))
        stack.enter_context(patch("pathlib.PosixPath.stat", side_effect=stat_side_effect))
        stack.enter_context(patch("pathlib.Path.read_text", side_effect=read_text_side_effect))
        stack.enter_context(patch("pathlib.PosixPath.read_text", side_effect=read_text_side_effect))
        yield


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
        self.state_manager.session.todos = []
        clear_all_caches()

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
            with patch_prompt_files({"system.xml": system_prompt}):
                with patch(
                    "tunacode.core.agents.agent_components.agent_config.get_mcp_servers",
                    return_value=[],
                ):
                    # Act
                    get_or_create_agent(model, self.state_manager)

        # Assert - Golden master
        assert model in self.state_manager.session.agents
        assert self.state_manager.session.agents[model] == mock_agent_class.return_value

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
        """Capture behavior when system.xml/md is loaded when available."""
        # Arrange
        model = "anthropic:claude-3"
        mock_agent_class = MagicMock()
        mock_tool_class = MagicMock()
        fallback_prompt = "Fallback system prompt from md file."

        with patch(
            "tunacode.core.agents.agent_components.agent_config.get_agent_tool",
            return_value=(mock_agent_class, mock_tool_class),
        ):
            with patch(
                "tunacode.core.agents.agent_components.agent_config.load_system_prompt",
                return_value=fallback_prompt,
            ):
                with patch(
                    "tunacode.core.agents.agent_components.agent_config.get_mcp_servers",
                    return_value=[],
                ):
                    # Act
                    get_or_create_agent(model, self.state_manager)

        # Assert - Golden master
        call_kwargs = mock_agent_class.call_args.kwargs
        # System prompt includes AGENTS.md context appended
        expected_prompt = (
            fallback_prompt
            + "\n\n# Project Context from AGENTS.md\n"
            + Path("AGENTS.md").read_text(encoding="utf-8")
        )
        assert call_kwargs["system_prompt"] == expected_prompt

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
            with patch_prompt_files({}):
                with patch(
                    "tunacode.core.agents.agent_components.agent_config.get_mcp_servers",
                    return_value=[],
                ):
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
            with patch_prompt_files({"system.xml": "prompt"}):
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
            with patch_prompt_files({"system.xml": "prompt"}):
                with patch(
                    "tunacode.core.agents.agent_components.agent_config.get_mcp_servers",
                    return_value=mock_mcp_servers,
                ):
                    # Act
                    get_or_create_agent(model, self.state_manager)

        # Assert - Golden master
        call_kwargs = mock_agent_class.call_args.kwargs
        assert call_kwargs["mcp_servers"] == mock_mcp_servers
