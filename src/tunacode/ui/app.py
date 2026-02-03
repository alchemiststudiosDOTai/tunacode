"""Textual-based REPL shell - Application entry point."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime
from typing import Any, Never

from rich.console import RenderableType
from rich.markdown import Markdown
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import LoadingIndicator, Static

from tunacode.core.agents.main import process_request
from tunacode.core.constants import (
    MIN_TOOL_PANEL_LINE_WIDTH,
    RICHLOG_CLASS_STREAMING,
    TOOL_PANEL_HORIZONTAL_INSET,
    build_nextstep_theme,
    build_tunacode_theme,
)
from tunacode.core.shared_types import ModelName
from tunacode.core.state import StateManager

from tunacode.ui.esc.handler import EscHandler
from tunacode.ui.renderers.errors import render_exception
from tunacode.ui.renderers.panels import tool_panel_smart
from tunacode.ui.repl_support import (
    StatusBarLike,
    build_textual_tool_callback,
    build_tool_result_callback,
    build_tool_start_callback,
    format_user_message,
)
from tunacode.ui.shell_runner import ShellRunner
from tunacode.ui.styles import STYLE_PRIMARY, STYLE_WARNING
from tunacode.ui.welcome import show_welcome
from tunacode.ui.widgets import (
    ChatContainer,
    CommandAutoComplete,
    Editor,
    EditorSubmitRequested,
    FileAutoComplete,
    ResourceBar,
    StatusBar,
    ToolResultDisplay,
)


class TextualReplApp(App[None]):
    TITLE = "TunaCode"
    CSS_PATH = [
        "styles/layout.tcss",
        "styles/widgets.tcss",
        "styles/modals.tcss",
        "styles/panels.tcss",
        "styles/theme-nextstep.tcss",
    ]

    BINDINGS = [
        Binding("escape", "cancel_request", "Cancel", show=False, priority=True),
    ]

    def __init__(self, *, state_manager: StateManager, show_setup: bool = False) -> None:
        super().__init__()
        self.state_manager: StateManager = state_manager
        self._show_setup: bool = show_setup
        self.request_queue: asyncio.Queue[str] = asyncio.Queue()

        self._current_request_task: asyncio.Task | None = None
        self._loading_indicator_shown: bool = False
        self._request_start_time: float = 0.0
        self._esc_handler: EscHandler = EscHandler()

        self.shell_runner = ShellRunner(self)

        self.chat_container: ChatContainer
        self.editor: Editor
        self.resource_bar: ResourceBar
        self.status_bar: StatusBarLike
        self.streaming_output: Static

    def compose(self) -> ComposeResult:
        self.resource_bar = ResourceBar()
        self.chat_container = ChatContainer(id="chat-container", auto_scroll=True)
        self.streaming_output = Static("", id="streaming-output")
        self.loading_indicator = LoadingIndicator()
        self.editor = Editor()
        self.status_bar = StatusBar()

        yield self.resource_bar
        with Container(id="viewport"):
            yield self.chat_container
            yield self.loading_indicator
        yield self.streaming_output
        yield self.editor
        yield FileAutoComplete(self.editor)
        yield CommandAutoComplete(self.editor)
        yield self.status_bar

    @property
    def rich_log(self) -> ChatContainer:
        """Backward compatibility alias for chat_container."""
        return self.chat_container

    def on_mount(self) -> None:
        tunacode_theme = build_tunacode_theme()
        self.register_theme(tunacode_theme)
        nextstep_theme = build_nextstep_theme()
        self.register_theme(nextstep_theme)

        user_config = self.state_manager.session.user_config
        saved_theme = user_config.get("settings", {}).get("theme", "dracula")
        self.theme = saved_theme if saved_theme in self.available_themes else "dracula"

        # Initialize session persistence metadata
        from tunacode.core.system_paths import get_project_id

        session = self.state_manager.session
        session.project_id = get_project_id()
        session.working_directory = os.getcwd()
        if not session.created_at:
            session.created_at = datetime.now(UTC).isoformat()

        if self._show_setup:
            from tunacode.ui.screens import SetupScreen

            self.push_screen(SetupScreen(self.state_manager), self._on_setup_complete)
        else:
            self._start_repl()

    async def on_unmount(self) -> None:
        """Save session before app exits."""
        await self.state_manager.save_session()

    def watch_theme(self, old_theme: str, new_theme: str) -> None:
        """Toggle CSS class when theme changes for theme-specific styling."""
        if old_theme:
            self.remove_class(f"theme-{old_theme}")
        if new_theme:
            self.add_class(f"theme-{new_theme}")

    def _on_setup_complete(self, completed: bool | None) -> None:
        """Called when setup screen is dismissed."""
        if completed:
            self._update_resource_bar()
        self._start_repl()

    def _start_repl(self) -> None:
        """Initialize REPL components after setup."""
        from tunacode.core.logging import get_logger

        # Initialize logging with TUI callback
        logger = get_logger()
        logger.set_state_manager(self.state_manager)

        def _write_tui(renderable: RenderableType) -> None:
            self.rich_log.write(renderable)

        logger.set_tui_callback(_write_tui)

        self.set_focus(self.editor)
        self.run_worker(self._request_worker, exclusive=False)
        self._update_resource_bar()
        show_welcome(self.rich_log)

    async def _request_worker(self) -> Never:
        while True:
            request = await self.request_queue.get()
            try:
                await self._process_request(request)
            except Exception as e:
                error_renderable = render_exception(e)
                self.rich_log.write(error_renderable)
            finally:
                self.request_queue.task_done()

    async def _process_request(self, message: str) -> None:
        session = self.state_manager.session

        self._request_start_time = time.monotonic()
        self.query_one("#viewport").remove_class(RICHLOG_CLASS_STREAMING)
        self.chat_container.clear_insertion_anchor()

        self._loading_indicator_shown = True
        self.loading_indicator.add_class("active")

        try:
            model_name = session.current_model or "openai/gpt-4o"

            self._current_request_task = asyncio.create_task(
                process_request(
                    message=message,
                    model=ModelName(model_name),
                    state_manager=self.state_manager,
                    tool_callback=build_textual_tool_callback(),
                    streaming_callback=None,
                    tool_result_callback=build_tool_result_callback(self),
                    tool_start_callback=build_tool_start_callback(self),
                    notice_callback=self._show_system_notice,
                )
            )
            await self._current_request_task
        except asyncio.CancelledError:
            self.notify("Cancelled")
        except Exception as e:
            error_renderable = render_exception(e)
            self.rich_log.write(error_renderable)
        finally:
            self._current_request_task = None
            self._loading_indicator_shown = False
            self.loading_indicator.remove_class("active")
            self.query_one("#viewport").remove_class(RICHLOG_CLASS_STREAMING)
            self.streaming_output.update("")
            self.streaming_output.remove_class("active")

            output_text = self._get_latest_response_text()

            if output_text is not None:
                from tunacode.ui.renderers.agent_response import render_agent_response

                duration_ms = (time.monotonic() - self._request_start_time) * 1000
                session = self.state_manager.session
                tokens = session.usage.last_call_usage.completion_tokens
                model = session.current_model or ""

                panel = render_agent_response(
                    content=output_text,
                    tokens=tokens,
                    duration_ms=duration_ms,
                    model=model,
                )
                self.chat_container.write("")
                response_widget = self.chat_container.write(panel, expand=True)
                self.chat_container.set_insertion_anchor(response_widget)

            self._update_resource_bar()

            # Auto-save session after processing
            await self.state_manager.save_session()

    def _get_latest_response_text(self) -> str | None:
        from pydantic_ai.messages import ModelResponse

        from tunacode.core.messaging import get_content

        messages = self.state_manager.session.conversation.messages
        for message in reversed(messages):
            if not isinstance(message, ModelResponse):
                continue

            raw_content = get_content(message)
            normalized_content = raw_content.strip()
            if normalized_content:
                return normalized_content

        return None

    async def on_editor_submit_requested(self, message: EditorSubmitRequested) -> None:
        from tunacode.ui.commands import handle_command

        if await handle_command(self, message.text):
            return

        await self.request_queue.put(message.text)

        from datetime import datetime

        timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")

        self.rich_log.write("")
        render_width = max(1, self.rich_log.size.width - 2)

        user_block = format_user_message(message.text, STYLE_PRIMARY, width=render_width)

        user_block.append(f"│ you {timestamp}", style=f"dim {STYLE_PRIMARY}")
        self.rich_log.write(user_block)

    def on_tool_result_display(self, message: ToolResultDisplay) -> None:
        max_line_width = self.tool_panel_max_width()
        panel = tool_panel_smart(
            name=message.tool_name,
            status=message.status,
            args=message.args,
            result=message.result,
            duration_ms=message.duration_ms,
            max_line_width=max_line_width,
        )
        self.chat_container.write(panel)

    def tool_panel_max_width(self) -> int:
        viewport = self.query_one("#viewport")
        width_candidates = [
            self.chat_container.content_region.width,
            viewport.content_region.width,
            self.chat_container.size.width,
            viewport.size.width,
            self.size.width,
        ]
        usable_widths = [width for width in width_candidates if width > 0]
        content_width = max(usable_widths, default=MIN_TOOL_PANEL_LINE_WIDTH)
        available_width = content_width - TOOL_PANEL_HORIZONTAL_INSET
        max_line_width = max(MIN_TOOL_PANEL_LINE_WIDTH, available_width)
        return max_line_width

    def _show_system_notice(self, notice: str) -> None:
        notice_text = Text(notice, style=STYLE_WARNING)
        self.rich_log.write(notice_text)

    def _is_user_prompt_request(self, message: Any) -> bool:
        parts = getattr(message, "parts", None)
        if not parts:
            return False

        return any(getattr(part, "part_kind", None) == "user-prompt" for part in parts)

    def _replay_session_messages(self) -> None:
        """Render loaded session messages to RichLog."""
        from pydantic_ai.messages import ModelRequest, ModelResponse

        from tunacode.core.messaging import get_content

        conversation = self.state_manager.session.conversation
        for msg in conversation.messages:
            content = get_content(msg)
            if not content:
                continue

            if isinstance(msg, ModelRequest):
                if not self._is_user_prompt_request(msg):
                    continue
                user_block = Text()
                user_block.append(f"| {content}\n", style=STYLE_PRIMARY)
                user_block.append("| (restored)", style=f"dim {STYLE_PRIMARY}")
                self.rich_log.write(user_block)
            elif isinstance(msg, ModelResponse):
                self.rich_log.write(Text("agent:", style="accent"))
                self.rich_log.write(Markdown(content))

    def action_cancel_request(self) -> None:
        """Cancel the current request, shell command, or clear editor input."""
        esc_handler = self._esc_handler
        current_request_task = self._current_request_task
        shell_runner = getattr(self, "shell_runner", None)
        editor = self.editor

        esc_handler.handle_escape(
            current_request_task=current_request_task,
            shell_runner=shell_runner,
            editor=editor,
        )

    def start_shell_command(self, raw_cmd: str) -> None:
        self.shell_runner.start(raw_cmd)

    def write_shell_output(self, renderable: RenderableType) -> None:
        self.rich_log.write(renderable)

    def shell_status_running(self) -> None:
        self.status_bar.update_running_action("shell")

    def shell_status_last(self) -> None:
        self.status_bar.update_last_action("shell")

    def _update_resource_bar(self) -> None:
        session = self.state_manager.session
        conversation = session.conversation

        # Use accumulated API usage totals for token display
        usage_total_tokens = session.usage.session_total_usage.total_tokens

        self.resource_bar.update_stats(
            model=session.current_model or "No model selected",
            tokens=usage_total_tokens,
            max_tokens=conversation.max_tokens or 200000,
        )

    def update_lsp_for_file(self, filepath: str) -> None:
        """Update ResourceBar LSP status based on file type.

        Args:
            filepath: Path to the file being edited
        """
        from tunacode.core.lsp_status import get_lsp_server_info

        info = get_lsp_server_info(filepath)
        self.resource_bar.update_lsp_status(info.server_name, info.available)
