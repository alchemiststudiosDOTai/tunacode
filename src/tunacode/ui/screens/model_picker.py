"""Model picker modal screens for TunaCode."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from tunacode.core.ui_api.configuration import get_models_for_provider, get_providers
from tunacode.core.ui_api.constants import MODEL_PICKER_UNFILTERED_LIMIT


def _filter_visible_items(
    items: list[tuple[str, str]],
    filter_query: str,
    limit: int,
) -> tuple[list[tuple[str, str]], bool]:
    normalized_query = filter_query.strip().lower()
    has_query = bool(normalized_query)
    visible_items: list[tuple[str, str]] = []
    total_matches = 0

    for display_name, item_id in items:
        display_name_lower = display_name.lower()
        if has_query and normalized_query not in display_name_lower:
            continue
        total_matches += 1
        if not has_query and len(visible_items) >= limit:
            continue
        visible_items.append((display_name, item_id))

    is_truncated = (not has_query) and (total_matches > len(visible_items))
    return visible_items, is_truncated


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
    message = f"Showing first {limit} {label}. Type to filter to see more."
    option_list.add_option(Option(message, disabled=True))


class ProviderPickerScreen(Screen[str | None]):
    """Modal screen for provider selection (step 1 of model picker)."""

    CSS = """
    ProviderPickerScreen {
        align: center middle;
    }

    #provider-container {
        width: 50;
        height: auto;
        max-height: 28;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #provider-title {
        text-style: bold;
        color: $accent;
        text-align: center;
        margin-bottom: 1;
    }

    #provider-filter {
        height: 3;
        margin-bottom: 1;
    }

    #provider-list {
        height: auto;
        max-height: 18;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, current_model: str) -> None:
        super().__init__()
        self._current_model = current_model
        self._current_provider = current_model.split(":")[0] if ":" in current_model else ""
        self._all_providers: list[tuple[str, str]] = []
        self._filter_query: str = ""

    def compose(self) -> ComposeResult:
        self._all_providers = get_providers()

        with Vertical(id="provider-container"):
            yield Static("Select Provider", id="provider-title")
            yield Input(placeholder="Filter providers...", id="provider-filter")
            yield OptionList(id="provider-list")

        self.call_after_refresh(self._rebuild_options)

    def _rebuild_options(self) -> None:
        """Rebuild OptionList with filtered items."""
        option_list = self.query_one("#provider-list", OptionList)
        option_list.clear_options()

        filter_query = self._filter_query
        visible_providers, is_truncated = _filter_visible_items(
            self._all_providers,
            filter_query,
            MODEL_PICKER_UNFILTERED_LIMIT,
        )

        highlight_index = _choose_highlight_index(visible_providers, self._current_provider)

        for display_name, provider_id in visible_providers:
            option_list.add_option(Option(display_name, id=provider_id))

        if highlight_index is not None:
            option_list.highlighted = highlight_index

        if is_truncated:
            _append_truncation_notice(
                option_list,
                MODEL_PICKER_UNFILTERED_LIMIT,
                "providers",
            )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter options as user types."""
        if event.input.id != "provider-filter":
            return
        self._filter_query = event.value
        self._rebuild_options()

    def on_key(self, event: events.Key) -> None:
        """Handle focus transitions between Input and OptionList."""
        filter_input = self.query_one("#provider-filter", Input)
        option_list = self.query_one("#provider-list", OptionList)

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
        """Confirm selection and dismiss with provider ID."""
        if event.option and event.option.id:
            self.dismiss(str(event.option.id))

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.dismiss(None)


class ModelPickerScreen(Screen[str | None]):
    """Modal screen for model selection (step 2 of model picker)."""

    CSS = """
    ModelPickerScreen {
        align: center middle;
    }

    #model-container {
        width: 60;
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

    def __init__(
        self,
        provider_id: str,
        current_model: str,
        recent_models: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._provider_id = provider_id
        self._current_model = current_model
        current_model_id = current_model.split(":", 1)[1] if ":" in current_model else ""
        self._current_model_id = current_model_id
        self._all_models: list[tuple[str, str]] = []
        self._recent_models: list[str] = recent_models or []
        self._filter_query: str = ""

    def compose(self) -> ComposeResult:
        self._all_models = get_models_for_provider(self._provider_id)

        with Vertical(id="model-container"):
            yield Static(f"Select Model ({self._provider_id})", id="model-title")
            yield Input(placeholder="Filter models...", id="model-filter")
            yield OptionList(id="model-list")

        self.call_after_refresh(self._rebuild_options)

    def _make_model_option(self, model_id: str, get_model_pricing, format_pricing_display) -> Option:
        """Build an ``Option`` with display name and pricing for *model_id*."""
        full_model = f"{self._provider_id}:{model_id}"
        pricing = get_model_pricing(full_model)
        display_name = model_id
        for dname, mid in self._all_models:
            if mid == model_id:
                display_name = dname
                break
        if pricing is not None:
            label = f"{display_name}  {format_pricing_display(pricing)}"
        else:
            label = display_name
        return Option(label, id=model_id)

    def _rebuild_options(self) -> None:
        """Rebuild OptionList with filtered items and pricing.

        When no filter query is active, recently-used models for this
        provider are shown in a ``Recent`` section at the top of the list.
        """
        from tunacode.core.ui_api.configuration import format_pricing_display, get_model_pricing

        option_list = self.query_one("#model-list", OptionList)
        option_list.clear_options()

        filter_query = self._filter_query
        visible_models, is_truncated = _filter_visible_items(
            self._all_models,
            filter_query,
            MODEL_PICKER_UNFILTERED_LIMIT,
        )

        # --- Recent models section (only when not filtering) ---
        provider_prefix = f"{self._provider_id}:"
        all_model_ids: set[str] = {mid for _, mid in self._all_models}
        recent_ids: list[str] = []
        if not filter_query.strip():
            for full in self._recent_models:
                if full.startswith(provider_prefix):
                    model_id = full[len(provider_prefix):]
                    # Validate against the full model set, not the truncated view
                    if model_id in all_model_ids:
                        recent_ids.append(model_id)

        recent_id_set: set[str] = set(recent_ids)

        if recent_ids:
            option_list.add_option(Option("── Recent ──", disabled=True))
            for model_id in recent_ids:
                option_list.add_option(self._make_model_option(model_id, get_model_pricing, format_pricing_display))
            option_list.add_option(Option("── All Models ──", disabled=True))

        highlight_index = _choose_highlight_index(visible_models, self._current_model_id)

        for display_name, model_id in visible_models:
            if model_id in recent_id_set:
                continue
            option_list.add_option(self._make_model_option(model_id, get_model_pricing, format_pricing_display))

        # Highlight: first recent model if present, otherwise the current model
        RECENT_HEADER_COUNT = 1  # "── Recent ──" header
        if recent_ids:
            option_list.highlighted = RECENT_HEADER_COUNT  # first recent model
        elif highlight_index is not None:
            option_list.highlighted = highlight_index

        if is_truncated:
            _append_truncation_notice(
                option_list,
                MODEL_PICKER_UNFILTERED_LIMIT,
                "models",
            )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter options as user types."""
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
        """Confirm selection and dismiss with full model string."""
        if event.option and event.option.id:
            full_model = f"{self._provider_id}:{event.option.id}"
            self.dismiss(full_model)

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.dismiss(None)
