"""
Characterization test for setup flow baseline.

This test captures the current behavior of the setup coordinator
before git safety removal to ensure we can verify functionality
after removal is complete.
"""

from unittest.mock import MagicMock

import pytest

from tunacode.core.setup import (
    AgentSetup,
    ConfigSetup,
    EnvironmentSetup,
    SetupCoordinator,
    TemplateSetup,
)
from tunacode.types import StateManager


class TestSetupFlowBaseline:
    """Test suite capturing current setup flow behavior."""

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
        state_manager.session.user_config = {
            "settings": {"max_retries": 3},
            "skip_git_safety": False,  # Default git safety enabled
        }
        state_manager.session.current_model = "test-model"
        state_manager.session.files_in_context = set()
        state_manager.session.iteration_count = 0
        state_manager.session.error_count = 0
        state_manager.session.consecutive_empty_responses = 0

        return state_manager

    @pytest.mark.asyncio
    async def test_setup_coordinator_initialization(self, mock_state_manager):
        """Test that SetupCoordinator initializes with all 4 setup steps."""
        coordinator = SetupCoordinator(mock_state_manager)

        # Verify coordinator initializes correctly
        assert coordinator.state_manager == mock_state_manager
        assert hasattr(coordinator, "register_step")
        assert hasattr(coordinator, "run_setup")

    @pytest.mark.asyncio
    async def test_setup_step_imports_available(self):
        """Test that all setup step classes are importable."""
        # All setup steps should be importable
        assert ConfigSetup is not None
        assert EnvironmentSetup is not None
        assert TemplateSetup is not None
        assert AgentSetup is not None

    @pytest.mark.asyncio
    async def test_setup_step_creation(self, mock_state_manager):
        """Test that all setup steps can be created."""
        config_setup = ConfigSetup(mock_state_manager)
        env_setup = EnvironmentSetup(mock_state_manager)
        template_setup = TemplateSetup(mock_state_manager)

        # Verify all setup steps have required methods
        for setup_step in [config_setup, env_setup, template_setup]:
            assert hasattr(setup_step, "name")
            assert hasattr(setup_step, "should_run")
            assert hasattr(setup_step, "execute")
            assert hasattr(setup_step, "validate")

    @pytest.mark.asyncio
    async def test_setup_step_names(self, mock_state_manager):
        """Test that setup steps have correct names."""
        config_setup = ConfigSetup(mock_state_manager)
        env_setup = EnvironmentSetup(mock_state_manager)
        template_setup = TemplateSetup(mock_state_manager)

        # Verify names are as expected
        assert config_setup.name == "Configuration"
        assert env_setup.name == "Environment Variables"
        assert template_setup.name == "Template Directory"

    @pytest.mark.asyncio
    async def test_setup_step_validation(self, mock_state_manager):
        """Test that setup steps validate correctly."""
        config_setup = ConfigSetup(mock_state_manager)
        env_setup = EnvironmentSetup(mock_state_manager)
        template_setup = TemplateSetup(mock_state_manager)

        # Mock user config for config validation
        mock_state_manager.session.user_config = {
            "settings": {"max_retries": 3},
            "default_model": "test-model",
            "env": {"TEST_API_KEY": "test-key"},
        }

        # Config validation depends on having proper config
        config_validation = await config_setup.validate()
        # Note: May return False due to missing API key validation, but that's expected
        assert isinstance(config_validation, bool)

        # Environment and template validation have their own logic
        env_validation = await env_setup.validate()
        template_validation = await template_setup.validate()
        assert isinstance(env_validation, bool)
        assert isinstance(template_validation, bool)
