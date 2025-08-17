"""Module: tunacode.core.setup.base

Base setup step abstraction for the TunaCode CLI initialization process.
Provides common interface and functionality for all setup steps.
"""

from abc import ABC, abstractmethod

from tunacode.core.state import StateManager


class BaseSetup(ABC):
    """Base class for all setup steps."""

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this setup step."""
        pass

    @abstractmethod
    async def should_run(self, _force_setup: bool = False) -> bool:
        """Determine if this setup step should run."""
        pass

    @abstractmethod
    async def execute(self, _force_setup: bool = False, _wizard_mode: bool = False) -> None:
        """Execute the setup step."""
        pass

    @abstractmethod
    async def validate(self) -> bool:
        """Validate that the setup was successful."""
        pass
