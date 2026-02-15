from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text

from tunacode.ui.styles import STYLE_ERROR, STYLE_MUTED, STYLE_PRIMARY, STYLE_SUCCESS

TAMAGOCHI_NAME: str = "Tamagotchi"
TAMAGOCHI_HEART: str = "♥"
TAMAGOCHI_ART_STATES: tuple[str, str] = (
    " /\\_/\\\n( T.T )\n > _ <",
    " /\\_/\\\n( ;.; )\n > _ <",
)
TAMAGOCHI_MOVE_RANGE: int = 4
SLOPBAR_HEALTH_BAR_WIDTH: int = 10
SLOPBAR_HEALTH_PERCENT_START: int = 50
SLOPBAR_HEALTH_NAME: str = "Slopbar Health"


@dataclass(slots=True)
class TamagochiPanelState:
    frame_index: int = 0
    offset: int = 0
    direction: int = 1
    show_heart: bool = False
    slopbar_health_percent: int = SLOPBAR_HEALTH_PERCENT_START


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


def render_slopbar_health(state: TamagochiPanelState) -> Text:
    filled = SLOPBAR_HEALTH_BAR_WIDTH * state.slopbar_health_percent // 100
    filled = max(0, min(SLOPBAR_HEALTH_BAR_WIDTH, filled))
    empty = SLOPBAR_HEALTH_BAR_WIDTH - filled

    bar = Text()
    bar.append("█" * filled, style=STYLE_SUCCESS)
    bar.append("░" * empty, style=STYLE_MUTED)
    bar.append(f" {state.slopbar_health_percent}%", style=f"bold {STYLE_PRIMARY}")
    return bar
