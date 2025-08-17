"""Tests for the onboarding features introduced in issue #55."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tunacode.cli.commands.base import CommandCategory
from tunacode.cli.commands.implementations.quickstart import QuickStartCommand
from tunacode.core.setup.config_setup import ConfigSetup
from tunacode.core.state import StateManager
from tunacode.exceptions import (
    ConfigurationError,
    FirstTimeSetupError,
    ModelConfigurationError,
    OnboardingError,
    ValidationError,
)
from tunacode.tutorial import TutorialManager
from tunacode.types import CommandContext


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager for testing."""
    state_manager = MagicMock(spec=StateManager)
    state_manager.session = MagicMock()
    state_manager.session.user_config = {
        "settings": {
            "enable_tutorial": True,
            "enable_streaming": True
        },
        "env": {},
        "default_model": "openai:gpt-4"
    }
    state_manager.session.messages = []
    return state_manager


@pytest.fixture
def mock_command_context(mock_state_manager):
    """Create a mock command context for testing."""
    context = MagicMock(spec=CommandContext)
    context.state_manager = mock_state_manager
    context.process_request = AsyncMock()
    return context


class TestQuickStartCommand:
    """Test the QuickStart command functionality."""

    def test_command_spec(self):
        """Test that the QuickStart command has correct specifications."""
        cmd = QuickStartCommand()

        assert cmd.spec.name == "quickstart"
        assert "/quickstart" in cmd.spec.aliases
        assert "/qs" in cmd.spec.aliases
        assert cmd.spec.category == CommandCategory.SYSTEM
        assert "tutorial" in cmd.spec.description.lower()

    @pytest.mark.asyncio
    async def test_quickstart_execution_user_cancels(self, mock_command_context):
        """Test quickstart command when user cancels."""
        cmd = QuickStartCommand()

        # Mock user input to cancel
        with patch('tunacode.ui.console.input', new_callable=AsyncMock) as mock_input:
            mock_input.return_value = "n"

            with patch('tunacode.ui.console.panel', new_callable=AsyncMock) as mock_panel:
                with patch('tunacode.ui.console.info', new_callable=AsyncMock) as mock_info:
                    await cmd.execute([], mock_command_context)

                    # Verify tutorial was offered
                    assert mock_panel.called

                    # Verify cancellation message was shown
                    mock_info.assert_called_once()
                    assert "cancelled" in mock_info.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_quickstart_saves_completion_status(self, mock_command_context):
        """Test that quickstart saves completion status."""
        cmd = QuickStartCommand()

        # Mock all the tutorial steps to complete quickly
        with patch('tunacode.ui.console.input', new_callable=AsyncMock) as mock_input:
            # User accepts tutorial and continues through all steps
            mock_input.side_effect = ["y", "y", "y", "y", "y"]  # Accept and continue through steps

            with patch('tunacode.ui.console.panel', new_callable=AsyncMock):
                with patch('tunacode.ui.console.success', new_callable=AsyncMock):
                    with patch('tunacode.utils.user_configuration.save_config') as mock_save:
                        await cmd.execute([], mock_command_context)

                        # Verify completion was marked
                        settings = mock_command_context.state_manager.session.user_config["settings"]
                        assert settings.get("quickstart_completed") is True

                        # Verify config was saved
                        assert mock_save.called


class TestTutorialManager:
    """Test the tutorial manager functionality."""

    def test_tutorial_manager_initialization(self, mock_state_manager):
        """Test tutorial manager initializes correctly."""
        manager = TutorialManager(mock_state_manager)

        assert manager.state_manager == mock_state_manager
        assert len(manager.steps) > 0
        assert len(manager.step_order) > 0
        assert "welcome" in manager.step_order
        assert "completion" in manager.step_order

    @pytest.mark.asyncio
    async def test_should_offer_tutorial_new_user(self, mock_state_manager):
        """Test that tutorial is offered to new users."""
        # Simulate new user
        mock_state_manager.session.messages = []
        mock_state_manager.session.user_config["settings"]["enable_tutorial"] = True

        # Mock the tutorial completion check
        with patch('tunacode.tutorial.steps.is_tutorial_completed', return_value=False):
            manager = TutorialManager(mock_state_manager)
            should_offer = await manager.should_offer_tutorial()

            assert should_offer is True

    @pytest.mark.asyncio
    async def test_should_not_offer_tutorial_completed_user(self, mock_state_manager):
        """Test that tutorial is not offered to users who completed it."""
        # Mock the tutorial completion check
        with patch('tunacode.tutorial.steps.is_tutorial_completed', return_value=True):
            manager = TutorialManager(mock_state_manager)
            should_offer = await manager.should_offer_tutorial()

            assert should_offer is False

    @pytest.mark.asyncio
    async def test_should_not_offer_tutorial_disabled(self, mock_state_manager):
        """Test that tutorial is not offered when disabled."""
        mock_state_manager.session.user_config["settings"]["enable_tutorial"] = False

        with patch('tunacode.tutorial.steps.is_tutorial_completed', return_value=False):
            manager = TutorialManager(mock_state_manager)
            should_offer = await manager.should_offer_tutorial()

            assert should_offer is False


