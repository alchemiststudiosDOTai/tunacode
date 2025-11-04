"""
Characterization test for model selection configuration persistence behavior.

This test documents the new behavior of the /model command where:
- `/model provider:model` updates session state AND persists to config by default
- `/model provider:model default` continues to persist and trigger restart

This establishes a baseline for the updated persistence behavior.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tunacode.cli.commands.implementations.model import ModelCommand
from tunacode.core.state import StateManager
from tunacode.types import CommandContext


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_file = temp_path / "tunacode.json"
        yield config_file


@pytest.fixture
def mock_state_manager(temp_config_dir):
    """Create a mock state manager with temp config."""
    state_manager = MagicMock(spec=StateManager)
    state_manager.session = MagicMock()

    # Use a real dict for user_config to ensure it behaves correctly
    real_config = {}
    state_manager.session.user_config = real_config
    state_manager.session.current_model = "gpt-4"
    return state_manager


@pytest.fixture
def mock_context(mock_state_manager):
    """Create a mock command context."""
    context = MagicMock(spec=CommandContext)
    context.state_manager = mock_state_manager
    return context


@pytest.fixture
def model_command():
    """Create a ModelCommand instance with mocked registry."""
    command = ModelCommand()
    command.registry = MagicMock()
    command._registry_loaded = True
    return command


class TestModelSelectionCharacterization:
    """Characterization tests for current model selection behavior."""

    @pytest.mark.asyncio
    async def test_model_selection_without_default_persists_to_config(
        self, model_command, mock_context, temp_config_dir, monkeypatch
    ):
        """
        Updated behavior: /model provider:model persists to config by default.
        """
        # Mock the config file path
        monkeypatch.setattr(
            "tunacode.utils.user_configuration.ApplicationSettings",
            lambda: MagicMock(
                paths=MagicMock(config_dir=temp_config_dir.parent, config_file=temp_config_dir)
            ),
        )

        # Mock registry to return a valid model
        mock_model_info = MagicMock()
        mock_model_info.full_id = "openai:gpt-4"
        mock_model_info.name = "GPT-4"
        model_command.registry.get_model.return_value = mock_model_info

        # Execute model selection without 'default'
        await model_command._set_model("openai:gpt-4", [], mock_context)

        # Verify session was updated
        assert mock_context.state_manager.session.current_model == "openai:gpt-4"

        # Verify config file WAS created/updated (new behavior)
        assert temp_config_dir.exists()
        contents = json.loads(temp_config_dir.read_text())
        assert contents.get("default_model") == "openai:gpt-4"

    @pytest.mark.asyncio
    async def test_model_selection_with_default_persists_to_config(
        self, model_command, mock_context, temp_config_dir, monkeypatch
    ):
        """
        Behavior: /model provider:model default persists to config file and triggers restart.
        """
        # Mock the config file path and save_config function
        monkeypatch.setattr(
            "tunacode.utils.user_configuration.ApplicationSettings",
            lambda: MagicMock(
                paths=MagicMock(config_dir=temp_config_dir.parent, config_file=temp_config_dir)
            ),
        )

        mock_save_config = MagicMock(return_value=True)
        monkeypatch.setattr("tunacode.utils.user_configuration.save_config", mock_save_config)

        # Mock registry to return a valid model
        mock_model_info = MagicMock()
        mock_model_info.full_id = "anthropic:claude-3-sonnet"
        mock_model_info.name = "Claude 3 Sonnet"
        model_command.registry.get_model.return_value = mock_model_info

        # Execute model selection with 'default'
        await model_command._set_model("anthropic:claude-3-sonnet", ["default"], mock_context)

        # Verify session was updated
        assert mock_context.state_manager.session.current_model == "anthropic:claude-3-sonnet"

        # Verify config save was attempted
        mock_save_config.assert_called_once_with(mock_context.state_manager)

        # Verify the config was updated in memory
        assert (
            mock_context.state_manager.session.user_config.get("default_model")
            == "anthropic:claude-3-sonnet"
        )

    @pytest.mark.asyncio
    async def test_config_file_contents_before_and_after_default_command(
        self, model_command, mock_context, temp_config_dir, monkeypatch
    ):
        """
        Characterization: Config file contents before/after default command.

        This demonstrates how the config file changes when using 'default'.
        """
        # Create initial config file
        initial_config = {"default_model": "openai:gpt-3.5-turbo", "settings": {"theme": "dark"}}
        temp_config_dir.write_text(json.dumps(initial_config, indent=2))

        # Mock the config file path
        monkeypatch.setattr(
            "tunacode.utils.user_configuration.ApplicationSettings",
            lambda: MagicMock(
                paths=MagicMock(config_dir=temp_config_dir.parent, config_file=temp_config_dir)
            ),
        )

        # Load the initial config into the state manager
        mock_context.state_manager.session.user_config = initial_config.copy()

        # Mock registry to return a valid model
        mock_model_info = MagicMock()
        mock_model_info.full_id = "google:gemini-pro"
        mock_model_info.name = "Gemini Pro"
        model_command.registry.get_model.return_value = mock_model_info

        # Verify initial config contents
        initial_contents = json.loads(temp_config_dir.read_text())
        assert initial_contents["default_model"] == "openai:gpt-3.5-turbo"

        # Execute model selection with 'default'
        await model_command._set_model("google:gemini-pro", ["default"], mock_context)

        # Verify config file was updated and session manager config reflects the change
        assert (
            mock_context.state_manager.session.user_config["default_model"] == "google:gemini-pro"
        )

        # Verify other settings were preserved
        assert mock_context.state_manager.session.user_config["settings"]["theme"] == "dark"

    @pytest.mark.asyncio
    async def test_multiple_model_selections_without_default_persists_last_selection(
        self, model_command, mock_context, temp_config_dir, monkeypatch
    ):
        """
        Updated behavior: Multiple model selections without 'default' persist;
        last selection should be reflected in config.
        """
        # Create initial config file
        initial_config = {"default_model": "openai:gpt-4"}
        temp_config_dir.write_text(json.dumps(initial_config, indent=2))

        # Mock the config file path
        monkeypatch.setattr(
            "tunacode.utils.user_configuration.ApplicationSettings",
            lambda: MagicMock(
                paths=MagicMock(config_dir=temp_config_dir.parent, config_file=temp_config_dir)
            ),
        )

        # Mock registry to return valid models
        def mock_get_model(model_id):
            mock_model = MagicMock()
            mock_model.full_id = model_id
            mock_model.name = model_id.split(":")[1]
            return mock_model

        model_command.registry.get_model = mock_get_model

        # Load initial config
        mock_context.state_manager.session.user_config = initial_config.copy()

        # Execute multiple model selections without 'default'
        await model_command._set_model("anthropic:claude-3-haiku", [], mock_context)
        await model_command._set_model("google:gemini-flash", [], mock_context)

        # Verify session changed to last model
        assert mock_context.state_manager.session.current_model == "google:gemini-flash"

        # Verify config file updated to last selection
        final_contents = json.loads(temp_config_dir.read_text())
        assert final_contents["default_model"] == "google:gemini-flash"

    def test_characterization_summary(self):
        """
        Summary of updated behavior characterization:

        NEW BEHAVIOR:
        - `/model provider:model` → Updates session state AND persists to config (auto-persist)
        - `/model provider:model default` → Updates session, persists to config,
          and returns 'restart'

        NOTES:
        - This reduces friction by persisting selections by default
        - Backward-compatible: "default" keyword still supported
        """
        # This is a documentation test - no assertions needed
        pass
