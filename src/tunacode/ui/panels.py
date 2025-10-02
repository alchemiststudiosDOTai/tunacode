"""Panel display functions for TunaCode UI."""

import asyncio
import time
from typing import TYPE_CHECKING, Any, Mapping, Optional, Union

if TYPE_CHECKING:
    from rich.markdown import Markdown
    from rich.padding import Padding
    from rich.pretty import Pretty
    from rich.table import Table
    from rich.text import Text

from tunacode.configuration.models import ModelRegistry
from tunacode.constants import (
    APP_NAME,
    CMD_CLEAR,
    CMD_COMPACT,
    CMD_DUMP,
    CMD_EXIT,
    CMD_HELP,
    CMD_MODEL,
    CMD_YOLO,
    DESC_CLEAR,
    DESC_COMPACT,
    DESC_DUMP,
    DESC_EXIT,
    DESC_HELP,
    DESC_MODEL,
    DESC_MODEL_DEFAULT,
    DESC_MODEL_SWITCH,
    DESC_YOLO,
    PANEL_AVAILABLE_COMMANDS,
    PANEL_MESSAGE_HISTORY,
    PANEL_MODELS,
    UI_COLORS,
)
from tunacode.core.state import StateManager
from tunacode.utils.file_utils import DotDict

from .constants import DEFAULT_PANEL_PADDING
from .decorators import create_sync_wrapper
from .output import print

colors = DotDict(UI_COLORS)

RenderableContent = Union["Text", "Markdown"]

_rich_components: Optional[Mapping[str, Any]] = None


def get_rich_components() -> Mapping[str, Any]:
    """Get Rich components lazily with caching."""

    global _rich_components
    if _rich_components is not None:
        return _rich_components

    from rich.box import ROUNDED
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.padding import Padding
    from rich.panel import Panel
    from rich.pretty import Pretty
    from rich.table import Table
    from rich.text import Text

    _rich_components = {
        "ROUNDED": ROUNDED,
        "Live": Live,
        "Markdown": Markdown,
        "Padding": Padding,
        "Panel": Panel,
        "Pretty": Pretty,
        "Table": Table,
        "Text": Text,
    }
    return _rich_components


