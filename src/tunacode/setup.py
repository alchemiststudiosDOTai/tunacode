"""
Module: tunacode.setup

Package setup and metadata configuration for the TunaCode CLI.
Provides high-level setup functions for initializing the application and its agents.
"""

from typing import Any, Optional

from tunacode.core.setup import (
    AgentSetup,
    ConfigSetup,
    EnvironmentSetup,
    GitSafetySetup,
    SetupCoordinator,
    TemplateSetup,
)
from tunacode.core.state import StateManager


async def setup(
    run_setup: bool, state_manager: StateManager, cli_config: dict = None, wizard_mode: bool = False
) -> None:
    """
    Setup TunaCode on startup using the new setup coordinator.

    Args:
        run_setup (bool): If True, force run the setup process, resetting current config.
        state_manager (StateManager): The state manager instance.
        cli_config (dict): Optional CLI configuration with baseurl, model, and key.
        wizard_mode (bool): If True, run interactive setup wizard.
    """
    coordinator = SetupCoordinator(state_manager)

    # Register setup steps in order
    config_setup = ConfigSetup(state_manager)
    if cli_config:
        config_setup.cli_config = cli_config
    coordinator.register_step(config_setup)
    coordinator.register_step(EnvironmentSetup(state_manager))
    coordinator.register_step(TemplateSetup(state_manager))
    coordinator.register_step(GitSafetySetup(state_manager))

    # Run all setup steps
    await coordinator.run_setup(force_setup=run_setup, wizard_mode=wizard_mode)


async def setup_agent(agent: Optional[Any], state_manager: StateManager) -> None:
    """
    Setup the agent separately.

    This is called from other parts of the codebase when an agent needs to be initialized.

    Args:
        agent: The agent instance to initialize.
        state_manager (StateManager): The state manager instance.
    """
    if agent is not None:
        agent_setup = AgentSetup(state_manager, agent)
        if await agent_setup.should_run():
            await agent_setup.execute()
            if not await agent_setup.validate():
                raise RuntimeError("Agent setup failed validation")
