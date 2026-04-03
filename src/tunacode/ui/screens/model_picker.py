"""Model picker modal screen for TunaCode."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from tunacode.configuration.models import (
    ModelPickerEntry,
    get_model_picker_entries,
    rank_model_picker_entries,
)
from tunacode.configuration.pricing import format_pricing_display, get_model_pricing
from tunacode.constants import MODEL_PICKER_UNFILTERED_LIMIT


def _choose_highlight_index(
    items: list[tuple[str, str]],
    current_id: str,
) -> int | None:
    if not items:
        return None

    for index, (_, item_id) in enumerate(items):
        if item_id == current_id:
            return index

    return 0


def _append_truncation_notice(option_list: OptionList, limit: int, label: str) -> None:
    message = (
        f"Showing current/recent picks plus first {limit} {label}. Type to filter to see more."
    )
    option_list.add_option(Option(message, disabled=True))


def _format_model_option_label(
    entry: ModelPickerEntry,
    *,
    is_current: bool,
    is_recent: bool,
) -> str:
    badges: list[str] = []
    if is_current:
        badges.append("current")
    elif is_recent:
        badges.append("recent")

    badge_text = f"[{', '.join(badges)}] " if badges else ""
    label = f"{badge_text}{entry.model_name}  {entry.provider_name}"

    pricing = get_model_pricing(entry.full_model)
    if pricing is not None:
        label = f"{label}  {format_pricing_display(pricing)}"

    return label


def build_model_picker_option_rows(
    entries: list[ModelPickerEntry],
    *,
    current_model: str,
    recent_models: list[str],
    filter_query: str,
) -> tuple[list[tuple[str, str]], int | None, bool]:
    """Build rendered picker rows plus highlight/truncation metadata."""
    visible_entries, is_truncated = rank_model_picker_entries(
        entries,
        current_model=current_model,
        recent_models=recent_models,
        filter_query=filter_query,
    )

    option_rows = [
        (
            _format_model_option_label(
                entry,
                is_current=entry.full_model == current_model,
                is_recent=entry.full_model in recent_models,
            ),
            entry.full_model,
        )
        for entry in visible_entries
    ]

    highlight_index = _choose_highlight_index(option_rows, current_model)
    return option_rows, highlight_index, is_truncated


class ModelPickerScreen(Screen[str | None]):
    """Modal screen for model selection."""

    CSS = """
    ModelPickerScreen {
        align: center middle;
    }

    #model-container {
        width: 78;
        height: auto;
        max-height: 28;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #model-title {
        text-style: bold;
        color: $accent;
        text-align: center;
        margin-bottom: 1;
    }

    #model-filter {
        height: 3;
        margin-bottom: 1;
    }

    #model-list {
        height: auto;
        max-height: 18;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, current_model: str, recent_models: list[str]) -> None:
        super().__init__()
        self._current_model = current_model
        self._recent_models = recent_models
        self._all_entries: list[ModelPickerEntry] = []
        self._filter_query = ""

    def compose(self) -> ComposeResult:
        self._all_entries = get_model_picker_entries()

        with Vertical(id="model-container"):
            yield Static("Select Model", id="model-title")
            yield Input(placeholder="Filter models or providers...", id="model-filter")
            yield OptionList(id="model-list")

        self.call_after_refresh(self._rebuild_options)

    def _rebuild_options(self) -> None:
        """Rebuild the OptionList with current/recent-first ordering."""
        option_list = self.query_one("#model-list", OptionList)
        option_list.clear_options()

        option_rows, highlight_index, is_truncated = build_model_picker_option_rows(
            self._all_entries,
            current_model=self._current_model,
            recent_models=self._recent_models,
            filter_query=self._filter_query,
        )

        for label, full_model in option_rows:
            option_list.add_option(Option(label, id=full_model))

        if highlight_index is not None:
            option_list.highlighted = highlight_index

        if is_truncated:
            _append_truncation_notice(
                option_list,
                MODEL_PICKER_UNFILTERED_LIMIT,
                "models",
            )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter options as the user types."""
        if event.input.id != "model-filter":
            return

        self._filter_query = event.value
        self._rebuild_options()

    def on_key(self, event: events.Key) -> None:
        """Handle focus transitions between Input and OptionList."""
        filter_input = self.query_one("#model-filter", Input)
        option_list = self.query_one("#model-list", OptionList)

        if event.key == "down" and self.focused == filter_input:
            self.set_focus(option_list)
            event.stop()
        elif event.key == "up" and self.focused == option_list:
            if option_list.highlighted == 0:
                self.set_focus(filter_input)
                event.stop()
        elif event.key == "escape" and self._filter_query:
            filter_input.value = ""
            self._filter_query = ""
            self._rebuild_options()
            event.stop()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Dismiss the screen with the selected full model string."""
        if event.option and event.option.id:
            self.dismiss(str(event.option.id))

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.dismiss(None)
