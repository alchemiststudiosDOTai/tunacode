"""Panel display functions for TunaCode UI."""

from typing import Any, Optional, Union

from rich.box import ROUNDED
from rich.live import Live
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
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
    PANEL_ERROR,
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


@create_sync_wrapper
async def panel(
    title: str,
    text: Union[str, Markdown, Pretty],
    top: int = DEFAULT_PANEL_PADDING["top"],
    right: int = DEFAULT_PANEL_PADDING["right"],
    bottom: int = DEFAULT_PANEL_PADDING["bottom"],
    left: int = DEFAULT_PANEL_PADDING["left"],
    border_style: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Display a rich panel with modern styling."""
    border_style = border_style or kwargs.get("style") or colors.border
    panel_obj = Panel(
        Padding(text, (0, 1, 0, 1)),
        title=f"[bold]{title}[/bold]",
        title_align="left",
        border_style=border_style,
        padding=(0, 1),
        box=ROUNDED,  # Use ROUNDED box style
    )
    await print(Padding(panel_obj, (top, right, bottom, left)), **kwargs)


async def agent(text: str, bottom: int = 1) -> None:
    """Display an agent panel with modern styling."""
    title = f"[bold {colors.primary}]●[/bold {colors.primary}] {APP_NAME}"
    await panel(title, Markdown(text), bottom=bottom, border_style=colors.primary)


class StreamingAgentPanel:
    """Streaming agent panel using Rich.Live for progressive display."""

    def __init__(self, bottom: int = 1):
        self.bottom = bottom
        self.title = f"[bold {colors.primary}]●[/bold {colors.primary}] {APP_NAME}"
        self.content = ""
        self.live = None

    def _create_panel(self) -> Panel:
        """Create a Rich panel with current content."""
        # Use the UI_THINKING_MESSAGE constant instead of hardcoded text
        from tunacode.constants import UI_THINKING_MESSAGE

        # If no content, show thinking message with Rich markup
        if not self.content:
            content_to_display = Text.from_markup(UI_THINKING_MESSAGE)
        else:
            # Normal content is markdown
            content_to_display = Markdown(self.content)

        panel_obj = Panel(
            Padding(content_to_display, (0, 1, 0, 1)),
            title=f"[bold]{self.title}[/bold]",
            title_align="left",
            border_style=colors.primary,
            padding=(0, 1),
            box=ROUNDED,
        )
        return Padding(
            panel_obj,
            (
                DEFAULT_PANEL_PADDING["top"],
                DEFAULT_PANEL_PADDING["right"],
                self.bottom,
                DEFAULT_PANEL_PADDING["left"],
            ),
        )

    async def start(self):
        """Start the live streaming display."""
        from .output import console

        self.live = Live(self._create_panel(), console=console, refresh_per_second=4)
        self.live.start()

    async def update(self, content_chunk: str):
        """Update the streaming display with new content."""
        self.content += content_chunk
        if self.live:
            self.live.update(self._create_panel())

    async def set_content(self, content: str):
        """Set the complete content (overwrites previous)."""
        self.content = content
        if self.live:
            self.live.update(self._create_panel())

    async def stop(self):
        """Stop the live streaming display."""
        if self.live:
            self.live.stop()
            self.live = None


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
    """Display an error panel."""
    await panel(PANEL_ERROR, text, style=colors.error)


async def dump_messages(messages_list=None, state_manager: StateManager = None) -> None:
    """Display message history panel."""
    if messages_list is None and state_manager:
        # Get messages from state manager
        messages = Pretty(state_manager.session.messages)
    elif messages_list is not None:
        messages = Pretty(messages_list)
    else:
        # No messages available
        messages = Pretty([])
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
    table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
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
    title: str, content: Union[str, Markdown], filepath: Optional[str] = None
) -> None:
    """Display a tool confirmation panel."""
    bottom_padding = 0 if filepath else 1
    await panel(title, content, bottom=bottom_padding, border_style=colors.warning)


# Auto-generated sync versions
sync_panel = panel.sync  # type: ignore
sync_tool_confirm = tool_confirm.sync  # type: ignore
