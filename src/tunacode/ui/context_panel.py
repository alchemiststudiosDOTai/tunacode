"""Context inspector panel helpers for the Textual REPL UI."""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.dom import DOMNode
from textual.widgets import Static

from tunacode.ui.styles import (
    STYLE_ACCENT,
    STYLE_ERROR,
    STYLE_MUTED,
    STYLE_PRIMARY,
    STYLE_SUCCESS,
    STYLE_WARNING,
)
from tunacode.ui.tamagochi import TAMAGOCHI_ART_STATES, TAMAGOCHI_NAME

CONTEXT_GAUGE_WIDTH: int = 24


class InspectorField(Static):
    """Context inspector field with text selection disabled."""

    ALLOW_SELECT = False


@dataclass(slots=True)
class ContextPanelWidgets:
    widgets: tuple[Static, ...]
    field_tamagochi: InspectorField
    field_model: InspectorField
    field_context: InspectorField
    field_cost: InspectorField
    field_files: InspectorField


def build_context_panel_widgets() -> ContextPanelWidgets:
    inspector_title = Static("Session Inspector", id="inspector-title")

    field_tamagochi = InspectorField(
        f"{TAMAGOCHI_ART_STATES[0]}",
        id="field-pet",
        classes="inspector-field",
    )
    field_tamagochi.border_title = TAMAGOCHI_NAME

    field_model = InspectorField(
        "---",
        id="field-model",
        classes="inspector-field",
    )
    field_model.border_title = "Model"

    field_context = InspectorField(
        "",
        id="field-context",
        classes="inspector-field",
    )
    field_context.border_title = "Context"

    field_cost = InspectorField(
        "",
        id="field-cost",
        classes="inspector-field",
    )
    field_cost.border_title = "Cost"

    field_files = InspectorField(
        "",
        id="field-files",
        classes="inspector-field",
    )
    field_files.border_title = "Files"

    widgets: tuple[Static, ...] = (
        inspector_title,
        field_tamagochi,
        field_model,
        field_context,
        field_cost,
        field_files,
    )

    return ContextPanelWidgets(
        widgets=widgets,
        field_tamagochi=field_tamagochi,
        field_model=field_model,
        field_context=field_context,
        field_cost=field_cost,
        field_files=field_files,
    )


def token_remaining_pct(tokens: int, max_tokens: int) -> float:
    if max_tokens == 0:
        return 0.0

    raw = (max_tokens - tokens) / max_tokens * 100
    return max(0.0, min(100.0, raw))


def token_color(remaining_pct: float) -> str:
    if remaining_pct > 60:
        return STYLE_SUCCESS
    if remaining_pct > 30:
        return STYLE_WARNING
    return STYLE_ERROR


def build_context_gauge(
    *,
    tokens: int,
    max_tokens: int,
    remaining_pct: float,
    token_style: str,
) -> Text:
    used_pct = 100.0 - remaining_pct
    filled = round(CONTEXT_GAUGE_WIDTH * used_pct / 100)
    empty = CONTEXT_GAUGE_WIDTH - filled

    gauge = Text()
    gauge.append("█" * filled, style=token_style)
    gauge.append("░" * empty, style=STYLE_MUTED)
    gauge.append(f" {remaining_pct:.0f}%\n", style=f"bold {token_style}")
    gauge.append(f"{tokens:,}", style=token_style)
    gauge.append(f" / {max_tokens:,}", style=STYLE_MUTED)
    return gauge


def build_files_field(edited_files: set[str]) -> tuple[str, Text]:
    sorted_files = sorted(edited_files)
    file_count = len(sorted_files)
    border_title = f"Files [{file_count}]"

    if not sorted_files:
        return border_title, Text("(none)", style=f"dim {STYLE_MUTED}")

    content = Text()
    for index, filepath in enumerate(sorted_files):
        content.append("▸ ", style=STYLE_ACCENT)
        content.append(filepath, style=STYLE_PRIMARY)
        if index < file_count - 1:
            content.append("\n")

    return border_title, content


def is_widget_within_field(widget: DOMNode | None, root: DOMNode, *, field_id: str) -> bool:
    current = widget
    while current is not None and current is not root:
        if getattr(current, "id", None) == field_id:
            return True
        current = current.parent

    return False