class TestEnhancedExceptions:
    """Test the enhanced exception classes with actionable error messages."""

    def test_configuration_error_with_suggestions(self):
        """Test ConfigurationError includes suggested actions."""
        suggested_actions = ["Run tunacode --wizard", "Check your API key"]
        help_links = ["https://docs.tunacode.ai/setup"]
        quick_fix = "tunacode --wizard"

        error = ConfigurationError(
            "Test error",
            suggested_actions=suggested_actions,
            help_links=help_links,
            quick_fix=quick_fix
        )

        error_str = str(error)

        # Check that all components are included
        assert "Test error" in error_str
        assert "💡 Quick fix: tunacode --wizard" in error_str
        assert "🔧 Suggested actions:" in error_str
        assert "1. Run tunacode --wizard" in error_str
        assert "2. Check your API key" in error_str
        assert "📚 More help:" in error_str
        assert "https://docs.tunacode.ai/setup" in error_str

    def test_onboarding_error_structure(self):
        """Test OnboardingError has proper structure."""
        error = OnboardingError("setup", "API key validation failed", "Check your API key")

        error_str = str(error)

        # Check core components
        assert "Onboarding failed at step 'setup'" in error_str
        assert "API key validation failed" in error_str
        assert "Check your API key" in error_str
        assert "tunacode --wizard" in error_str
        assert "🔧 Suggested actions:" in error_str
        assert "📚 More help:" in error_str

    def test_model_configuration_error_invalid_format(self):
        """Test ModelConfigurationError for invalid model format."""
        error = ModelConfigurationError(model="gpt-4")  # Missing provider prefix

        error_str = str(error)

        assert "Invalid model format" in error_str
        assert "gpt-4" in error_str
        assert "provider:model" in error_str
        assert "openai:gpt-4" in error_str

    def test_first_time_setup_error_no_api_key(self):
        """Test FirstTimeSetupError for missing API key."""
        error = FirstTimeSetupError("no_api_key")

        error_str = str(error)

        assert "No API key provided" in error_str
        assert "platform.openai.com" in error_str
        assert "console.anthropic.com" in error_str
        assert "tunacode --wizard" in error_str

    def test_validation_error_with_format_details(self):
        """Test ValidationError includes format details."""
        error = ValidationError(
            "Invalid input",
            field="model",
            expected_format="provider:model-name",
            example="openai:gpt-4"
        )

        error_str = str(error)

        assert "Invalid input" in error_str
        assert "📋 Expected format: provider:model-name" in error_str
        assert "💡 Example: openai:gpt-4" in error_str
        assert "🎯 Field: model" in error_str


class TestConfigSetupWizardMode:
    """Test the enhanced config setup wizard functionality."""

    @pytest.mark.asyncio
    async def test_config_setup_wizard_mode_parameter(self, mock_state_manager):
        """Test that config setup accepts wizard_mode parameter."""
        config_setup = ConfigSetup(mock_state_manager)

        # Mock the necessary components
        with patch('tunacode.utils.system.get_device_id', return_value="test-device"):
            with patch('tunacode.utils.user_configuration.load_config', return_value=None):
                with patch.object(config_setup, '_onboarding_wizard', new_callable=AsyncMock) as mock_wizard:
                    with patch('tunacode.utils.user_configuration.save_config'):

                        # Test that wizard mode calls the wizard method
                        await config_setup.execute(force_setup=True, wizard_mode=True)

                        assert mock_wizard.called

    @pytest.mark.asyncio
    async def test_config_setup_regular_mode(self, mock_state_manager):
        """Test that config setup uses regular onboarding when not in wizard mode."""
        config_setup = ConfigSetup(mock_state_manager)

        # Mock the necessary components
        with patch('tunacode.utils.system.get_device_id', return_value="test-device"):
            with patch('tunacode.utils.user_configuration.load_config', return_value=None):
                with patch.object(config_setup, '_onboarding', new_callable=AsyncMock) as mock_onboarding:
                    with patch('tunacode.utils.user_configuration.save_config'):

                        # Test that regular mode calls the regular onboarding method
                        await config_setup.execute(force_setup=True, wizard_mode=False)

                        assert mock_onboarding.called


class TestOnboardingIntegration:
    """Test integration between onboarding components."""

    @pytest.mark.asyncio
    async def test_tutorial_manager_progress_tracking(self, mock_state_manager):
        """Test that tutorial manager tracks progress correctly."""
        from tunacode.tutorial.steps import load_tutorial_progress, save_tutorial_progress

        # Save some progress
        save_tutorial_progress(mock_state_manager, "basic_interaction", ["welcome"])

        # Load and verify progress
        progress = load_tutorial_progress(mock_state_manager)

        assert progress["current_step"] == "basic_interaction"
        assert "welcome" in progress["completed_steps"]

    def test_tutorial_completion_marking(self, mock_state_manager):
        """Test that tutorial completion is properly marked."""
        from tunacode.tutorial.steps import is_tutorial_completed, mark_tutorial_completed

        # Initially not completed
        assert not is_tutorial_completed(mock_state_manager)

        # Mark as completed
        mark_tutorial_completed(mock_state_manager)

        # Verify completion
        assert is_tutorial_completed(mock_state_manager)

        # Verify completion flag is set
        settings = mock_state_manager.session.user_config["settings"]
        assert settings.get("tutorial_completed") is True
