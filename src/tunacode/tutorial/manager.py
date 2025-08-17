"""Tutorial manager for coordinating the TunaCode tutorial experience."""

import logging
from typing import Any, Dict

from ..types import StateManager
from ..ui import console as ui
from .steps import (
    TutorialStepResult,
    create_tutorial_steps,
    get_tutorial_completion_key,
    is_first_time_user,
    is_tutorial_completed,
    is_tutorial_declined,
    load_tutorial_progress,
    mark_tutorial_completed,
    mark_tutorial_declined,
    save_tutorial_progress,
)

logger = logging.getLogger(__name__)


class TutorialManager:
    """Manages the tutorial experience for TunaCode users."""

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.steps = create_tutorial_steps()
        self.step_order = [
            "welcome",
            "basic_interaction",
            "file_operations",
            "commands",
            "best_practices",
            "completion"
        ]

    async def should_offer_tutorial(self) -> bool:
        """Determine if we should offer the tutorial to the user."""
        # Don't offer if already completed or declined
        if is_tutorial_completed(self.state_manager):
            return False

        if is_tutorial_declined(self.state_manager):
            return False

        # Check if tutorial is enabled in settings
        settings = self.state_manager.session.user_config.get("settings", {})
        tutorial_enabled = settings.get("enable_tutorial", True)

        if not tutorial_enabled:
            return False

        # Only offer to first-time users (installed within last 7 days)
        if not is_first_time_user(self.state_manager):
            return False

        # Check if this is a fresh session (no significant interaction yet)
        message_count = len(self.state_manager.session.messages)

        # Offer tutorial if user has minimal interaction history
        return message_count < 3

    async def offer_tutorial(self) -> bool:
        """Offer the tutorial to the user and return whether they accepted."""
        await ui.line()

        message = (
            "👋 Welcome to TunaCode! It looks like you're new here.\n\n"
            "Would you like a quick interactive tutorial to get started?\n"
            "It takes about 5 minutes and covers the essential features.\n\n"
            "You can always access it later with [green]/quickstart[/green]"
        )

        await ui.panel("🎓 Tutorial Available", message, border_style="yellow")

        choice = await ui.input(
            "tutorial_offer",
            pretext="  → Start tutorial? [Y/n]: ",
            state_manager=self.state_manager,
        )

        choice = choice.strip().lower()

        if choice in ['n', 'no', 'false']:
            await ui.muted("Tutorial skipped. Use [green]/quickstart[/green] anytime to start it!")
            # Mark as declined so we don't ask again
            mark_tutorial_declined(self.state_manager)

            # Save the configuration to persist the declined status
            try:
                from ..utils import user_configuration
                user_configuration.save_config(self.state_manager)
            except Exception as e:
                logger.warning(f"Failed to save tutorial declined status: {e}")

            return False

        return True

    async def run_tutorial(self, resume: bool = False) -> bool:
        """
        Run the complete tutorial experience.

        Args:
            resume: If True, resume from where the user left off

        Returns:
            True if tutorial was completed, False if interrupted
        """
        try:
            progress = load_tutorial_progress(self.state_manager) if resume else None
            current_step_id = progress.get("current_step", "welcome") if progress else "welcome"
            completed_steps = progress.get("completed_steps", []) if progress else []

            if resume and progress:
                await ui.info(f"📖 Resuming tutorial from: {current_step_id}")

            # Find starting position
            start_index = 0
            if current_step_id in self.step_order:
                start_index = self.step_order.index(current_step_id)

            # Execute tutorial steps
            for i in range(start_index, len(self.step_order)):
                step_id = self.step_order[i]

                if step_id not in self.steps:
                    logger.warning(f"Tutorial step '{step_id}' not found")
                    continue

                step = self.steps[step_id]

                # Skip if already completed (when resuming)
                if step_id in completed_steps:
                    continue

                result = await step.execute(self.state_manager)

                if result == TutorialStepResult.EXIT:
                    # Save progress and exit
                    save_tutorial_progress(self.state_manager, step_id, completed_steps)
                    await ui.info("📚 Tutorial paused. Use [green]/quickstart[/green] to resume!")
                    return False

                elif result == TutorialStepResult.RETRY:
                    # Retry the current step
                    i -= 1
                    continue

                elif result == TutorialStepResult.SKIPPED:
                    await ui.muted(f"⏭️  Skipped: {step.content.title}")

                elif result == TutorialStepResult.COMPLETED:
                    completed_steps.append(step_id)
                    await ui.success(f"✅ Completed: {step.content.title}")

                # Save progress after each step
                save_tutorial_progress(self.state_manager, step_id, completed_steps)

            # Tutorial completed
            mark_tutorial_completed(self.state_manager)

            # Save the configuration
            try:
                from ..utils import user_configuration
                user_configuration.save_config(self.state_manager)
            except Exception as e:
                logger.warning(f"Failed to save tutorial completion: {e}")

            await ui.line()
            await ui.success("🎉 Tutorial completed! You're ready to use TunaCode effectively.")
            await ui.muted("Use [green]/help[/green] to explore more commands and features.")

            return True

        except Exception as e:
            logger.error(f"Tutorial error: {e}")
            await ui.error(f"Tutorial encountered an error: {str(e)}")
            return False

    def get_tutorial_status(self) -> Dict[str, Any]:
        """Get the current tutorial status and progress."""
        if is_tutorial_completed(self.state_manager):
            return {
                "completed": True,
                "current_step": None,
                "completed_steps": self.step_order,
                "total_steps": len(self.step_order)
            }

        progress = load_tutorial_progress(self.state_manager)
        return {
            "completed": False,
            "current_step": progress.get("current_step", "welcome"),
            "completed_steps": progress.get("completed_steps", []),
            "total_steps": len(self.step_order),
            "progress_percentage": len(progress.get("completed_steps", [])) / len(self.step_order) * 100
        }

    async def reset_tutorial(self) -> None:
        """Reset tutorial progress and allow it to be taken again."""
        settings = self.state_manager.session.user_config.get("settings", {})

        # Remove completion and progress markers
        if get_tutorial_completion_key() in settings:
            del settings[get_tutorial_completion_key()]

        if "tutorial_progress" in settings:
            del settings["tutorial_progress"]

        # Save the configuration
        try:
            from ..utils import user_configuration
            user_configuration.save_config(self.state_manager)
            await ui.success("📚 Tutorial reset! You can take it again anytime.")
        except Exception as e:
            logger.warning(f"Failed to save tutorial reset: {e}")
            await ui.warning("Tutorial reset, but changes may not persist.")
