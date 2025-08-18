"""
Module: tunacode.tutorial.steps

Tutorial step management and progress tracking functionality.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from ..types import StateManager
from .content import get_tutorial_steps

logger = logging.getLogger(__name__)


@dataclass
class TutorialStepResult:
    """Result of executing a tutorial step."""

    completed: bool
    should_continue: bool
    user_input: Optional[str] = None


def create_tutorial_steps() -> List[str]:
    """Create and return the list of tutorial steps."""
    return get_tutorial_steps()


def get_tutorial_completion_key() -> str:
    """Get the config key for storing tutorial completion status."""
    return "tutorial_completed"


def get_tutorial_progress_key() -> str:
    """Get the config key for storing tutorial progress."""
    return "tutorial_progress"


def mark_tutorial_completed(state_manager: StateManager) -> None:
    """Mark the tutorial as completed in user config."""
    if "settings" not in state_manager.session.user_config:
        state_manager.session.user_config["settings"] = {}

    state_manager.session.user_config["settings"][get_tutorial_completion_key()] = True

    # Clear any existing progress since it's now completed
    if get_tutorial_progress_key() in state_manager.session.user_config["settings"]:
        del state_manager.session.user_config["settings"][get_tutorial_progress_key()]


def save_tutorial_progress(state_manager: StateManager, current_step: int) -> None:
    """Save tutorial progress to user config."""
    if "settings" not in state_manager.session.user_config:
        state_manager.session.user_config["settings"] = {}

    state_manager.session.user_config["settings"][get_tutorial_progress_key()] = current_step


def load_tutorial_progress(state_manager: StateManager) -> int:
    """Load tutorial progress from user config."""
    settings = state_manager.session.user_config.get("settings", {})
    return settings.get(get_tutorial_progress_key(), 0)


def clear_tutorial_progress(state_manager: StateManager) -> None:
    """Clear tutorial progress from user config."""
    if "settings" not in state_manager.session.user_config:
        return

    if get_tutorial_progress_key() in state_manager.session.user_config["settings"]:
        del state_manager.session.user_config["settings"][get_tutorial_progress_key()]


def is_tutorial_completed(state_manager: StateManager) -> bool:
    """Check if the tutorial has been completed."""
    settings = state_manager.session.user_config.get("settings", {})
    return settings.get(get_tutorial_completion_key(), False)


def get_tutorial_declined_key() -> str:
    """Get the config key for storing tutorial declined status."""
    return "tutorial_declined"


def mark_tutorial_declined(state_manager: StateManager) -> None:
    """Mark the tutorial as declined in user config."""
    if "settings" not in state_manager.session.user_config:
        state_manager.session.user_config["settings"] = {}

    state_manager.session.user_config["settings"][get_tutorial_declined_key()] = True

    # Clear any existing progress since it was declined
    if get_tutorial_progress_key() in state_manager.session.user_config["settings"]:
        del state_manager.session.user_config["settings"][get_tutorial_progress_key()]


def is_tutorial_declined(state_manager: StateManager) -> bool:
    """Check if the tutorial has been declined."""
    settings = state_manager.session.user_config.get("settings", {})
    return settings.get(get_tutorial_declined_key(), False)


def is_first_time_user(state_manager: StateManager) -> bool:
    """Check if this is a first-time user based on installation date."""
    from datetime import datetime, timedelta

    settings = state_manager.session.user_config.get("settings", {})
    installation_date_str = settings.get("first_installation_date")

    if not installation_date_str:
        # No installation date means legacy user, treat as experienced
        return False

    try:
        installation_date = datetime.fromisoformat(installation_date_str)
        now = datetime.now()

        # Consider first-time if installed within last 7 days
        return (now - installation_date) <= timedelta(days=7)
    except (ValueError, TypeError):
        # Invalid date format, treat as experienced user
        return False
