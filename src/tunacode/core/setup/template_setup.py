"""Module: tunacode.core.setup.template_setup

Template directory initialization for the TunaCode CLI.
Handles creation of template directories and ensures proper structure.
"""

import platform
from pathlib import Path

from tunacode.core.setup.base import BaseSetup
from tunacode.core.state import StateManager
from tunacode.ui import console as ui


class TemplateSetup(BaseSetup):
    """Setup step for template directory structure."""

    def __init__(self, state_manager: StateManager):
        super().__init__(state_manager)
        # Use same config directory as main configuration
        self.config_dir = Path.home() / ".config" / "tunacode"
        self.template_dir = self.config_dir / "templates"

    @property
    def name(self) -> str:
        return "Template Directory"

    async def should_run(self, force_setup: bool = False) -> bool:
        """Run if template directory doesn't exist or force setup is requested."""
        return force_setup or not self.template_dir.exists()

    async def execute(self, force_setup: bool = False, wizard_mode: bool = False) -> None:
        """Create template directory structure."""
        try:
            # Create main template directory
            self.template_dir.mkdir(parents=True, exist_ok=True)

            # Create subdirectories for organization (optional, for future use)
            subdirs = ["project", "tool", "config"]
            for subdir in subdirs:
                subdir_path = self.template_dir / subdir
                subdir_path.mkdir(exist_ok=True)

            # Set appropriate permissions on Unix-like systems
            if platform.system() != "Windows":
                import os

                os.chmod(self.template_dir, 0o755)
                for subdir in subdirs:
                    os.chmod(self.template_dir / subdir, 0o755)

            await ui.info(f"Created template directory structure at: {self.template_dir}")

        except PermissionError:
            await ui.error(
                f"Permission denied: Cannot create template directory at {self.template_dir}"
            )
            raise
        except OSError as e:
            await ui.error(f"Failed to create template directory: {str(e)}")
            raise

    async def validate(self) -> bool:
        """Validate that template directory exists and is accessible."""
        if not self.template_dir.exists():
            return False

        # Check if directory is writable
        try:
            test_file = self.template_dir / ".test_write"
            test_file.touch()
            test_file.unlink()
            return True
        except Exception:
            return False
