"""Git safety setup to create a working branch for TunaCode."""

import subprocess
from pathlib import Path

from tunacode.core.setup.base import BaseSetup
from tunacode.core.state import StateManager
from tunacode.ui import console as ui
from tunacode.ui.input import input as prompt_input
from tunacode.ui.panels import panel


async def yes_no_prompt(question: str, default: bool = True) -> bool:
    """Simple yes/no prompt."""
    default_text = "[Y/n]" if default else "[y/N]"
    response = await prompt_input(session_key="yes_no", pretext=f"{question} {default_text}: ")

    if not response.strip():
        return default

    return response.lower().strip() in ["y", "yes"]


class GitSafetySetup(BaseSetup):
    """Setup step to create a safe working branch for TunaCode."""

    def __init__(self, state_manager: StateManager):
        super().__init__(state_manager)

    @property
    def name(self) -> str:
        """Return the name of this setup step."""
        return "Git Safety"

    async def should_run(self, _force: bool = False) -> bool:
        """Check if we should run git safety setup."""
        # Always run unless user has explicitly disabled it
        return not self.state_manager.session.user_config.get("skip_git_safety", False)

    async def execute(self, _force: bool = False, _wizard_mode: bool = False) -> None:
        """Create a safety branch for TunaCode operations."""
        try:
            # Check if git is installed
            result = subprocess.run(
                ["git", "--version"], capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                await panel(
                    " Git Not Found",
                    "Git is not installed or not in PATH. TunaCode will modify files directly.\n"
                    "It's strongly recommended to install Git for safety.",
                    border_style="yellow",
                )
                return

            # Check if we're in a git repository
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                check=False,
                cwd=Path.cwd(),
            )

            if result.returncode != 0:
                await panel(
                    " Not a Git Repository",
                    "This directory is not a Git repository. TunaCode will modify files directly.\n"
                    "Consider initializing a Git repository for safety: git init",
                    border_style="yellow",
                )
                return

            # Get current branch name
            result = subprocess.run(
                ["git", "branch", "--show-current"], capture_output=True, text=True, check=True
            )
            current_branch = result.stdout.strip()

            if not current_branch:
                # Detached HEAD state
                await panel(
                    " Detached HEAD State",
                    "You're in a detached HEAD state. TunaCode will continue without creating a branch.",
                    border_style="yellow",
                )
                return

            # Check if we're already on a -tunacode branch
            if current_branch.endswith("-tunacode"):
                await ui.info(f"Already on a TunaCode branch: {current_branch}")
                return

            # Propose new branch name
            new_branch = f"{current_branch}-tunacode"

            # Check if there are uncommitted changes
            result = subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
            )

            has_changes = bool(result.stdout.strip())

            # Ask user if they want to create a safety branch
            message = (
                f"For safety, TunaCode can create a new branch '{new_branch}' based on '{current_branch}'.\n"
                f"This helps protect your work from unintended changes.\n"
            )

            if has_changes:
                message += "\n You have uncommitted changes that will be brought to the new branch."

            create_branch = await yes_no_prompt(f"{message}\n\nCreate safety branch?", default=True)

            if not create_branch:
                # User declined - show warning
                await panel(
                    " Working Without Safety Branch",
                    "You've chosen to work directly on your current branch.\n"
                    "TunaCode will modify files in place. Make sure you have backups!",
                    border_style="red",
                )
                # Save preference
                self.state_manager.session.user_config["skip_git_safety"] = True
                # Save the updated configuration to disk
                try:
                    from tunacode.utils.user_configuration import save_config

                    save_config(self.state_manager)
                except Exception as e:
                    # Log the error but don't fail the setup process
                    import logging

                    logging.warning(f"Failed to save skip_git_safety preference: {e}")
                return

            # Create and checkout the new branch
            try:
                # Check if branch already exists
                result = subprocess.run(
                    ["git", "show-ref", "--verify", f"refs/heads/{new_branch}"],
                    capture_output=True,
                    check=False,
                    text=True,
                )

                if result.returncode == 0:
                    # Branch exists, ask to use it
                    use_existing = await yes_no_prompt(
                        f"Branch '{new_branch}' already exists. Switch to it?", default=True
                    )
                    if use_existing:
                        subprocess.run(["git", "checkout", new_branch], check=True)
                        await ui.success(f"Switched to existing branch: {new_branch}")
                    else:
                        await ui.warning("Continuing on current branch")
                else:
                    # Create new branch
                    subprocess.run(["git", "checkout", "-b", new_branch], check=True)
                    await ui.success(f"Created and switched to new branch: {new_branch}")

            except subprocess.CalledProcessError as e:
                await panel(
                    " Failed to Create Branch",
                    f"Could not create branch '{new_branch}': {str(e)}\n"
                    "Continuing on current branch.",
                    border_style="red",
                )

        except Exception as e:
            # Non-fatal error - just warn the user
            await panel(
                " Git Safety Setup Failed",
                f"Could not set up Git safety: {str(e)}\n"
                "TunaCode will continue without branch protection.",
                border_style="yellow",
            )

    async def validate(self) -> bool:
        """Validate git safety setup - always returns True as this is optional."""
        return True
