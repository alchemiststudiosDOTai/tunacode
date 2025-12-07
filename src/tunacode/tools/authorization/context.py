from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tunacode.constants import ToolName

if TYPE_CHECKING:
    from tunacode.core.state import StateManager
    from tunacode.templates.loader import Template


@dataclass(frozen=True)
class AuthContext:
    """Immutable context for authorization decisions."""

    yolo_mode: bool
    tool_ignore_list: tuple[ToolName, ...]
    active_template: Template | None

    @classmethod
    def from_state(cls, state: StateManager) -> AuthContext:
        """Build context directly from session state."""
        active_template = None
        if hasattr(state, "tool_handler") and state.tool_handler is not None:
            active_template = getattr(state.tool_handler, "active_template", None)

        return cls(
            yolo_mode=state.session.yolo,
            tool_ignore_list=tuple(state.session.tool_ignore),
            active_template=active_template,
        )
