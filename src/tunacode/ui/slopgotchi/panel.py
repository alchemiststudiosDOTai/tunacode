from __future__ import annotations

import time
from dataclasses import dataclass

from rich.text import Text
from textual.widgets import Static

from tunacode.ui.styles import STYLE_ERROR, STYLE_SUCCESS

SLOPGOTCHI_NAME: str = "Slopgotchi"
SLOPGOTCHI_HEART: str = "\u2665"
SLOPGOTCHI_ART_STATES: tuple[str, str] = (
    " /\\_/\\\n( T.T )\n > _ <",
    " /\\_/\\\n( ;.; )\n > _ <",
)
SLOPGOTCHI_MOVE_RANGE: int = 4
SLOPGOTCHI_AUTO_MOVE_INTERVAL_SECONDS: float = 0.75


@dataclass(slots=True)
class SlopgotchiPanelState:
    frame_index: int = 0
    offset: int = 0
    direction: int = 1
    show_heart: bool = False
    last_auto_move: float = 0.0


def _advance_offset(state: SlopgotchiPanelState) -> None:
    state.offset += state.direction
    if state.offset >= SLOPGOTCHI_MOVE_RANGE:
        state.offset = SLOPGOTCHI_MOVE_RANGE
        state.direction = -1
        return
    if state.offset <= 0:
        state.offset = 0
        state.direction = 1


def touch_slopgotchi(state: SlopgotchiPanelState) -> None:
    frame_count = len(SLOPGOTCHI_ART_STATES)
    state.show_heart = True
    state.frame_index = (state.frame_index + 1) % frame_count
    _advance_offset(state)


def advance_slopgotchi(state: SlopgotchiPanelState, *, now: float) -> bool:
    if now - state.last_auto_move < SLOPGOTCHI_AUTO_MOVE_INTERVAL_SECONDS:
        return False

    state.last_auto_move = now
    _advance_offset(state)
    frame_count = len(SLOPGOTCHI_ART_STATES)
    state.frame_index = (state.frame_index + 1) % frame_count
    return True


def render_slopgotchi(state: SlopgotchiPanelState) -> Text:
    frame_count = len(SLOPGOTCHI_ART_STATES)
    frame = SLOPGOTCHI_ART_STATES[state.frame_index % frame_count]
    pad = " " * state.offset

    art = Text()
    padded_frame = "\n".join(pad + line for line in frame.split("\n"))
    art.append(padded_frame, style=STYLE_SUCCESS)

    art.append("\n")
    if state.show_heart:
        art.append(f"{pad}  {SLOPGOTCHI_HEART}", style=f"bold {STYLE_ERROR}")

    return art


class SlopgotchiHandler:
    """Manages slopgotchi widget interactions and animations."""

    def __init__(self, state: SlopgotchiPanelState, widget: Static) -> None:
        self._state = state
        self._widget = widget

    def touch(self) -> None:
        """Handle user tap interaction."""
        touch_slopgotchi(self._state)
        self._refresh()

    def update(self) -> bool:
        """Advance animation state if enough time has elapsed."""
        if not advance_slopgotchi(self._state, now=time.monotonic()):
            return False
        self._refresh()
        return True

    def _refresh(self) -> None:
        """Update the widget with current state."""
        art = render_slopgotchi(self._state)
        self._widget.update(art)
