"""Development-focused commands for TunaCode CLI."""

import os
import subprocess
from typing import List

from ....types import CommandContext, CommandResult
from ....ui import console as ui
from ..base import CommandCategory, CommandSpec, SimpleCommand


class BranchCommand(SimpleCommand):
    """Create and switch to a new git branch."""

    spec = CommandSpec(
        name="branch",
        aliases=["/branch"],
        description="Create and switch to a new git branch",
        category=CommandCategory.DEVELOPMENT,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        if not args:
            await ui.error("Usage: /branch <branch-name>")
            return

        if not os.path.exists(".git"):
            await ui.error("Not a git repository")
            return

        branch_name = args[0]

        try:
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            await ui.success(f"Switched to new branch '{branch_name}'")
        except subprocess.TimeoutExpired:
            await ui.error("Git command timed out")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            await ui.error(f"Git error: {error_msg}")
        except FileNotFoundError:
            await ui.error("Git executable not found")


class InitCommand(SimpleCommand):
    """Creates or updates AGENTS.md with project-specific context."""

    spec = CommandSpec(
        name="/init",
        aliases=[],
        description="Analyze codebase and create/update AGENTS.md file",
        category=CommandCategory.DEVELOPMENT,
    )

    async def execute(self, args, context: CommandContext) -> CommandResult:
        """Execute the init command."""
        # Minimal implementation to make test pass
        prompt = """Please analyze this codebase and create a AGENTS.md file containing:
1. Build/lint/test commands - especially for running a single test
2. Code style guidelines including imports, formatting, types, naming conventions, error handling, etc.

The file you create will be given to agentic coding agents (such as yourself) that operate in this repository.
Make it about 20 lines long.
If there's already a AGENTS.md, improve it.
If there are Cursor rules (in .cursor/rules/ or .cursorrules) or Copilot rules (in .github/copilot-instructions.md),
make sure to include them."""

        # Call the agent to analyze and create/update the file
        if context.process_request:
            await context.process_request(
                prompt, context.state_manager.session.current_model, context.state_manager
            )

        return None
