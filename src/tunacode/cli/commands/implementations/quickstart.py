"""QuickStart command for TunaCode CLI - Interactive onboarding tutorial."""

from typing import List

from ....types import CommandContext
from ....ui import console as ui
from ..base import CommandCategory, CommandSpec, SimpleCommand


class QuickStartCommand(SimpleCommand):
    """Interactive quickstart tutorial for new users."""

    spec = CommandSpec(
        name="quickstart",
        aliases=["/quickstart", "/qs"],
        description="Interactive tutorial for getting started with TunaCode",
        category=CommandCategory.SYSTEM,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        """Run the interactive quickstart tutorial."""
        await ui.line()

        # Welcome and overview
        welcome_message = (
            "🚀 Welcome to the TunaCode QuickStart Tutorial!\n\n"
            "This tutorial will show you the core features in just a few minutes:\n"
            "• Basic AI interactions\n"
            "• File operations\n"
            "• Useful commands\n"
            "• Pro tips for efficient coding\n\n"
            "Ready to get started?"
        )
        await ui.panel("🎯 QuickStart Tutorial", welcome_message, border_style="cyan")

        # Get user confirmation
        choice = await ui.input(
            "quickstart_confirm",
            pretext="  → Continue with tutorial? [Y/n]: ",
            state_manager=context.state_manager,
        )

        if choice.strip().lower() in ['n', 'no', 'false']:
            await ui.info("Tutorial cancelled. Type [green]/quickstart[/green] anytime to try again!")
            return

        # Step 1: Basic AI interaction
        await self._step1_basic_interaction(context)

        # Step 2: File operations
        await self._step2_file_operations(context)

        # Step 3: Essential commands
        await self._step3_essential_commands(context)

        # Step 4: Pro tips
        await self._step4_pro_tips(context)

        # Completion
        await self._tutorial_completion(context)

    async def _step1_basic_interaction(self, context: CommandContext) -> None:
        """Step 1: Basic AI interaction demo."""
        await ui.line()

        message = (
            "📝 Step 1: Basic AI Interaction\n\n"
            "TunaCode is your AI coding assistant. You can ask questions in natural language.\n\n"
            "Try these examples:\n"
            "• \"Explain what this function does\"\n"
            "• \"Help me fix this bug\"\n"
            "• \"Create a Python function to calculate fibonacci\"\n"
            "• \"Review my code for improvements\"\n\n"
            "💡 Tip: Be specific about what you want!"
        )
        await ui.panel("📝 Basic Interaction", message, border_style="green")

        choice = await ui.input(
            "step1_continue",
            pretext="  → Ready for the next step? [Y/n]: ",
            state_manager=context.state_manager,
        )

        if choice.strip().lower() in ['n', 'no']:
            await ui.muted("Taking a break. Type [green]/quickstart[/green] to resume anytime!")
            return

    async def _step2_file_operations(self, context: CommandContext) -> None:
        """Step 2: File operations demo."""
        await ui.line()

        message = (
            "📁 Step 2: File Operations\n\n"
            "TunaCode can read, write, and modify files directly:\n\n"
            "File reading:\n"
            "• \"Read the main.py file\"\n"
            "• \"Show me the config.json file\"\n\n"
            "File writing:\n"
            "• \"Create a new file called utils.py with helper functions\"\n"
            "• \"Update the README with installation instructions\"\n\n"
            "File analysis:\n"
            "• \"Find all TODO comments in the codebase\"\n"
            "• \"List all Python files in the src directory\"\n\n"
            "💡 Tip: TunaCode automatically tracks files you mention!"
        )
        await ui.panel("📁 File Operations", message, border_style="blue")

        choice = await ui.input(
            "step2_continue",
            pretext="  → Continue to commands? [Y/n]: ",
            state_manager=context.state_manager,
        )

        if choice.strip().lower() in ['n', 'no']:
            await ui.muted("Tutorial paused. Use [green]/quickstart[/green] to continue!")
            return

    async def _step3_essential_commands(self, context: CommandContext) -> None:
        """Step 3: Essential commands overview."""
        await ui.line()

        message = (
            "⚡ Step 3: Essential Commands\n\n"
            "TunaCode has many useful slash commands:\n\n"
            "Core commands:\n"
            "• [green]/help[/green] - Show all available commands\n"
            "• [green]/clear[/green] - Clear conversation history\n"
            "• [green]/model[/green] - Switch AI models\n\n"
            "Development commands:\n"
            "• [green]/branch[/green] - Create git branch for changes\n"
            "• [green]/compact[/green] - Summarize long conversations\n"
            "• [green]/fix[/green] - Get help with errors\n\n"
            "Productivity:\n"
            "• [green]/thoughts[/green] - See AI reasoning (debug mode)\n"
            "• [green]/streaming[/green] - Toggle response streaming\n\n"
            "💡 Tip: Commands start with / and can be tab-completed!"
        )
        await ui.panel("⚡ Essential Commands", message, border_style="yellow")

        choice = await ui.input(
            "step3_continue",
            pretext="  → Ready for pro tips? [Y/n]: ",
            state_manager=context.state_manager,
        )

        if choice.strip().lower() in ['n', 'no']:
            await ui.muted("Almost done! Type [green]/quickstart[/green] to finish anytime!")
            return

    async def _step4_pro_tips(self, context: CommandContext) -> None:
        """Step 4: Pro tips for efficient usage."""
        await ui.line()

        message = (
            "🏆 Step 4: Pro Tips\n\n"
            "Level up your TunaCode usage:\n\n"
            "Context management:\n"
            "• Reference files: \"Look at src/main.py and explain the login function\"\n"
            "• Use specific language: \"Python function\" vs \"function\"\n"
            "• Break down complex tasks into steps\n\n"
            "Efficiency tricks:\n"
            "• Use Ctrl+C to interrupt long responses\n"
            "• Press Up arrow to edit previous messages\n"
            "• Multiline input with Shift+Enter\n\n"
            "Best practices:\n"
            "• Be specific about requirements\n"
            "• Ask for explanations when learning\n"
            "• Use [green]/branch[/green] before making changes\n\n"
            "💡 Pro tip: TunaCode learns your coding style over time!"
        )
        await ui.panel("🏆 Pro Tips", message, border_style="magenta")

    async def _tutorial_completion(self, context: CommandContext) -> None:
        """Tutorial completion and next steps."""
        await ui.line()

        completion_message = (
            "🎉 Congratulations! You've completed the QuickStart tutorial!\n\n"
            "You now know:\n"
            "• How to interact with TunaCode naturally\n"
            "• File operations and code analysis\n"
            "• Essential commands for productivity\n"
            "• Pro tips for efficient coding\n\n"
            "Next steps:\n"
            "• Try asking TunaCode to help with your current project\n"
            "• Explore [green]/help[/green] for more commands\n"
            "• Check out the documentation for advanced features\n\n"
            "Happy coding! 🚀"
        )
        await ui.panel("🎉 Tutorial Complete!", completion_message, border_style="green")

        # Mark tutorial as completed in user config
        if "settings" not in context.state_manager.session.user_config:
            context.state_manager.session.user_config["settings"] = {}

        context.state_manager.session.user_config["settings"]["quickstart_completed"] = True

        # Save the configuration
        try:
            from tunacode.utils import user_configuration
            user_configuration.save_config(context.state_manager)
        except Exception:
            # Don't fail if we can't save
            pass

        await ui.success("💾 Progress saved! You won't see this tutorial prompt again.")
        await ui.muted("Use [green]/quickstart[/green] anytime to review the tutorial.")
