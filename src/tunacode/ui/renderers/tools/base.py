"""Base class and protocol for tool renderers following NeXTSTEP UI principles.

All tool renderers implement a 4-zone layout pattern:
- Zone 1: Header (tool name, status info)
- Zone 2: Params (key-value parameter display)
- Zone 3: Viewport (main content, padded to minimum height)
- Zone 4: Status (truncation info, timing)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from tunacode.constants import (
    BOX_HORIZONTAL,
    HOOK_ARROW_PREFIX,
    MAX_PANEL_LINE_WIDTH,
    MIN_TOOL_PANEL_LINE_WIDTH,
    MIN_VIEWPORT_LINES,
    SEPARATOR_WIDTH,
    TOOL_PANEL_WIDTH_DEBUG,
    TOOL_VIEWPORT_LINES,
    UI_COLORS,
)


def truncate_line(line: str, max_width: int = MAX_PANEL_LINE_WIDTH) -> str:
    """Truncate a single line if too wide.

    Args:
        line: The line to truncate
        max_width: Maximum allowed width (default: MAX_PANEL_LINE_WIDTH)

    Returns:
        Original line if within limit, otherwise truncated with '...'
    """
    if len(line) > max_width:
        return line[: max_width - 3] + "..."
    return line


def truncate_content(
    content: str,
    max_lines: int = TOOL_VIEWPORT_LINES,
    max_width: int = MAX_PANEL_LINE_WIDTH,
) -> tuple[str, int, int]:
    """Truncate content to viewport size.

    Args:
        content: Multi-line content string
        max_lines: Maximum number of lines to show
        max_width: Maximum width per line

    Returns:
        Tuple of (truncated_content, lines_shown, total_lines)
    """
    lines = content.splitlines()
    total = len(lines)

    if total <= max_lines:
        truncated = [truncate_line(ln, max_width) for ln in lines]
        return "\n".join(truncated), total, total

    truncated = [truncate_line(ln, max_width) for ln in lines[:max_lines]]
    return "\n".join(truncated), max_lines, total


def pad_lines(lines: list[str], min_lines: int = MIN_VIEWPORT_LINES) -> list[str]:
    """Pad a list of lines to minimum height.

    Args:
        lines: List of content lines
        min_lines: Minimum number of lines required

    Returns:
        Padded list with at least min_lines entries
    """
    result = list(lines)
    while len(result) < min_lines:
        result.append("")
    return result


def clamp_content_width(max_line_width: int, reserved_width: int) -> int:
    """Clamp content width to avoid negative or zero widths after prefixes."""
    return max(MIN_TOOL_PANEL_LINE_WIDTH, max_line_width - reserved_width)


def relative_path(filepath: str, root_path: Path) -> str:
    """Return filepath relative to root_path when possible."""
    path = Path(filepath)
    if not path.is_absolute():
        return path.as_posix()

    try:
        relative = path.relative_to(root_path)
    except ValueError:
        return path.as_posix()

    return relative.as_posix()


def build_hook_params_prefix() -> Text:
    """Build Zone 2 params prefix for tool panels."""
    params = Text()
    params.append(HOOK_ARROW_PREFIX, style="dim")
    return params


def build_hook_path_params(filepath: str, root_path: Path) -> Text:
    """Build Zone 2 params line for file-based tools."""
    relative = relative_path(filepath, root_path)
    params = build_hook_params_prefix()
    params.append(relative, style="dim underline")
    return params


# Type alias for render functions
RenderFunc = Callable[
    [dict[str, Any] | None, str, float | None, int],
    RenderableType | None,
]

# Registry mapping tool names to their render functions
_renderer_registry: dict[str, RenderFunc] = {}


def tool_renderer(tool_name: str) -> Callable[[RenderFunc], RenderFunc]:
    """Decorator to register a render function for a tool.

    Args:
        tool_name: The name of the tool this renderer handles

    Returns:
        Decorator that registers the function and returns it unchanged

    Example:
        @tool_renderer("list_dir")
        def render_list_dir(args, result, duration_ms):
            ...
    """

    def decorator(func: RenderFunc) -> RenderFunc:
        _renderer_registry[tool_name] = func
        return func

    return decorator


def get_renderer(tool_name: str) -> RenderFunc | None:
    """Look up the render function for a tool.

    Args:
        tool_name: The name of the tool

    Returns:
        The registered render function, or None if not found
    """
    return _renderer_registry.get(tool_name)


def list_renderers() -> list[str]:
    """Get list of all registered tool renderer names.

    Returns:
        Sorted list of registered tool names
    """
    return sorted(_renderer_registry.keys())


@dataclass
class RendererConfig:
    """Configuration for a tool renderer."""

    tool_name: str
    success_color: str = UI_COLORS["success"]
    warning_color: str = UI_COLORS["warning"]
    muted_color: str = UI_COLORS["muted"]


T = TypeVar("T")


@runtime_checkable
class ToolRendererProtocol(Protocol[T]):
    """Protocol defining the interface for tool renderers.

    Type parameter T is the parsed data type (e.g., BashData, ListDirData).
    """

    def parse_result(self, args: dict[str, Any] | None, result: str) -> T | None:
        """Parse raw result string into structured data.

        Args:
            args: Tool arguments passed to the tool
            result: Raw result string from tool execution

        Returns:
            Parsed data object, or None if parsing fails
        """
        ...

    def build_header(self, data: T, duration_ms: float | None, max_line_width: int) -> Text:
        """Build Zone 1: header with tool name and status info.

        Args:
            data: Parsed tool result data
            duration_ms: Execution duration in milliseconds
            max_line_width: Maximum line width for truncation

        Returns:
            Rich Text object for the header zone
        """
        ...

    def build_params(self, data: T, max_line_width: int) -> Text | None:
        """Build Zone 2: parameter key-value display.

        Args:
            data: Parsed tool result data
            max_line_width: Maximum line width for truncation

        Returns:
            Rich Text object for params zone, or None if no params
        """
        ...

    def build_viewport(self, data: T, max_line_width: int) -> RenderableType:
        """Build Zone 3: main content viewport.

        Args:
            data: Parsed tool result data
            max_line_width: Maximum line width for truncation

        Returns:
            Rich renderable for the viewport zone
        """
        ...

    def build_status(self, data: T, duration_ms: float | None, max_line_width: int) -> Text:
        """Build Zone 4: status line with truncation info and timing.

        Args:
            data: Parsed tool result data
            duration_ms: Execution duration in milliseconds
            max_line_width: Maximum line width for truncation

        Returns:
            Rich Text object for the status zone
        """
        ...

    def get_border_color(self, data: T) -> str:
        """Determine panel border color based on result state.

        Args:
            data: Parsed tool result data

        Returns:
            Color string for the panel border
        """
        ...

    def get_status_text(self, data: T) -> str:
        """Get status text for panel title (e.g., 'done', 'exit 1').

        Args:
            data: Parsed tool result data

        Returns:
            Status text string
        """
        ...


class BaseToolRenderer(ABC, Generic[T]):
    """Abstract base class for tool renderers implementing the 4-zone pattern.

    Subclasses must implement the abstract methods to provide tool-specific
    parsing and zone building. The render() method provides the common
    composition logic.

    Type parameter T is the parsed data type for the specific renderer.
    """

    def __init__(self, config: RendererConfig) -> None:
        """Initialize renderer with configuration.

        Args:
            config: Renderer configuration including tool name and colors
        """
        self.config = config

    @abstractmethod
    def parse_result(self, args: dict[str, Any] | None, result: str) -> T | None:
        """Parse raw result string into structured data.

        Args:
            args: Tool arguments passed to the tool
            result: Raw result string from tool execution

        Returns:
            Parsed data object, or None if parsing fails
        """
        ...

    @abstractmethod
    def build_header(self, data: T, duration_ms: float | None, max_line_width: int) -> Text:
        """Build Zone 1: header with tool name and status info.

        Args:
            data: Parsed tool result data
            duration_ms: Execution duration in milliseconds
            max_line_width: Maximum line width for truncation

        Returns:
            Rich Text object for the header zone
        """
        ...

    @abstractmethod
    def build_params(self, data: T, max_line_width: int) -> Text | None:
        """Build Zone 2: parameter key-value display.

        Args:
            data: Parsed tool result data
            max_line_width: Maximum line width for truncation

        Returns:
            Rich Text object for params zone, or None if no params
        """
        ...

    @abstractmethod
    def build_viewport(self, data: T, max_line_width: int) -> RenderableType:
        """Build Zone 3: main content viewport.

        Args:
            data: Parsed tool result data
            max_line_width: Maximum line width for truncation

        Returns:
            Rich renderable for the viewport zone
        """
        ...

    @abstractmethod
    def build_status(self, data: T, duration_ms: float | None, max_line_width: int) -> Text:
        """Build Zone 4: status line with truncation info and timing.

        Args:
            data: Parsed tool result data
            duration_ms: Execution duration in milliseconds
            max_line_width: Maximum line width for truncation

        Returns:
            Rich Text object for the status zone
        """
        ...

    def get_border_color(self, data: T) -> str:
        """Determine panel border color based on result state.

        Default implementation returns success color. Override for
        conditional coloring (e.g., bash exit codes).

        Args:
            data: Parsed tool result data

        Returns:
            Color string for the panel border
        """
        return self.config.success_color

    def get_status_text(self, data: T) -> str:
        """Get status text for panel title.

        Default implementation returns 'done'. Override for
        conditional status (e.g., bash exit codes).

        Args:
            data: Parsed tool result data

        Returns:
            Status text string
        """
        return "done"

    def build_separator(self) -> Text:
        """Build a horizontal separator line.

        Returns:
            Rich Text object containing the separator
        """
        return Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")

    def pad_viewport_lines(self, lines: list[str]) -> list[str]:
        """Pad viewport lines to minimum height for visual consistency.

        Args:
            lines: List of content lines

        Returns:
            Padded list with at least MIN_VIEWPORT_LINES entries
        """
        result = list(lines)
        while len(result) < MIN_VIEWPORT_LINES:
            result.append("")
        return result

    def render(
        self,
        args: dict[str, Any] | None,
        result: str,
        duration_ms: float | None = None,
        max_line_width: int = MAX_PANEL_LINE_WIDTH,
    ) -> RenderableType | None:
        """Render tool result using the 4-zone layout pattern.

        This is the template method that orchestrates the rendering process:
        1. Parse the result into structured data
        2. Build each zone using abstract methods
        3. Compose zones with separators
        4. Wrap in a Panel with title and styling

        Args:
            args: Tool arguments passed to the tool
            result: Raw result string from tool execution
            duration_ms: Execution duration in milliseconds
            max_line_width: Maximum line width for truncation

        Returns:
            Rich Panel containing the rendered output, or None if parsing fails
        """
        data = self.parse_result(args, result)
        if data is None:
            return None

        # Build zones
        header = self.build_header(data, duration_ms, max_line_width)
        params = self.build_params(data, max_line_width)
        viewport = self.build_viewport(data, max_line_width)
        status = self.build_status(data, duration_ms, max_line_width)
        if TOOL_PANEL_WIDTH_DEBUG:
            status.append(f"  width: {max_line_width}", style="dim")
        separator = self.build_separator()

        content_parts: list[RenderableType] = [header]

        if params is not None:
            content_parts.append(params)

        content_parts.extend([separator, viewport, separator, status])

        content = Group(*content_parts)

        timestamp = datetime.now().strftime("%H:%M:%S")
        border_color = self.get_border_color(data)
        status_text = self.get_status_text(data)

        return Panel(
            content,
            title=f"[{border_color}]{self.config.tool_name}[/] [{status_text}]",
            subtitle=f"[{self.config.muted_color}]{timestamp}[/]",
            border_style=Style(color=border_color),
            padding=(0, 1),
            expand=True,
        )