@create_sync_wrapper
async def panel(
    title: str,
    text: Union[str, "Markdown", "Pretty", "Table"],
    top: int = DEFAULT_PANEL_PADDING["top"],
    right: int = DEFAULT_PANEL_PADDING["right"],
    bottom: int = DEFAULT_PANEL_PADDING["bottom"],
    left: int = DEFAULT_PANEL_PADDING["left"],
    border_style: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Display a rich panel with modern styling."""
    rich = get_rich_components()
    border_style = border_style or kwargs.get("style") or colors.border

    panel_obj = rich["Panel"](
        rich["Padding"](text, (0, 1, 0, 1)),
        title=f"[bold]{title}[/bold]",
        title_align="left",
        border_style=border_style,
        padding=(0, 1),
        box=rich["ROUNDED"],  # Use ROUNDED box style
    )

    final_padding = rich["Padding"](panel_obj, (top, right, bottom, left))

    await print(final_padding, **kwargs)


async def agent(text: str, bottom: int = 1) -> None:
    """Display an agent panel with modern styling."""
    rich = get_rich_components()
    title = f"[bold {colors.primary}]●[/bold {colors.primary}] {APP_NAME}"
    await panel(title, rich["Markdown"](text), bottom=bottom, border_style=colors.primary)


class StreamingAgentPanel:
    """Streaming agent panel using Rich.Live for progressive display."""

    bottom: int
    title: str
    content: str
    live: Optional[Any]
    _last_update_time: float
    _dots_task: Optional[asyncio.Task]
    _dots_count: int
    _show_dots: bool

    def __init__(self, bottom: int = 1, debug: bool = False):
        self.bottom = bottom
        self.title = f"[bold {colors.primary}]●[/bold {colors.primary}] {APP_NAME}"
        self.content = ""
        self.live = None
        self._last_update_time = 0.0
        self._dots_task = None
        self._dots_count = 0
        self._show_dots = True  # Start with dots enabled for "Thinking..."
        # Debug/diagnostic instrumentation (printed after stop to avoid Live interference)
        self._debug_enabled = debug
        self._debug_events: list[str] = []
        self._update_count: int = 0
        self._first_update_done: bool = False
        self._dots_tick_count: int = 0
        self._max_logged_dots: int = 10

    def _log_debug(self, label: str, **data: Any) -> None:
        if not self._debug_enabled:
            return
        try:
            ts = time.perf_counter_ns()
        except Exception:
            ts = 0
        payload = ", ".join(f"{k}={repr(v)}" for k, v in data.items()) if data else ""
        line = f"[ui] {label} ts_ns={ts}{(' ' + payload) if payload else ''}"
        self._debug_events.append(line)

    def _create_panel(self) -> "Padding":
        """Create a Rich panel with current content."""
        from tunacode.constants import UI_THINKING_MESSAGE

        rich = get_rich_components()

        # Show "Thinking..." only when no content has arrived yet
        if not self.content:
            # Apply dots animation to "Thinking..." message too
            thinking_msg = UI_THINKING_MESSAGE
            if self._show_dots:
                # Remove the existing ... from the message and add animated dots
                base_msg = thinking_msg.replace("...", "")
                dots_patterns = ["", ".", "..", "..."]
                dots = dots_patterns[self._dots_count % len(dots_patterns)]
                thinking_msg = base_msg + dots
            content_renderable: RenderableContent = rich["Text"].from_markup(thinking_msg)
        else:
            # Once we have content, show it with optional dots animation
            display_content = self.content
            # Add animated dots if we're waiting for more content
            if self._show_dots:
                # Cycle through: "", ".", "..", "..."
                dots_patterns = ["", ".", "..", "..."]
                dots = dots_patterns[self._dots_count % len(dots_patterns)]
                display_content = self.content.rstrip() + dots
            content_renderable = rich["Markdown"](display_content)
        panel_obj = rich["Panel"](
            rich["Padding"](content_renderable, (0, 1, 0, 1)),
            title=f"[bold]{self.title}[/bold]",
            title_align="left",
            border_style=colors.primary,
            padding=(0, 1),
            box=rich["ROUNDED"],
        )
        return rich["Padding"](
            panel_obj,
            (
                DEFAULT_PANEL_PADDING["top"],
                DEFAULT_PANEL_PADDING["right"],
                self.bottom,
                DEFAULT_PANEL_PADDING["left"],
            ),
        )

    async def _animate_dots(self):
        """Animate dots after a pause in streaming."""
        while True:
            await asyncio.sleep(0.2)  # Faster animation cycle
            current_time = time.time()
            # Use shorter delay for initial "Thinking..." phase
            delay_threshold = 0.3 if not self.content else 1.0
            # Show dots after the delay threshold
            if current_time - self._last_update_time > delay_threshold:
                self._show_dots = True
                self._dots_count += 1
                # Log only a few initial ticks to avoid noise
                if (
                    self._debug_enabled
                    and not self.content
                    and self._dots_tick_count < self._max_logged_dots
                ):
                    self._dots_tick_count += 1
                    self._log_debug("dots_tick", n=self._dots_count)
                if self.live:
                    self.live.update(self._create_panel())
            else:
                # Only reset if we have content (keep dots for initial "Thinking...")
                if self.content:
                    self._show_dots = False
                    self._dots_count = 0

    async def start(self):
        """Start the live streaming display."""
        from .output import get_console

        rich = get_rich_components()

        self.live = rich["Live"](self._create_panel(), console=get_console(), refresh_per_second=4)
        self.live.start()
        self._log_debug("start")
        # For "Thinking...", set time in past to trigger dots immediately
        if not self.content:
            self._last_update_time = time.time() - 0.4  # Triggers dots on first cycle
        else:
            self._last_update_time = time.time()
        # Start the dots animation task
        self._dots_task = asyncio.create_task(self._animate_dots())

    async def update(self, content_chunk: str):
        """Update the streaming display with new content."""
        # Defensive: some providers may yield None chunks intermittently
        if content_chunk is None:
            content_chunk = ""

        # Filter out plan mode system prompts and tool definitions from streaming
        # Use more precise filtering to avoid false positives
        content_str = str(content_chunk).strip()
        if content_str and any(
            content_str.startswith(phrase) or phrase in content_str
            for phrase in [
                "🔧 PLAN MODE",
                "TOOL EXECUTION ONLY",
                "planning assistant that ONLY communicates",
                "namespace functions {",
                "namespace multi_tool_use {",
            ]
        ):
            return

        # Special handling for the training data phrase - only filter if it's a complete system message
        if "You are trained on data up to" in content_str and len(content_str) > 50:
            # Only filter if this looks like a complete system message, not user content
            if (
                content_str.startswith("You are trained on data up to")
                or "The current date is" in content_str
            ):
                return

        # Ensure type safety for concatenation
        incoming = str(content_chunk)
        # First-chunk diagnostics
        is_first_chunk = (not self.content) and bool(incoming)
        if is_first_chunk:
            self._log_debug(
                "first_chunk_received",
                chunk_repr=incoming[:5],
                chunk_len=len(incoming),
            )
        self.content = (self.content or "") + incoming

        # Reset the update timer when we get new content
        self._last_update_time = time.time()
        # Hide dots immediately when new content arrives
        if self._show_dots:
            self._log_debug("disable_dots_called")
        self._show_dots = False

        if self.live:
            # Log timing around the first two live.update() calls
            self._update_count += 1
            if self._update_count <= 2:
                self._log_debug("live_update.start", update_index=self._update_count)
            self.live.update(self._create_panel())
            if self._update_count <= 2:
                self._log_debug("live_update.end", update_index=self._update_count)

    async def set_content(self, content: str):
        """Set the complete content (overwrites previous)."""
        # Filter out plan mode system prompts and tool definitions
        # Use more precise filtering to avoid false positives
        content_str = str(content).strip()
        if content_str and any(
            content_str.startswith(phrase) or phrase in content_str
            for phrase in [
                "🔧 PLAN MODE",
                "TOOL EXECUTION ONLY",
                "planning assistant that ONLY communicates",
                "namespace functions {",
                "namespace multi_tool_use {",
            ]
        ):
            return

        # Special handling for the training data phrase - only filter if it's a complete system message
        if "You are trained on data up to" in content_str and len(content_str) > 50:
            # Only filter if this looks like a complete system message, not user content
            if (
                content_str.startswith("You are trained on data up to")
                or "The current date is" in content_str
            ):
                return

        self.content = content
        if self.live:
            self.live.update(self._create_panel())

    async def stop(self):
        """Stop the live streaming display."""
        # Cancel the dots animation task
        if self._dots_task:
            self._dots_task.cancel()
            try:
                await self._dots_task
            except asyncio.CancelledError:
                pass
            finally:
                self._log_debug("dots_task_cancelled")

        if self.live:
            # Get the console before stopping the live display
            from .output import console

            # Stop the live display
            self.live.stop()

            # Comprehensive cleanup to prevent extra lines
            console.print("", end="")  # Reset the current line without newline
            if hasattr(console, "file") and hasattr(console.file, "flush"):
                console.file.flush()  # Ensure output is flushed

            # Mark that we just finished streaming (for output control)
            try:
                from tunacode.core.logging.handlers import _streaming_context

                _streaming_context["just_finished"] = True
            except ImportError:
                pass  # If we can't import, continue without the optimization

            self.live = None

        # Emit debug diagnostics after Live has been stopped (to avoid interference)
        if self._debug_enabled:
            from .output import print as ui_print

            # Summarize UI buffer state
            ui_prefix = "[debug]"
            ui_buffer_first5 = repr((self.content or "")[:5])
            lines = [
                f"{ui_prefix} ui_buffer_first5={ui_buffer_first5} total_len={len(self.content or '')}",
            ]
            # Include recorded event lines
            lines.extend(self._debug_events)
            # Flush lines to console
            for line in lines:
                await ui_print(line)


async def agent_streaming(content_stream, bottom: int = 1):
    """Display an agent panel with streaming content updates.

    Args:
        content_stream: Async iterator yielding content chunks
        bottom: Bottom padding for the panel
    """
    panel = StreamingAgentPanel(bottom=bottom)
    await panel.start()

    try:
        async for chunk in content_stream:
            await panel.update(chunk)
    finally:
        await panel.stop()


async def error(text: str) -> None:
    """Unified logging: error message."""
    from .logging_compat import ui_logger

    await ui_logger.error(text)


async def dump_messages(messages_list=None, state_manager: StateManager = None) -> None:
    """Display message history panel."""
    rich = get_rich_components()
    if messages_list is None and state_manager:
        # Get messages from state manager
        messages = rich["Pretty"](state_manager.session.messages)
    elif messages_list is not None:
        messages = rich["Pretty"](messages_list)
    else:
        # No messages available
        messages = rich["Pretty"]([])
    await panel(PANEL_MESSAGE_HISTORY, messages, style=colors.muted)


async def models(state_manager: StateManager = None) -> None:
    """Display available models panel."""
    model_registry = ModelRegistry()
    model_ids = list(model_registry.list_models().keys())
    model_list = "\n".join([f"{index} - {model}" for index, model in enumerate(model_ids)])
    current_model = state_manager.session.current_model if state_manager else "unknown"
    text = f"Current model: {current_model}\n\n{model_list}"
    await panel(PANEL_MODELS, text, border_style=colors.muted)


async def help(command_registry=None) -> None:
    """Display the available commands organized by category."""
    rich = get_rich_components()
    table = rich["Table"](show_header=False, box=None, padding=(0, 2, 0, 0))
    table.add_column("Command", style=f"bold {colors.primary}", justify="right", min_width=18)
    table.add_column("Description", style=colors.muted)

    if command_registry:
        # Use the new command registry to display commands by category
        from ..cli.commands import CommandCategory

        category_order = [
            CommandCategory.SYSTEM,
            CommandCategory.NAVIGATION,
            CommandCategory.DEVELOPMENT,
            CommandCategory.MODEL,
            CommandCategory.DEBUG,
        ]

        for category in category_order:
            commands = command_registry.get_commands_by_category(category)
            if commands:
                # Add category header
                table.add_row("", "")
                table.add_row(f"[bold]{category.value.title()}[/bold]", "")

                # Add commands in this category
                for command in commands:
                    # Show primary command name
                    cmd_display = f"/{command.name}"
                    table.add_row(cmd_display, command.description)

                    # Special handling for model command variations
                    if command.name == "model":
                        table.add_row(f"{cmd_display} <n>", DESC_MODEL_SWITCH)
                        table.add_row(f"{cmd_display} <n> default", DESC_MODEL_DEFAULT)

        # Add built-in commands
        table.add_row("", "")
        table.add_row("[bold]Built-in[/bold]", "")
        table.add_row(CMD_EXIT, DESC_EXIT)
    else:
        # Fallback to static command list
        commands = [
            (CMD_HELP, DESC_HELP),
            (CMD_CLEAR, DESC_CLEAR),
            (CMD_DUMP, DESC_DUMP),
            (CMD_YOLO, DESC_YOLO),
            (CMD_COMPACT, DESC_COMPACT),
            (CMD_MODEL, DESC_MODEL),
            (f"{CMD_MODEL} <n>", DESC_MODEL_SWITCH),
            (f"{CMD_MODEL} <n> default", DESC_MODEL_DEFAULT),
            (CMD_EXIT, DESC_EXIT),
        ]

        for cmd, desc in commands:
            table.add_row(cmd, desc)

    await panel(PANEL_AVAILABLE_COMMANDS, table, border_style=colors.muted)


@create_sync_wrapper
async def tool_confirm(
    title: str, content: Union[str, "Markdown"], filepath: Optional[str] = None
) -> None:
    """Display a tool confirmation panel."""
    bottom_padding = 0 if filepath else 1
    await panel(title, content, bottom=bottom_padding, border_style=colors.warning)


# Auto-generated sync versions
sync_panel = panel.sync  # type: ignore
sync_tool_confirm = tool_confirm.sync  # type: ignore
