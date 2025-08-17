"""Module: tunacode.core.setup.coordinator

Setup orchestration and coordination for the TunaCode CLI.
Manages the execution order and validation of all registered setup steps.
"""

from typing import List

from tunacode.core.setup.base import BaseSetup
from tunacode.core.state import StateManager
from tunacode.ui import console as ui


class SetupCoordinator:
    """Coordinator for running all setup steps in order."""

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.setup_steps: List[BaseSetup] = []

    def register_step(self, step: BaseSetup) -> None:
        """Register a setup step to be run."""
        self.setup_steps.append(step)

    async def run_setup(self, force_setup: bool = False, wizard_mode: bool = False) -> None:
        """Run all registered setup steps concurrently if possible."""
        # Run should_run checks sequentially (they may depend on order)
        steps_to_run = []
        for step in self.setup_steps:
            try:
                if await step.should_run(force_setup):
                    steps_to_run.append(step)
            except Exception as e:
                await ui.error(
                    f"Setup failed at step '{getattr(step, 'name', repr(step))}': {str(e)}"
                )
                raise
        # Run all .execute(force_setup) in parallel where possible (independent steps)
        from asyncio import gather

        try:
            await gather(*(step.execute(force_setup, wizard_mode) for step in steps_to_run))
            # Now validate all sequentially: if any fail, raise error
            for step in steps_to_run:
                if not await step.validate():
                    await ui.error(f"Setup validation failed: {step.name}")
                    raise RuntimeError(f"Setup step '{step.name}' failed validation")
        except Exception as e:
            await ui.error(f"Setup error: {str(e)}")
            raise

    async def run_setup_wizard(self) -> None:
        """Run setup in interactive wizard mode with enhanced guidance."""
        await ui.muted("🧙‍♂️ Starting setup wizard...")
        await self.run_setup(force_setup=True, wizard_mode=True)

    def clear_steps(self) -> None:
        """Clear all registered setup steps."""
        self.setup_steps.clear()
