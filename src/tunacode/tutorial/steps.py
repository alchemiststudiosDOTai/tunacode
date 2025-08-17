"""Tutorial step definitions and management for TunaCode."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from ..types import StateManager
from ..ui import console as ui
from .content import TUTORIAL_STEPS, TutorialContent


class TutorialStepResult(Enum):
    """Result of executing a tutorial step."""
    COMPLETED = "completed"
    SKIPPED = "skipped"
    RETRY = "retry"
    EXIT = "exit"


@dataclass
class TutorialStep:
    """A single step in the tutorial sequence."""

    step_id: str
    content: TutorialContent
    is_optional: bool = False

    async def execute(self, state_manager: StateManager) -> TutorialStepResult:
        """Execute this tutorial step."""
        await ui.line()

        # Display step content
        message = f"{self.content.description}\n\n"

        if self.content.instructions:
            message += "📋 Key Points:\n"
            for instruction in self.content.instructions:
                message += f"  • {instruction}\n"
            message += "\n"

        if self.content.examples:
            message += "💡 Examples:\n"
            for example in self.content.examples:
                message += f"  • {example}\n"
            message += "\n"

        if self.content.tips:
            message += "🎯 Pro Tips:\n"
            for tip in self.content.tips:
                message += f"  • {tip}\n"
            message += "\n"

        if self.content.next_action:
            message += f"👉 Next: {self.content.next_action}"

        await ui.panel(f"📚 {self.content.title}", message, border_style="cyan")

        # Get user input
        prompt = "  → Continue [Enter], Skip [s], or Exit [x]: "
        if self.is_optional:
            prompt = "  → Continue [Enter], Skip [s] (recommended), or Exit [x]: "

        choice = await ui.input(
            f"tutorial_step_{self.step_id}",
            pretext=prompt,
            state_manager=state_manager,
        )

        choice = choice.strip().lower()

        if choice in ['x', 'exit', 'quit']:
            return TutorialStepResult.EXIT
        elif choice in ['s', 'skip']:
            return TutorialStepResult.SKIPPED
        elif choice in ['r', 'retry']:
            return TutorialStepResult.RETRY
        else:
            return TutorialStepResult.COMPLETED


def create_tutorial_steps() -> Dict[str, TutorialStep]:
    """Create the standard tutorial step sequence."""
    steps = {}

    step_order = [
        "welcome",
        "basic_interaction",
        "file_operations",
        "commands",
        "best_practices",
        "completion"
    ]

    for step_id in step_order:
        if step_id in TUTORIAL_STEPS:
            content = TUTORIAL_STEPS[step_id]
            # Mark advanced steps as optional
            is_optional = step_id in ["commands", "best_practices"]
            steps[step_id] = TutorialStep(step_id, content, is_optional)

    return steps


def get_tutorial_progress_key() -> str:
    """Get the config key for storing tutorial progress."""
    return "tutorial_progress"


def get_tutorial_completion_key() -> str:
    """Get the config key for storing tutorial completion status."""
    return "tutorial_completed"


def save_tutorial_progress(
    state_manager: StateManager,
    current_step: str,
    completed_steps: list
) -> None:
    """Save tutorial progress to user config."""
    if "settings" not in state_manager.session.user_config:
        state_manager.session.user_config["settings"] = {}

    progress_data = {
        "current_step": current_step,
        "completed_steps": completed_steps,
        "last_update": "2025-08-17"  # Could use datetime if needed
    }

    state_manager.session.user_config["settings"][get_tutorial_progress_key()] = progress_data


def load_tutorial_progress(state_manager: StateManager) -> Dict[str, Any]:
    """Load tutorial progress from user config."""
    settings = state_manager.session.user_config.get("settings", {})
    return settings.get(get_tutorial_progress_key(), {
        "current_step": "welcome",
        "completed_steps": [],
        "last_update": None
    })


def mark_tutorial_completed(state_manager: StateManager) -> None:
    """Mark the tutorial as completed in user config."""
    if "settings" not in state_manager.session.user_config:
        state_manager.session.user_config["settings"] = {}

    state_manager.session.user_config["settings"][get_tutorial_completion_key()] = True

    # Clear progress since it's completed
    if get_tutorial_progress_key() in state_manager.session.user_config["settings"]:
        del state_manager.session.user_config["settings"][get_tutorial_progress_key()]


def is_tutorial_completed(state_manager: StateManager) -> bool:
    """Check if the tutorial has been completed."""
    settings = state_manager.session.user_config.get("settings", {})
    return settings.get(get_tutorial_completion_key(), False)
