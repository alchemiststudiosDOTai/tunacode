from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text

from tunacode.ui.styles import STYLE_ERROR, STYLE_SUCCESS

TAMAGOCHI_NAME: str = "Tamagotchi"
TAMAGOCHI_HEART: str = "♥"
TAMAGOCHI_ART_STATES: tuple[str, str] = (
    " /\\_/\\\n( T.T )\n > _ <",
    " /\\_/\\\n( ;.; )\n > _ <",
)
TAMAGOCHI_MOVE_RANGE: int = 4


@dataclass(slots=True)
class TamagochiPanelState:
    frame_index: int = 0
    offset: int = 0
    direction: int = 1
    show_heart: bool = False


def touch_tamagochi(state: TamagochiPanelState) -> None:
    frame_count = len(TAMAGOCHI_ART_STATES)
    state.show_heart = True
    state.frame_index = (state.frame_index + 1) % frame_count
    state.offset += state.direction

    if state.offset >= TAMAGOCHI_MOVE_RANGE:
        state.offset = TAMAGOCHI_MOVE_RANGE
        state.direction = -1
        return

    if state.offset <= 0:
        state.offset = 0
        state.direction = 1


def render_tamagochi(state: TamagochiPanelState) -> Text:
    frame_count = len(TAMAGOCHI_ART_STATES)
    frame = TAMAGOCHI_ART_STATES[state.frame_index % frame_count]

    art = Text()
    art.append(frame, style=STYLE_SUCCESS)

    if state.show_heart:
        art.append("\n")
        art.append(f"  {TAMAGOCHI_HEART}", style=f"bold {STYLE_ERROR}")

    return art
