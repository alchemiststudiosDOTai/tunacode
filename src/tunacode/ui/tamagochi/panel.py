from __future__ import annotations

import time
from dataclasses import dataclass

from rich.text import Text
from textual.widgets import Static

from tunacode.ui.styles import STYLE_ERROR, STYLE_SUCCESS

TAMAGOCHI_NAME: str = "Tamagotchi"
TAMAGOCHI_HEART: str = "♥"
TAMAGOCHI_ART_STATES: tuple[str, str] = (
    " /\\_/\\\n( T.T )\n > _ <",
    " /\\_/\\\n( ;.; )\n > _ <",
)
TAMAGOCHI_MOVE_RANGE: int = 4
TAMAGOCHI_AUTO_MOVE_INTERVAL_SECONDS: float = 0.75


@dataclass(slots=True)
class TamagochiPanelState:
    frame_index: int = 0
    offset: int = 0
    direction: int = 1
    show_heart: bool = False
    last_auto_move: float = 0.0


def _advance_offset(state: TamagochiPanelState) -> None:
    state.offset += state.direction
    if state.offset >= TAMAGOCHI_MOVE_RANGE:
        state.offset = TAMAGOCHI_MOVE_RANGE
        state.direction = -1
        return
    if state.offset <= 0:
        state.offset = 0
        state.direction = 1


def touch_tamagochi(state: TamagochiPanelState) -> None:
    frame_count = len(TAMAGOCHI_ART_STATES)
    state.show_heart = True
    state.frame_index = (state.frame_index + 1) % frame_count
    _advance_offset(state)


def advance_tamagochi(state: TamagochiPanelState, *, now: float) -> bool:
    if now - state.last_auto_move < TAMAGOCHI_AUTO_MOVE_INTERVAL_SECONDS:
        return False

    state.last_auto_move = now
    _advance_offset(state)
    frame_count = len(TAMAGOCHI_ART_STATES)
    state.frame_index = (state.frame_index + 1) % frame_count
    return True


def render_tamagochi(state: TamagochiPanelState) -> Text:
    frame_count = len(TAMAGOCHI_ART_STATES)
    frame = TAMAGOCHI_ART_STATES[state.frame_index % frame_count]
    pad = " " * state.offset

    art = Text()
    padded_frame = "\n".join(pad + line for line in frame.split("\n"))
    art.append(padded_frame, style=STYLE_SUCCESS)

    if state.show_heart:
        art.append("\n")
        art.append(f"{pad}  {TAMAGOCHI_HEART}", style=f"bold {STYLE_ERROR}")

    return art


class TamagochiHandler:
    """Manages tamagochi widget interactions and animations."""

    def __init__(self, state: TamagochiPanelState, widget: Static) -> None:
        self._state = state
        self._widget = widget

    def touch(self) -> None:
        """Handle user tap interaction."""
        touch_tamagochi(self._state)
        self._refresh()

    def update(self) -> bool:
        """Advance animation state if enough time has elapsed."""
        if not advance_tamagochi(self._state, now=time.monotonic()):
            return False
        self._refresh()
        return True

    def _refresh(self) -> None:
        """Update the widget with current state."""
        art = render_tamagochi(self._state)
        self._widget.update(art)
