"""Interactive model selector UI component."""

from typing import List, Optional

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import HTML, StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
    WindowAlign,
)
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.search import SearchState
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame

from ..utils.models_registry import ModelInfo, ModelsRegistry


class ModelSelector:
    """Interactive model selector with search and navigation."""

    def __init__(self, registry: ModelsRegistry):
        """Initialize the model selector."""
        self.registry = registry
        self.models: List[ModelInfo] = []
        self.filtered_models: List[ModelInfo] = []
        self.selected_index = 0
        self.search_text = ""
        self.selected_model: Optional[ModelInfo] = None

        # Create key bindings
        self.kb = self._create_key_bindings()

        # Create search buffer
        self.search_buffer = Buffer(on_text_changed=self._on_search_changed)

        # Search state
        self.search_state = SearchState()

    def _create_key_bindings(self) -> KeyBindings:
        """Create key bindings for the selector."""
        kb = KeyBindings()

        @kb.add("up", "k")
        def move_up(event):
            """Move selection up."""
            if self.selected_index > 0:
                self.selected_index -= 1
                self._update_display()

        @kb.add("down", "j")
        def move_down(event):
            """Move selection down."""
            if self.selected_index < len(self.filtered_models) - 1:
                self.selected_index += 1
                self._update_display()

        @kb.add("pageup")
        def page_up(event):
            """Move selection up by page."""
            self.selected_index = max(0, self.selected_index - 10)
            self._update_display()

        @kb.add("pagedown")
        def page_down(event):
            """Move selection down by page."""
            self.selected_index = min(len(self.filtered_models) - 1, self.selected_index + 10)
            self._update_display()

        @kb.add("enter")
        def select_model(event):
            """Select the current model."""
            if 0 <= self.selected_index < len(self.filtered_models):
                self.selected_model = self.filtered_models[self.selected_index]
                event.app.exit(result=self.selected_model)

        @kb.add("c-c", "escape", "q")
        def cancel(event):
            """Cancel selection."""
            event.app.exit(result=None)

        @kb.add("/")
        def focus_search(event):
            """Focus the search input."""
            event.app.layout.focus(self.search_buffer)

        @kb.add("tab")
        def next_provider(event):
            """Jump to next provider."""
            if not self.filtered_models:
                return

            current_provider = self.filtered_models[self.selected_index].provider
            for i in range(self.selected_index + 1, len(self.filtered_models)):
                if self.filtered_models[i].provider != current_provider:
                    self.selected_index = i
                    self._update_display()
                    break

        @kb.add("s-tab")
        def prev_provider(event):
            """Jump to previous provider."""
            if not self.filtered_models:
                return

            current_provider = self.filtered_models[self.selected_index].provider
            for i in range(self.selected_index - 1, -1, -1):
                if self.filtered_models[i].provider != current_provider:
                    self.selected_index = i
                    self._update_display()
                    break

        return kb

    def _on_search_changed(self, buffer: Buffer) -> None:
        """Handle search text changes."""
        self.search_text = buffer.text
        self._filter_models()
        self._update_display()

    def _filter_models(self) -> None:
        """Filter models based on search text."""
        if not self.search_text:
            self.filtered_models = self.models.copy()
        else:
            # Search and sort by relevance
            self.filtered_models = self.registry.search_models(self.search_text)

        # Reset selection
        self.selected_index = 0 if self.filtered_models else -1

    def _get_model_lines(self) -> List[StyleAndTextTuples]:
        """Get formatted lines for model display."""
        lines = []

        if not self.filtered_models:
            lines.append([("class:muted", "No models found")])
            return lines

        # Group models by provider
        current_provider = None
        for i, model in enumerate(self.filtered_models):
            # Add provider header if changed
            if model.provider != current_provider:
                if current_provider is not None:
                    lines.append([])  # Empty line between providers

                provider_info = self.registry.providers.get(model.provider)
                provider_name = provider_info.name if provider_info else model.provider
                lines.append([("class:provider", f"▼ {provider_name}")])
                current_provider = model.provider

            # Model line
            is_selected = i == self.selected_index

            # Build model display
            parts = []

            # Selection indicator
            if is_selected:
                parts.append(("class:selected", "→ "))
            else:
                parts.append(("", "  "))

            # Model ID and name
            parts.append(("class:model-id" if not is_selected else "class:selected-id",
                         f"{model.id}"))
            parts.append(("class:muted", " - "))
            parts.append(("class:model-name" if not is_selected else "class:selected-name",
                         model.name))

            # Cost and limits
            details = []
            if model.cost.input is not None:
                details.append(f"${model.cost.input}/{model.cost.output}")
            if model.limits.context:
                details.append(f"{model.limits.context//1000}k")

            if details:
                parts.append(("class:muted", f" ({', '.join(details)})"))

            # Capabilities badges
            badges = []
            if model.capabilities.attachment:
                badges.append("📎")
            if model.capabilities.reasoning:
                badges.append("🧠")
            if model.capabilities.tool_call:
                badges.append("🔧")

            if badges:
                parts.append(("class:badges", " " + "".join(badges)))

            lines.append(parts)

        return lines

    def _get_details_panel(self) -> StyleAndTextTuples:
        """Get the details panel content for selected model."""
        if not self.filtered_models or self.selected_index < 0:
            return [("", "Select a model to see details")]

        model = self.filtered_models[self.selected_index]
        lines = []

        # Model name and ID
        lines.append([("class:title", model.name)])
        lines.append([("class:muted", f"{model.full_id}")])
        lines.append([])

        # Pricing
        lines.append([("class:section", "Pricing:")])
        if model.cost.input is not None:
            lines.append([("", f"  Input: ${model.cost.input} per 1M tokens")])
            lines.append([("", f"  Output: ${model.cost.output} per 1M tokens")])
        else:
            lines.append([("class:muted", "  Not available")])
        lines.append([])

        # Limits
        lines.append([("class:section", "Limits:")])
        if model.limits.context:
            lines.append([("", f"  Context: {model.limits.context:,} tokens")])
        if model.limits.output:
            lines.append([("", f"  Output: {model.limits.output:,} tokens")])
        if not model.limits.context and not model.limits.output:
            lines.append([("class:muted", "  Not specified")])
        lines.append([])

        # Capabilities
        lines.append([("class:section", "Capabilities:")])
        caps = []
        if model.capabilities.attachment:
            caps.append("Attachments")
        if model.capabilities.reasoning:
            caps.append("Reasoning")
        if model.capabilities.tool_call:
            caps.append("Tool calling")
        if model.capabilities.temperature:
            caps.append("Temperature control")

        if caps:
            for cap in caps:
                lines.append([("", f"  ✓ {cap}")])
        else:
            lines.append([("class:muted", "  Basic text generation")])

        if model.capabilities.knowledge:
            lines.append([])
            lines.append([("class:section", "Knowledge cutoff:")])
            lines.append([("", f"  {model.capabilities.knowledge}")])

        # Modalities
        if model.modalities:
            lines.append([])
            lines.append([("class:section", "Modalities:")])
            if "input" in model.modalities:
                lines.append([("", f"  Input: {', '.join(model.modalities['input'])}")])
            if "output" in model.modalities:
                lines.append([("", f"  Output: {', '.join(model.modalities['output'])}")])

        return lines

    def _update_display(self) -> None:
        """Update the display (called on changes)."""
        # This will trigger a redraw through prompt_toolkit's event system
        if hasattr(self, "app"):
            self.app.invalidate()

    def _create_layout(self) -> Layout:
        """Create the application layout."""
        # Model list
        model_list = FormattedTextControl(
            self._get_model_lines,
            focusable=False,
            show_cursor=False
        )

        model_window = Window(
            content=model_list,
            width=Dimension(min=40, preferred=60),
            height=Dimension(min=10, preferred=20),
            scroll_offsets=True,
            wrap_lines=False
        )

        # Details panel
        details_control = FormattedTextControl(
            self._get_details_panel,
            focusable=False,
            show_cursor=False
        )

        details_window = Window(
            content=details_control,
            width=Dimension(min=30, preferred=40),
            wrap_lines=True
        )

        # Search bar
        search_field = Window(
            BufferControl(
                buffer=self.search_buffer,
                focus_on_click=True
            ),
            height=1
        )

        search_label = Window(
            FormattedTextControl(HTML("<b>Search:</b> ")),
            width=8,
            height=1,
            dont_extend_width=True
        )

        search_bar = VSplit([search_label, search_field])

        # Help text
        help_text = Window(
            FormattedTextControl(
                HTML("<muted>↑↓: Navigate | Enter: Select | /: Search | Tab: Next provider | Esc: Cancel</muted>")
            ),
            height=1,
            align=WindowAlign.CENTER
        )

        # Main content
        content = VSplit([
            Frame(model_window, title="Select Model"),
            Frame(details_window, title="Details")
        ])

        # Root layout
        root = HSplit([
            search_bar,
            Window(height=1),  # Spacer
            content,
            Window(height=1),  # Spacer
            help_text
        ])

        return Layout(root)

    async def select_model(self, initial_query: str = "") -> Optional[ModelInfo]:
        """Show the model selector and return selected model."""
        # Load all models
        self.models = list(self.registry.models.values())
        self.search_buffer.text = initial_query

        # Filter initially
        self._filter_models()

        # Create application
        self.app = Application(
            layout=self._create_layout(),
            key_bindings=self.kb,
            mouse_support=True,
            full_screen=False,
            style=self._get_style()
        )

        # Run the selector
        result = await self.app.run_async()
        return result

    def _get_style(self) -> Style:
        """Get the style for the selector."""
        return Style.from_dict({
            'provider': 'bold cyan',
            'model-id': 'white',
            'model-name': 'bright_white',
            'selected': 'reverse bold',
            'selected-id': 'reverse bold white',
            'selected-name': 'reverse bold bright_white',
            'muted': 'gray',
            'badges': 'yellow',
            'title': 'bold bright_white',
            'section': 'bold cyan',
        })


async def select_model_interactive(
    registry: Optional[ModelsRegistry] = None,
    initial_query: str = ""
) -> Optional[str]:
    """Show interactive model selector and return selected model ID."""
    if registry is None:
        registry = ModelsRegistry()
        await registry.load()

    selector = ModelSelector(registry)
    model = await selector.select_model(initial_query)

    if model:
        return model.full_id
    return None
