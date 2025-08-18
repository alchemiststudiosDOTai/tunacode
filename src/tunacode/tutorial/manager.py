"""
Module: tunacode.tutorial.manager

Tutorial manager for orchestrating the TunaCode onboarding experience.
"""

import logging

from ..types import StateManager
from ..ui import console as ui
from .steps import (
    create_tutorial_steps,
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
        self.steps = [
            "welcome",
            "basic_chat",
            "file_operations",
            "commands",
            "best_practices",
            "completion",
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
        await ui.panel(
            "🎯 Welcome to TunaCode!",
            "Would you like a quick 2-minute tutorial to get started?\n"
            "This will help you learn the basics and start coding faster.",
            border_style="cyan",
        )

        choice = await ui.input(
            "tutorial_offer",
            pretext="  → Start tutorial? [Y/n]: ",
            state_manager=self.state_manager,
        )

        choice = choice.strip().lower()

        if choice in ["n", "no", "false"]:
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
            resume: If True, resume from saved progress

        Returns:
            True if tutorial completed successfully, False if cancelled
        """
        try:
            from .content import TUTORIAL_CONTENT

            # Load progress or start from beginning
            current_step = load_tutorial_progress(self.state_manager) if resume else 0
            steps = create_tutorial_steps()

            await ui.line()
            await ui.info(f"🎯 Starting TunaCode Tutorial ({len(steps)} steps)")
            await ui.line()

            while current_step < len(steps):
                step_id = steps[current_step]
                step_content = TUTORIAL_CONTENT.get(step_id, {})

                if not step_content:
                    logger.warning(f"Missing content for tutorial step: {step_id}")
                    current_step += 1
                    continue

                # Display step content
                await ui.panel(
                    f"Step {current_step + 1}/{len(steps)}: {step_content.get('title', step_id)}",
                    step_content.get("content", ""),
                    border_style="cyan",
                )

                # Get user input for progression
                action_text = step_content.get("action", "Press Enter to continue...")
                try:
                    user_input = await ui.input(
                        f"tutorial_step_{current_step}",
                        pretext=f"  → {action_text} ",
                        state_manager=self.state_manager,
                    )

                    # Allow users to exit tutorial early
                    if user_input.lower() in ["quit", "exit", "skip"]:
                        await ui.info(
                            "Tutorial cancelled. Use [green]/quickstart[/green] to restart anytime!"
                        )
                        return False

                except Exception as e:
                    logger.warning(f"Tutorial interrupted: {e}")
                    # Save progress before exiting
                    save_tutorial_progress(self.state_manager, current_step)
                    await ui.info("Tutorial paused. Use [green]/quickstart[/green] to resume!")
                    return False

                current_step += 1
                save_tutorial_progress(self.state_manager, current_step)

            # Tutorial completed successfully
            mark_tutorial_completed(self.state_manager)

            # Save the completion status
            try:
                from ..utils import user_configuration

                user_configuration.save_config(self.state_manager)
            except Exception as e:
                logger.warning(f"Failed to save tutorial completion status: {e}")

            await ui.line()
            await ui.success("🎉 Tutorial completed! You're ready to use TunaCode.")
            await ui.line()

            return True

        except Exception as e:
            logger.error(f"Tutorial failed: {e}")
            await ui.error(f"Tutorial encountered an error: {e}")
            return False
