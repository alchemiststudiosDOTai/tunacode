"""
Test suite for TunaCode onboarding features including tutorial system,
quickstart command, and first-time user detection.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tunacode.cli.commands.implementations.quickstart import QuickStartCommand
from tunacode.tutorial import TutorialManager
from tunacode.tutorial.content import TUTORIAL_CONTENT, get_tutorial_steps
from tunacode.tutorial.steps import (
    create_tutorial_steps,
    get_tutorial_completion_key,
    get_tutorial_declined_key,
    get_tutorial_progress_key,
    is_first_time_user,
    is_tutorial_completed,
    is_tutorial_declined,
    load_tutorial_progress,
    mark_tutorial_completed,
    mark_tutorial_declined,
    save_tutorial_progress,
)
from tunacode.types import StateManager


@pytest.fixture
def mock_state_manager():
    """Create a mock StateManager for testing."""
    state_manager = MagicMock(spec=StateManager)
    state_manager.session = MagicMock()
    state_manager.session.user_config = {}
    state_manager.session.messages = []
    return state_manager


@pytest.fixture
def mock_ui():
    """Create a mock UI for testing."""
    ui = MagicMock()
    ui.panel = AsyncMock()
    ui.input = AsyncMock()
    ui.info = AsyncMock()
    ui.success = AsyncMock()
    ui.error = AsyncMock()
    ui.muted = AsyncMock()
    ui.line = AsyncMock()
    return ui


@pytest.fixture
def tutorial_manager(mock_state_manager):
    """Create a TutorialManager instance for testing."""
    return TutorialManager(mock_state_manager)


class TestTutorialStepManagement:
    """Test tutorial step creation and progression."""

    def test_create_tutorial_steps(self):
        """Test tutorial step creation returns correct steps."""
        steps = create_tutorial_steps()
        expected_steps = [
            "welcome",
            "basic_chat",
            "file_operations",
            "commands",
            "best_practices",
            "completion",
        ]
        assert steps == expected_steps
        assert len(steps) == 6

    def test_get_tutorial_steps_content(self):
        """Test tutorial content matches expected steps."""
        steps = get_tutorial_steps()
        for step in steps:
            assert step in TUTORIAL_CONTENT
            assert "title" in TUTORIAL_CONTENT[step]
            assert "content" in TUTORIAL_CONTENT[step]
            assert "action" in TUTORIAL_CONTENT[step]


class TestTutorialProgressTracking:
    """Test tutorial progress saving and loading."""

    def test_tutorial_completion_tracking(self, mock_state_manager):
        """Test marking and checking tutorial completion."""
        # Initially not completed
        assert not is_tutorial_completed(mock_state_manager)

        # Mark as completed
        mark_tutorial_completed(mock_state_manager)
        assert is_tutorial_completed(mock_state_manager)

        # Check settings were created
        assert "settings" in mock_state_manager.session.user_config
        assert mock_state_manager.session.user_config["settings"][get_tutorial_completion_key()]

    def test_tutorial_declined_tracking(self, mock_state_manager):
        """Test marking and checking tutorial declined status."""
        # Initially not declined
        assert not is_tutorial_declined(mock_state_manager)

        # Mark as declined
        mark_tutorial_declined(mock_state_manager)
        assert is_tutorial_declined(mock_state_manager)

        # Check settings were created
        assert "settings" in mock_state_manager.session.user_config
        assert mock_state_manager.session.user_config["settings"][get_tutorial_declined_key()]

    def test_tutorial_progress_saving_loading(self, mock_state_manager):
        """Test saving and loading tutorial progress."""
        # Initially no progress
        progress = load_tutorial_progress(mock_state_manager)
        assert progress == 0

        # Save progress
        save_tutorial_progress(mock_state_manager, 3)
        progress = load_tutorial_progress(mock_state_manager)
        assert progress == 3

        # Check settings were created
        assert "settings" in mock_state_manager.session.user_config
        assert mock_state_manager.session.user_config["settings"][get_tutorial_progress_key()] == 3

    def test_completion_clears_progress(self, mock_state_manager):
        """Test that marking tutorial complete clears any saved progress."""
        # Save some progress first
        save_tutorial_progress(mock_state_manager, 2)
        assert load_tutorial_progress(mock_state_manager) == 2

        # Mark as completed
        mark_tutorial_completed(mock_state_manager)

        # Progress should be cleared
        progress_key = get_tutorial_progress_key()
        settings = mock_state_manager.session.user_config.get("settings", {})
        assert progress_key not in settings

    def test_declined_clears_progress(self, mock_state_manager):
        """Test that marking tutorial declined clears any saved progress."""
        # Save some progress first
        save_tutorial_progress(mock_state_manager, 4)
        assert load_tutorial_progress(mock_state_manager) == 4

        # Mark as declined
        mark_tutorial_declined(mock_state_manager)

        # Progress should be cleared
        progress_key = get_tutorial_progress_key()
        settings = mock_state_manager.session.user_config.get("settings", {})
        assert progress_key not in settings


class TestFirstTimeUserDetection:
    """Test first-time user detection logic."""

    def test_first_time_user_no_installation_date(self, mock_state_manager):
        """Test that users without installation date are considered experienced."""
        # No installation date set
        result = is_first_time_user(mock_state_manager)
        assert not result

    def test_first_time_user_recent_installation(self, mock_state_manager):
        """Test that recently installed users are considered first-time."""
        # Set installation date to 3 days ago
        install_date = datetime.now() - timedelta(days=3)
        mock_state_manager.session.user_config["settings"] = {
            "first_installation_date": install_date.isoformat()
        }

        result = is_first_time_user(mock_state_manager)
        assert result

    def test_first_time_user_old_installation(self, mock_state_manager):
        """Test that users with old installations are not considered first-time."""
        # Set installation date to 10 days ago
        install_date = datetime.now() - timedelta(days=10)
        mock_state_manager.session.user_config["settings"] = {
            "first_installation_date": install_date.isoformat()
        }

        result = is_first_time_user(mock_state_manager)
        assert not result

    def test_first_time_user_invalid_date(self, mock_state_manager):
        """Test that invalid installation dates are handled gracefully."""
        # Set invalid installation date
        mock_state_manager.session.user_config["settings"] = {
            "first_installation_date": "invalid-date"
        }

        result = is_first_time_user(mock_state_manager)
        assert not result


class TestTutorialManager:
    """Test TutorialManager functionality."""

    @pytest.mark.asyncio
    async def test_should_offer_tutorial_completed(self, tutorial_manager, mock_state_manager):
        """Test that tutorial is not offered if already completed."""
        mark_tutorial_completed(mock_state_manager)
        result = await tutorial_manager.should_offer_tutorial()
        assert not result

    @pytest.mark.asyncio
    async def test_should_offer_tutorial_declined(self, tutorial_manager, mock_state_manager):
        """Test that tutorial is not offered if declined."""
        mark_tutorial_declined(mock_state_manager)
        result = await tutorial_manager.should_offer_tutorial()
        assert not result

    @pytest.mark.asyncio
    async def test_should_offer_tutorial_disabled(self, tutorial_manager, mock_state_manager):
        """Test that tutorial is not offered if disabled in settings."""
        mock_state_manager.session.user_config["settings"] = {
            "enable_tutorial": False,
            "first_installation_date": datetime.now().isoformat(),
        }
        result = await tutorial_manager.should_offer_tutorial()
        assert not result

    @pytest.mark.asyncio
    async def test_should_offer_tutorial_not_first_time(self, tutorial_manager, mock_state_manager):
        """Test that tutorial is not offered to experienced users."""
        # Set old installation date
        install_date = datetime.now() - timedelta(days=10)
        mock_state_manager.session.user_config["settings"] = {
            "first_installation_date": install_date.isoformat()
        }
        result = await tutorial_manager.should_offer_tutorial()
        assert not result

    @pytest.mark.asyncio
    async def test_should_offer_tutorial_many_messages(self, tutorial_manager, mock_state_manager):
        """Test that tutorial is not offered to users with many messages."""
        # Set recent installation but many messages
        install_date = datetime.now() - timedelta(days=1)
        mock_state_manager.session.user_config["settings"] = {
            "first_installation_date": install_date.isoformat()
        }
        mock_state_manager.session.messages = ["msg"] * 5  # More than 3 messages

        result = await tutorial_manager.should_offer_tutorial()
        assert not result

    @pytest.mark.asyncio
    async def test_should_offer_tutorial_valid_conditions(
        self, tutorial_manager, mock_state_manager
    ):
        """Test that tutorial is offered under valid conditions."""
        # Set recent installation, few messages, tutorial enabled
        install_date = datetime.now() - timedelta(days=1)
        mock_state_manager.session.user_config["settings"] = {
            "first_installation_date": install_date.isoformat(),
            "enable_tutorial": True,
        }
        mock_state_manager.session.messages = ["msg"]  # Less than 3 messages

        result = await tutorial_manager.should_offer_tutorial()
        assert result

    @pytest.mark.asyncio
    async def test_offer_tutorial_accepted(self, tutorial_manager, mock_ui):
        """Test tutorial offer when user accepts."""
        mock_ui.input.return_value = "y"

        with patch.object(tutorial_manager, "state_manager") as mock_sm:
            mock_sm.session.user_config = {}
            result = await tutorial_manager.offer_tutorial()

        assert result
        mock_ui.panel.assert_called_once()
        mock_ui.input.assert_called_once()

    @pytest.mark.asyncio
    async def test_offer_tutorial_declined(self, tutorial_manager, mock_ui):
        """Test tutorial offer when user declines."""
        mock_ui.input.return_value = "n"

        with patch.object(tutorial_manager, "state_manager") as mock_sm:
            mock_sm.session.user_config = {}
            with patch("tunacode.tutorial.manager.mark_tutorial_declined") as mock_decline:
                result = await tutorial_manager.offer_tutorial()

        assert not result
        mock_decline.assert_called_once()
        mock_ui.muted.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_tutorial_success(self, tutorial_manager, mock_ui):
        """Test successful tutorial completion."""
        with patch.object(tutorial_manager, "state_manager") as mock_sm:
            mock_sm.session.user_config = {}
            with patch("tunacode.tutorial.manager.ui", mock_ui):
                with patch("tunacode.tutorial.manager.mark_tutorial_completed") as mock_complete:
                    # Mock user advancing through all steps
                    mock_ui.input.return_value = ""  # Just press enter
                    result = await tutorial_manager.run_tutorial()

        assert result
        mock_complete.assert_called_once()
        mock_ui.success.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_tutorial_cancelled(self, tutorial_manager, mock_ui):
        """Test tutorial cancellation by user."""
        with patch.object(tutorial_manager, "state_manager") as mock_sm:
            mock_sm.session.user_config = {}
            with patch("tunacode.tutorial.manager.ui", mock_ui):
                # User types 'quit' to cancel
                mock_ui.input.return_value = "quit"
                result = await tutorial_manager.run_tutorial()

        assert not result
        mock_ui.info.assert_called()


class TestQuickStartCommand:
    """Test QuickStart command functionality."""

    @pytest.mark.asyncio
    async def test_quickstart_command_success(self, mock_ui):
        """Test successful quickstart command execution."""
        # Create mock context
        context = MagicMock()
        context.ui = mock_ui
        context.state_manager = MagicMock()

        # Create command instance
        command = QuickStartCommand()

        # Mock tutorial manager
        with patch(
            "tunacode.cli.commands.implementations.quickstart.TutorialManager"
        ) as mock_tutorial_cls:
            mock_tutorial = mock_tutorial_cls.return_value
            mock_tutorial.run_tutorial.return_value = True

            await command.execute(context)

        mock_tutorial_cls.assert_called_once_with(context.state_manager)
        mock_tutorial.run_tutorial.assert_called_once()
        mock_ui.success.assert_called_once()

    @pytest.mark.asyncio
    async def test_quickstart_command_cancelled(self, mock_ui):
        """Test quickstart command when tutorial is cancelled."""
        # Create mock context
        context = MagicMock()
        context.ui = mock_ui
        context.state_manager = MagicMock()

        # Create command instance
        command = QuickStartCommand()

        # Mock tutorial manager
        with patch(
            "tunacode.cli.commands.implementations.quickstart.TutorialManager"
        ) as mock_tutorial_cls:
            mock_tutorial = mock_tutorial_cls.return_value
            mock_tutorial.run_tutorial.return_value = False

            await command.execute(context)

        mock_ui.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_quickstart_command_import_error(self, mock_ui):
        """Test quickstart command when tutorial system is unavailable."""
        # Create mock context
        context = MagicMock()
        context.ui = mock_ui
        context.state_manager = MagicMock()

        # Create command instance
        command = QuickStartCommand()

        # Mock import error
        with patch(
            "tunacode.cli.commands.implementations.quickstart.TutorialManager",
            side_effect=ImportError,
        ):
            await command.execute(context)

        mock_ui.error.assert_called_once_with("Tutorial system is not available")

    def test_quickstart_command_spec(self):
        """Test QuickStart command specification."""
        command = QuickStartCommand()

        assert command.spec.name == "quickstart"
        assert "/quickstart" in command.spec.aliases
        assert "/qs" in command.spec.aliases
        assert "tutorial" in command.spec.description.lower()


class TestTutorialContent:
    """Test tutorial content structure and completeness."""

    def test_tutorial_content_structure(self):
        """Test that all tutorial content has required fields."""
        steps = get_tutorial_steps()

        for step_id in steps:
            assert step_id in TUTORIAL_CONTENT
            content = TUTORIAL_CONTENT[step_id]

            # Check required fields
            assert "title" in content
            assert "content" in content
            assert "action" in content

            # Check field types
            assert isinstance(content["title"], str)
            assert isinstance(content["content"], str)
            assert isinstance(content["action"], str)

            # Check content is not empty
            assert content["title"].strip()
            assert content["content"].strip()
            assert content["action"].strip()

    def test_tutorial_content_consistency(self):
        """Test that tutorial steps and content are consistent."""
        steps = get_tutorial_steps()
        content_keys = set(TUTORIAL_CONTENT.keys())
        step_set = set(steps)

        # All steps should have content
        assert step_set.issubset(content_keys)

        # No extra content without corresponding steps
        assert content_keys == step_set

    def test_tutorial_welcome_step(self):
        """Test specific content of welcome step."""
        welcome = TUTORIAL_CONTENT["welcome"]

        assert "Welcome" in welcome["title"]
        assert "TunaCode" in welcome["content"]
        assert "tutorial" in welcome["content"].lower()

    def test_tutorial_completion_step(self):
        """Test specific content of completion step."""
        completion = TUTORIAL_CONTENT["completion"]

        assert "Complete" in completion["title"] or "🎉" in completion["title"]
        assert (
            "Congratulations" in completion["content"] or "ready" in completion["content"].lower()
        )
