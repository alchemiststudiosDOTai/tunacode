"""Rich Panel Renderer for Textual TUI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from tunacode.constants import (
    MAX_PANEL_LINE_WIDTH,
    MAX_PANEL_LINES,
    MAX_SEARCH_RESULTS_DISPLAY,
    UI_COLORS,
)


class PanelType(str, Enum):
    TOOL = "tool"
    ERROR = "error"
    SEARCH = "search"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"


PANEL_STYLES: dict[PanelType, dict[str, str]] = {
    PanelType.TOOL: {
        "border": UI_COLORS["primary"],
        "title": UI_COLORS["primary"],
        "subtitle": UI_COLORS["muted"],
    },
    PanelType.ERROR: {
        "border": UI_COLORS["error"],
        "title": UI_COLORS["error"],
        "subtitle": UI_COLORS["muted"],
    },
    PanelType.SEARCH: {
        "border": UI_COLORS["accent"],
        "title": UI_COLORS["accent"],
        "subtitle": UI_COLORS["muted"],
    },
    PanelType.INFO: {
        "border": UI_COLORS["muted"],
        "title": UI_COLORS["text"],
        "subtitle": UI_COLORS["muted"],
    },
    PanelType.SUCCESS: {
        "border": UI_COLORS["success"],
        "title": UI_COLORS["success"],
        "subtitle": UI_COLORS["muted"],
    },
    PanelType.WARNING: {
        "border": UI_COLORS["warning"],
        "title": UI_COLORS["warning"],
        "subtitle": UI_COLORS["muted"],
    },
}


@dataclass
class ToolDisplayData:
    tool_name: str
    status: str
    arguments: dict[str, Any]
    result: str | None = None
    duration_ms: float | None = None
    timestamp: datetime | None = None


@dataclass
class ErrorDisplayData:
    error_type: str
    message: str
    suggested_fix: str | None = None
    recovery_commands: list[str] | None = None
    context: dict[str, Any] | None = None
    severity: str = "error"


@dataclass
class SearchResultData:
    query: str
    results: list[dict[str, Any]]
    total_count: int
    current_page: int = 1
    page_size: int = 10
    search_time_ms: float | None = None
    source: str | None = None  # "index" or "filesystem" for glob cache status


class RichPanelRenderer:
    @staticmethod
    def render_tool(data: ToolDisplayData) -> RenderableType:
        status_map = {
            "running": (PanelType.TOOL, "..."),
            "completed": (PanelType.SUCCESS, "done"),
            "failed": (PanelType.ERROR, "fail"),
        }
        panel_type, status_suffix = status_map.get(data.status, (PanelType.INFO, data.status))
        styles = PANEL_STYLES[panel_type]

        content_parts: list[RenderableType] = []
        footer_parts: list[str] = []

        if data.arguments:
            args_table = Table.grid(padding=(0, 1))
            args_table.add_column(style="dim")
            args_table.add_column()
            for key, value in data.arguments.items():
                display_value = _truncate_value(value, max_length=60)
                args_table.add_row(f"{key}:", display_value)
            content_parts.append(args_table)

        if data.result:
            truncated_result, shown, total = _truncate_content(data.result)
            result_text = Text()
            result_text.append("\n")
            result_text.append(truncated_result)
            content_parts.append(result_text)

            # Add line count to footer if truncated
            if shown < total:
                footer_parts.append(f"{shown}/{total} lines")

        if data.duration_ms is not None:
            footer_parts.append(f"{data.duration_ms:.0f}ms")

        # Build footer from parts
        if footer_parts:
            footer_text = Text("\n" + " • ".join(footer_parts), style="dim")
            content_parts.append(footer_text)

        content = Group(*content_parts) if content_parts else Text("...")

        subtitle = None
        if data.timestamp:
            time_str = data.timestamp.strftime("%H:%M:%S")
            subtitle = f"[{styles['subtitle']}]{time_str}[/]"

        return Panel(
            content,
            title=f"[{styles['title']}]{data.tool_name}[/] [{status_suffix}]",
            subtitle=subtitle,
            border_style=Style(color=styles["border"]),
            padding=(0, 1),
            expand=False,
        )

    @staticmethod
    def render_diff_tool(
        tool_name: str,
        message: str,
        diff: str,
        args: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        timestamp: datetime | None = None,
    ) -> RenderableType:
        styles = PANEL_STYLES[PanelType.SUCCESS]

        content_parts: list[RenderableType] = []

        if args:
            args_table = Table.grid(padding=(0, 1))
            args_table.add_column(style="dim")
            args_table.add_column()
            for key, value in args.items():
                display_value = _truncate_value(value, max_length=60)
                args_table.add_row(f"{key}:", display_value)
            content_parts.append(args_table)
            content_parts.append(Text("\n"))

        if message:
            content_parts.append(Text(message))
            content_parts.append(Text("\n"))

        # Use Syntax highlighter for the diff
        diff_syntax = Syntax(diff, "diff", theme="monokai", word_wrap=True)
        content_parts.append(diff_syntax)

        if duration_ms is not None:
            footer = Text(f"\n{duration_ms:.0f}ms", style="dim")
            content_parts.append(footer)

        content = Group(*content_parts)

        subtitle = None
        if timestamp:
            time_str = timestamp.strftime("%H:%M:%S")
            subtitle = f"[{styles['subtitle']}]{time_str}[/]"

        return Panel(
            content,
            title=f"[{styles['title']}]{tool_name}[/] [done]",
            subtitle=subtitle,
            border_style=Style(color=styles["border"]),
            padding=(0, 1),
            expand=False,
        )

    @staticmethod
    def render_error(data: ErrorDisplayData) -> RenderableType:
        severity_map = {
            "error": PanelType.ERROR,
            "warning": PanelType.WARNING,
            "info": PanelType.INFO,
        }
        panel_type = severity_map.get(data.severity, PanelType.ERROR)
        styles = PANEL_STYLES[panel_type]

        content_parts: list[RenderableType] = []

        message_text = Text(data.message, style=styles["title"])
        content_parts.append(message_text)

        if data.suggested_fix:
            fix_text = Text()
            fix_text.append("\n\nFix: ", style="bold")
            fix_text.append(data.suggested_fix, style=UI_COLORS["success"])
            content_parts.append(fix_text)

        if data.recovery_commands:
            commands_text = Text("\n\nRecovery:\n", style="bold")
            for cmd in data.recovery_commands:
                commands_text.append(f"  {cmd}\n", style=UI_COLORS["primary"])
            content_parts.append(commands_text)

        if data.context:
            ctx_table = Table.grid(padding=(0, 1))
            ctx_table.add_column(style="dim")
            ctx_table.add_column()
            for key, value in data.context.items():
                ctx_table.add_row(f"{key}:", str(value))
            content_parts.append(Text("\n"))
            content_parts.append(ctx_table)

        content = Group(*content_parts)

        return Panel(
            content,
            title=f"[{styles['title']}]{data.error_type}[/]",
            border_style=Style(color=styles["border"]),
            padding=(0, 1),
            expand=True,
        )

    @staticmethod
    def render_search_results(data: SearchResultData) -> RenderableType:
        styles = PANEL_STYLES[PanelType.SEARCH]
        content_parts: list[RenderableType] = []

        query_text = Text()
        query_text.append("Query: ", style="dim")
        query_text.append(data.query, style="bold")
        content_parts.append(query_text)

        # Apply search result limiting
        display_results, shown_count, actual_total = _truncate_search_results(data.results)
        total_count = max(data.total_count, actual_total)

        start_idx = (data.current_page - 1) * data.page_size + 1
        end_idx = min(start_idx + shown_count - 1, total_count)
        total_pages = (total_count + data.page_size - 1) // data.page_size

        stats_text = Text()
        stats_text.append(f"\nShowing {start_idx}-{end_idx} of {total_count}", style="dim")
        if total_pages > 1:
            stats_text.append(f" (page {data.current_page}/{total_pages})", style="dim")
        content_parts.append(stats_text)

        if data.search_time_ms is not None:
            time_text = Text(f" in {data.search_time_ms:.0f}ms", style="dim")
            content_parts.append(time_text)

        content_parts.append(Text("\n"))

        results_table = Table.grid(padding=(0, 1))
        results_table.add_column(width=3, style="dim")
        results_table.add_column()

        for i, result in enumerate(display_results, start=start_idx):
            title = result.get("title", result.get("file", result.get("name", "...")))
            snippet = result.get("snippet", result.get("content", ""))
            relevance = result.get("relevance", result.get("score"))

            result_text = Text()
            result_text.append(str(title), style="bold")
            if relevance is not None:
                result_text.append(f" ({relevance:.0%})", style="dim")
            if snippet:
                result_text.append(f"\n  {_truncate_value(snippet, 80)}", style="dim")

            results_table.add_row(f"{i}.", result_text)

        # Show "+N more" indicator if truncated
        if shown_count < actual_total:
            more_count = actual_total - shown_count
            results_table.add_row("", Text(f"+{more_count} more results", style="dim italic"))

        content_parts.append(results_table)

        content = Group(*content_parts)

        subtitle = None
        if total_pages > 1:
            subtitle = f"[{styles['subtitle']}]Use arrows to navigate[/]"
        elif data.source == "index":
            subtitle = f"[{UI_COLORS['success']}]Indexed[/]"
        elif data.source == "filesystem":
            subtitle = f"[{styles['subtitle']}]Scanned[/]"

        return Panel(
            content,
            title=f"[{styles['title']}]Search Results[/]",
            subtitle=subtitle,
            border_style=Style(color=styles["border"]),
            padding=(0, 1),
            expand=True,
        )

    @staticmethod
    def render_info(title: str, content: str | RenderableType) -> RenderableType:
        styles = PANEL_STYLES[PanelType.INFO]

        if isinstance(content, str):
            content = Text(content)

        return Panel(
            content,
            title=f"[{styles['title']}]{title}[/]",
            border_style=Style(color=styles["border"]),
            padding=(0, 1),
            expand=False,
        )

    @staticmethod
    def render_success(title: str, message: str) -> RenderableType:
        styles = PANEL_STYLES[PanelType.SUCCESS]

        return Panel(
            Text(message, style=styles["title"]),
            title=f"[{styles['title']}]{title}[/]",
            border_style=Style(color=styles["border"]),
            padding=(0, 1),
            expand=False,
        )

    @staticmethod
    def render_warning(title: str, message: str) -> RenderableType:
        styles = PANEL_STYLES[PanelType.WARNING]

        return Panel(
            Text(message, style=styles["title"]),
            title=f"[{styles['title']}]{title}[/]",
            border_style=Style(color=styles["border"]),
            padding=(0, 1),
            expand=False,
        )


def _truncate_value(value: Any, max_length: int = 50) -> str:
    str_value = str(value)
    if len(str_value) <= max_length:
        return str_value
    return str_value[: max_length - 3] + "..."


def _truncate_content(
    content: str,
    max_lines: int = MAX_PANEL_LINES,
    max_line_width: int = MAX_PANEL_LINE_WIDTH,
) -> tuple[str, int, int]:
    """
    Line-aware truncation preserving structure.

    Returns: (truncated_content, shown_lines, total_lines)
    """
    lines = content.splitlines()
    total = len(lines)

    if total <= max_lines:
        # Still truncate individual long lines
        truncated = []
        for line in lines:
            if len(line) > max_line_width:
                truncated.append(line[:max_line_width] + "...")
            else:
                truncated.append(line)
        return "\n".join(truncated), total, total

    # Take first max_lines, truncate individual lines if too wide
    truncated = []
    for line in lines[:max_lines]:
        if len(line) > max_line_width:
            truncated.append(line[:max_line_width] + "...")
        else:
            truncated.append(line)

    return "\n".join(truncated), max_lines, total


def _truncate_search_results(
    results: list[dict[str, Any]],
    max_display: int = MAX_SEARCH_RESULTS_DISPLAY,
) -> tuple[list[dict[str, Any]], int, int]:
    """
    Truncate search results list with count info.

    Returns: (truncated_results, shown_count, total_count)
    """
    total = len(results)
    if total <= max_display:
        return results, total, total
    return results[:max_display], max_display, total


def tool_panel(
    name: str,
    status: str,
    args: dict[str, Any] | None = None,
    result: str | None = None,
    duration_ms: float | None = None,
) -> RenderableType:
    data = ToolDisplayData(
        tool_name=name,
        status=status,
        arguments=args or {},
        result=result,
        duration_ms=duration_ms,
        timestamp=datetime.now(),
    )
    return RichPanelRenderer.render_tool(data)


def error_panel(
    error_type: str,
    message: str,
    suggested_fix: str | None = None,
    recovery_commands: list[str] | None = None,
    severity: str = "error",
) -> RenderableType:
    data = ErrorDisplayData(
        error_type=error_type,
        message=message,
        suggested_fix=suggested_fix,
        recovery_commands=recovery_commands,
        severity=severity,
    )
    return RichPanelRenderer.render_error(data)


def search_panel(
    query: str,
    results: list[dict[str, Any]],
    total_count: int | None = None,
    page: int = 1,
    search_time_ms: float | None = None,
) -> RenderableType:
    data = SearchResultData(
        query=query,
        results=results,
        total_count=total_count or len(results),
        current_page=page,
        search_time_ms=search_time_ms,
    )
    return RichPanelRenderer.render_search_results(data)


def tool_panel_smart(
    name: str,
    status: str,
    args: dict[str, Any] | None = None,
    result: str | None = None,
    duration_ms: float | None = None,
) -> RenderableType:
    """Route tool output to NeXTSTEP-style renderers.

    Each tool has a dedicated renderer with 4-zone layout:
    - Header: identifier + summary
    - Parameters: selection context
    - Viewport: primary content
    - Status: metrics, truncation info
    """
    # Only apply custom renderers for completed tools with results
    if status == "completed" and result:
        from tunacode.ui.renderers.tools import (
            render_bash,
            render_glob,
            render_grep,
            render_list_dir,
            render_read_file,
            render_research_codebase,
            render_update_file,
            render_web_fetch,
        )

        # Map tool names to their renderers
        renderer_map = {
            "list_dir": render_list_dir,
            "grep": render_grep,
            "glob": render_glob,
            "read_file": render_read_file,
            "update_file": render_update_file,
            "bash": render_bash,
            "web_fetch": render_web_fetch,
            "research_codebase": render_research_codebase,
        }

        renderer = renderer_map.get(name.lower())
        if renderer:
            panel = renderer(args, result, duration_ms)
            if panel:
                return panel

    # Fallback to generic panel for unsupported tools or failed renders
    return tool_panel(name, status, args, result, duration_ms)


def _try_parse_search_result(
    tool_name: str,
    args: dict[str, Any] | None,
    result: str,
) -> SearchResultData | None:
    from tunacode.ui.renderers.search import SearchDisplayRenderer

    query = None
    if args:
        query = args.get("pattern") or args.get("query")

    if tool_name.lower() == "grep":
        return SearchDisplayRenderer.parse_grep_output(result, query)
    elif tool_name.lower() == "glob":
        return SearchDisplayRenderer.parse_glob_output(result, query)

    return None
