"""Textual-based REPL shell - Application entry point."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import LoadingIndicator, RichLog, Static

from tunacode.constants import (
    MAX_CALLBACK_CONTENT,
    RICHLOG_CLASS_PAUSED,
    RICHLOG_CLASS_STREAMING,
    build_nextstep_theme,
    build_tunacode_theme,
)
from tunacode.core.agents.main import process_request
from tunacode.indexing import CodeIndex
from tunacode.tools.authorization.handler import ToolHandler
from tunacode.types import (
    ModelName,
    StateManager,
    ToolConfirmationRequest,
    ToolConfirmationResponse,
)
from tunacode.ui.renderers.errors import render_exception
from tunacode.ui.renderers.panels import tool_panel_smart
from tunacode.ui.styles import (
    STYLE_ERROR,
    STYLE_HEADING,
    STYLE_MUTED,
    STYLE_PRIMARY,
    STYLE_SUBHEADING,
    STYLE_SUCCESS,
    STYLE_WARNING,
)
from tunacode.ui.widgets import (
    CommandAutoComplete,
    Editor,
    EditorSubmitRequested,
    FileAutoComplete,
    ResourceBar,
    StatusBar,
    ToolResultDisplay,
)

# Throttle streaming display updates to reduce visual churn
STREAM_THROTTLE_MS: float = 200.0

# Collapse threshold for pasted content display
COLLAPSE_THRESHOLD = 10


def _format_collapsed_message(text: str, style: str) -> Text:
    """Format long pasted text with collapsed middle section.

    Shows first 3 lines, collapse indicator, and last 2 lines.
    """
    lines = text.split("\n")
    line_count = len(lines)

    if line_count <= COLLAPSE_THRESHOLD:
        block = Text()
        block.append(f"│ {text}\n", style=style)
        return block

    # Show first 3 and last 2 lines with collapse indicator
    preview = "\n│ ".join(lines[:3])
    suffix = "\n│ ".join(lines[-2:])
    collapsed = line_count - 5

    block = Text()
    block.append(f"│ {preview}\n", style=style)
    block.append(f"│ [[ {collapsed} more lines ]]\n", style=f"dim {style}")
    block.append(f"│ {suffix}\n", style=style)
    return block


@dataclass
class PendingConfirmationState:
    """Tracks pending tool confirmation state."""

    future: asyncio.Future[ToolConfirmationResponse]
    request: ToolConfirmationRequest


class TextualReplApp(App[None]):
    TITLE = "TunaCode"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("ctrl+p", "toggle_pause", "Pause/Resume Stream", show=False, priority=True),
        Binding("escape", "cancel_stream", "Cancel", show=False, priority=True),
    ]

    def __init__(self, *, state_manager: StateManager, show_setup: bool = False) -> None:
        super().__init__()
        self.state_manager: StateManager = state_manager
        self._show_setup: bool = show_setup
        self.request_queue: asyncio.Queue[str] = asyncio.Queue()
        self.pending_confirmation: PendingConfirmationState | None = None

        self._streaming_paused: bool = False
        self._streaming_cancelled: bool = False
        self._stream_buffer: list[str] = []
        self.current_stream_text: str = ""
        self._current_request_task: asyncio.Task | None = None
        self._loading_indicator_shown: bool = False
        self._last_display_update: float = 0.0

        self.rich_log: RichLog
        self.editor: Editor
        self.resource_bar: ResourceBar
        self.status_bar: StatusBar
        self.streaming_output: Static

    def compose(self) -> ComposeResult:
        self.resource_bar = ResourceBar()
        self.rich_log = RichLog(wrap=True, markup=True, highlight=True, auto_scroll=True)
        self.streaming_output = Static("", id="streaming-output")
        self.loading_indicator = LoadingIndicator()
        self.editor = Editor()
        self.status_bar = StatusBar()

        yield self.resource_bar
        with Container(id="viewport"):
            yield self.rich_log
            yield self.streaming_output
            yield self.loading_indicator
        yield self.editor
        yield FileAutoComplete(self.editor)
        yield CommandAutoComplete(self.editor)
        yield self.status_bar

    def on_mount(self) -> None:
        tunacode_theme = build_tunacode_theme()
        self.register_theme(tunacode_theme)
        nextstep_theme = build_nextstep_theme()
        self.register_theme(nextstep_theme)

        user_config = self.state_manager.session.user_config
        saved_theme = user_config.get("settings", {}).get("theme", "dracula")
        self.theme = saved_theme if saved_theme in self.available_themes else "dracula"

        # Initialize session persistence metadata
        from tunacode.utils.system.paths import get_project_id

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
        self.state_manager.save_session()

    def watch_theme(self, old_theme: str, new_theme: str) -> None:
        """Toggle CSS class when theme changes for theme-specific styling."""
        if old_theme:
            self.remove_class(f"theme-{old_theme}")
        if new_theme:
            self.add_class(f"theme-{new_theme}")

    def _on_setup_complete(self, completed: bool) -> None:
        """Called when setup screen is dismissed."""
        if completed:
            self._update_resource_bar()
        self._start_repl()

    def _start_repl(self) -> None:
        """Initialize REPL components after setup."""
        self.set_focus(self.editor)
        self.run_worker(self._request_worker, exclusive=False)
        self.run_worker(self._startup_index_worker, exclusive=False)
        self._update_resource_bar()
        self._show_welcome()

    async def _startup_index_worker(self) -> None:
        """Build startup index with dynamic sizing."""
        import asyncio

        def do_index() -> tuple[int, int | None, bool]:
            """Returns (indexed_count, total_or_none, is_partial)."""
            index = CodeIndex.get_instance()
            total = index.quick_count()

            if total < CodeIndex.QUICK_INDEX_THRESHOLD:
                index.build_index()
                return len(index._all_files), None, False
            else:
                count = index.build_priority_index()
                return count, total, True

        loop = asyncio.get_event_loop()
        indexed, total, is_partial = await loop.run_in_executor(None, do_index)

        if is_partial:
            msg = Text()
            msg.append(
                f"Code cache: {indexed}/{total} files indexed, expanding...",
                style=STYLE_MUTED,
            )
            self.rich_log.write(msg)

            # Expand in background
            def do_expand() -> int:
                index = CodeIndex.get_instance()
                index.expand_index()
                return len(index._all_files)

            final_count = await loop.run_in_executor(None, do_expand)
            done_msg = Text()
            done_msg.append(f"Code cache built: {final_count} files indexed ✓", style=STYLE_SUCCESS)
            self.rich_log.write(done_msg)
        else:
            msg = Text()
            msg.append(f"Code cache built: {indexed} files indexed ✓", style=STYLE_SUCCESS)
            self.rich_log.write(msg)

    def _show_welcome(self) -> None:
        welcome = Text()
        welcome.append("Welcome to TunaCode\n", style=STYLE_HEADING)
        welcome.append("AI coding assistant for your terminal.\n\n", style=STYLE_MUTED)
        welcome.append("Commands:\n", style=STYLE_PRIMARY)
        welcome.append("  /help    - Show all commands\n", style="")
        welcome.append("  /clear   - Clear conversation\n", style="")
        welcome.append("  /yolo    - Toggle auto-confirm\n", style="")
        welcome.append("  /branch  - Create git branch\n", style="")
        welcome.append("  /plan    - Toggle planning mode\n", style="")
        welcome.append("  /model   - Switch model\n", style="")
        welcome.append("  /theme   - Switch theme\n", style="")
        welcome.append("  /resume  - Load saved session\n", style="")
        welcome.append("  !<cmd>   - Run shell command\n", style="")
        self.rich_log.write(welcome)

    async def _request_worker(self) -> None:
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
        self.current_stream_text = ""
        self._last_display_update = 0.0
        self._streaming_cancelled = False
        self.query_one("#viewport").add_class(RICHLOG_CLASS_STREAMING)

        self._loading_indicator_shown = True
        self.loading_indicator.add_class("active")

        try:
            model_name = self.state_manager.session.current_model or "openai/gpt-4o"

            # Set progress callback on session for subagent progress tracking
            self.state_manager.session.tool_progress_callback = build_tool_progress_callback(self)

            self._current_request_task = asyncio.create_task(
                process_request(
                    message=message,
                    model=ModelName(model_name),
                    state_manager=self.state_manager,
                    tool_callback=build_textual_tool_callback(self, self.state_manager),
                    streaming_callback=self.streaming_callback,
                    tool_result_callback=build_tool_result_callback(self),
                    tool_start_callback=build_tool_start_callback(self),
                )
            )
            await self._current_request_task
        except asyncio.CancelledError:
            from tunacode.core.agents.agent_components import patch_tool_messages

            patch_tool_messages(
                "Operation cancelled by user",
                state_manager=self.state_manager,
            )
            self.notify("Cancelled")
        except Exception as e:
            from tunacode.core.agents.agent_components import patch_tool_messages

            patch_tool_messages(
                f"Request failed: {type(e).__name__}",
                state_manager=self.state_manager,
            )
            error_renderable = render_exception(e)
            self.rich_log.write(error_renderable)
        finally:
            self._current_request_task = None
            self._loading_indicator_shown = False
            self.loading_indicator.remove_class("active")
            self.query_one("#viewport").remove_class(RICHLOG_CLASS_STREAMING)
            self.query_one("#viewport").remove_class(RICHLOG_CLASS_PAUSED)
            self.streaming_output.update("")
            self.streaming_output.remove_class("active")

            if self.current_stream_text and not self._streaming_cancelled:
                self.rich_log.write("")
                self.rich_log.write(Text("agent:", style="accent"))
                self.rich_log.write(Markdown(self.current_stream_text))

            self.current_stream_text = ""
            self._streaming_cancelled = False
            self._update_resource_bar()

            # Auto-save session after processing
            self.state_manager.save_session()

    async def on_editor_submit_requested(self, message: EditorSubmitRequested) -> None:
        from tunacode.ui.commands import handle_command

        if await handle_command(self, message.text):
            return

        await self.request_queue.put(message.text)

        from datetime import datetime

        timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")
        line_count = message.text.count("\n") + 1

        self.rich_log.write("")

        # Collapse only if pasted AND exceeds threshold
        if message.was_pasted and line_count > COLLAPSE_THRESHOLD:
            user_block = _format_collapsed_message(message.text, STYLE_PRIMARY)
        else:
            user_block = Text()
            user_block.append(f"│ {message.text}\n", style=STYLE_PRIMARY)

        user_block.append(f"│ you {timestamp}", style=f"dim {STYLE_PRIMARY}")
        self.rich_log.write(user_block)

    async def request_tool_confirmation(
        self, request: ToolConfirmationRequest
    ) -> ToolConfirmationResponse:
        if self.pending_confirmation is not None and not self.pending_confirmation.future.done():
            raise RuntimeError("Previous confirmation still pending")

        future: asyncio.Future[ToolConfirmationResponse] = asyncio.Future()
        self.pending_confirmation = PendingConfirmationState(future=future, request=request)
        self._show_inline_confirmation(request)
        return await future

    def on_tool_result_display(self, message: ToolResultDisplay) -> None:
        panel = tool_panel_smart(
            name=message.tool_name,
            status=message.status,
            args=message.args,
            result=message.result,
            duration_ms=message.duration_ms,
        )
        self.rich_log.write(panel)

    def _replay_session_messages(self) -> None:
        """Render loaded session messages to RichLog."""
        from pydantic_ai.messages import ModelRequest, ModelResponse

        from tunacode.utils.messaging.message_utils import get_message_content

        for msg in self.state_manager.session.messages:
            if isinstance(msg, dict) and "thought" in msg:
                continue  # Skip internal thoughts

            content = get_message_content(msg)
            if not content:
                continue

            if isinstance(msg, ModelRequest):
                user_block = Text()
                user_block.append(f"| {content}\n", style=STYLE_PRIMARY)
                user_block.append("| (restored)", style=f"dim {STYLE_PRIMARY}")
                self.rich_log.write(user_block)
            elif isinstance(msg, ModelResponse):
                self.rich_log.write(Text("agent:", style="accent"))
                self.rich_log.write(Markdown(content))

    async def streaming_callback(self, chunk: str) -> None:
        if self._streaming_paused:
            self._stream_buffer.append(chunk)
            return

        # Always accumulate immediately
        self.current_stream_text += chunk

        # Throttle display updates to reduce visual churn
        now = time.monotonic()
        elapsed_ms = (now - self._last_display_update) * 1000

        if elapsed_ms >= STREAM_THROTTLE_MS:
            self._last_display_update = now
            self.streaming_output.update(Markdown(self.current_stream_text))
            self.streaming_output.add_class("active")
            self.rich_log.scroll_end()

    def action_toggle_pause(self) -> None:
        if self._streaming_paused:
            self.resume_streaming()
        else:
            self.pause_streaming()

    def pause_streaming(self) -> None:
        self._streaming_paused = True
        self.query_one("#viewport").add_class(RICHLOG_CLASS_PAUSED)
        self.notify("Streaming paused...")

    def resume_streaming(self) -> None:
        self._streaming_paused = False
        self.query_one("#viewport").remove_class(RICHLOG_CLASS_PAUSED)
        self.notify("Streaming resumed...")

        if self._stream_buffer:
            buffered_text = "".join(self._stream_buffer)
            self.current_stream_text += buffered_text
            self._stream_buffer.clear()

        # Force immediate display update on resume
        self._last_display_update = time.monotonic()
        self.streaming_output.update(Markdown(self.current_stream_text))

    def action_cancel_stream(self) -> None:
        # If confirmation is pending, Escape rejects it
        if self.pending_confirmation is not None and not self.pending_confirmation.future.done():
            response = ToolConfirmationResponse(approved=False, skip_future=False, abort=True)
            self.pending_confirmation.future.set_result(response)
            self.pending_confirmation = None
            self.rich_log.write(Text("Rejected", style=STYLE_ERROR))
            return

        # Otherwise, cancel the stream
        if self._current_request_task is None:
            return
        self._streaming_cancelled = True
        self._stream_buffer.clear()
        self.current_stream_text = ""
        self._current_request_task.cancel()

    def _update_resource_bar(self) -> None:
        session = self.state_manager.session
        usage = session.session_total_usage

        # Use actual context window tokens, not cumulative API usage
        context_tokens = session.total_tokens

        self.resource_bar.update_stats(
            model=session.current_model or "No model selected",
            tokens=context_tokens,
            max_tokens=session.max_tokens or 200000,
            session_cost=usage.get("cost", 0.0),
        )

    def _show_inline_confirmation(self, request: ToolConfirmationRequest) -> None:
        """Display inline confirmation prompt in RichLog."""
        content_parts: list[Text | Syntax] = []

        # Header
        header = Text()
        header.append(f"Confirm: {request.tool_name}\n", style=STYLE_SUBHEADING)
        content_parts.append(header)

        # Arguments
        args_text = Text()
        for key, value in request.args.items():
            display_value = str(value)
            if len(display_value) > 60:
                display_value = display_value[:57] + "..."
            args_text.append(f"  {key}: ", style=STYLE_MUTED)
            args_text.append(f"{display_value}\n")
        content_parts.append(args_text)

        # Diff Preview (if available)
        if request.diff_content:
            content_parts.append(Text("\nPreview changes:\n", style="bold"))
            content_parts.append(
                Syntax(request.diff_content, "diff", theme="monokai", word_wrap=True)
            )
            content_parts.append(Text("\n"))

        # Footer Actions
        actions = Text()
        actions.append("\n")
        actions.append("[1]", style=f"bold {STYLE_SUCCESS}")
        actions.append(" Yes  ")
        actions.append("[2]", style=f"bold {STYLE_WARNING}")
        actions.append(" Yes + Skip  ")
        actions.append("[3]", style=f"bold {STYLE_ERROR}")
        actions.append(" No")
        content_parts.append(actions)

        # Use Group to stack components vertically
        from rich.console import Group

        panel = Panel(
            Group(*content_parts),
            border_style=STYLE_PRIMARY,
            padding=(0, 1),
            expand=False,
        )
        self.rich_log.write(panel)

    def on_key(self, event: events.Key) -> None:
        """Handle key events, intercepting confirmation keys when pending."""
        if self.pending_confirmation is None or self.pending_confirmation.future.done():
            return

        response: ToolConfirmationResponse | None = None

        if event.key == "1":
            response = ToolConfirmationResponse(approved=True, skip_future=False, abort=False)
            self.rich_log.write(Text("Approved", style=STYLE_SUCCESS))
        elif event.key == "2":
            response = ToolConfirmationResponse(approved=True, skip_future=True, abort=False)
            self.rich_log.write(Text("Approved (skipping future)", style=STYLE_WARNING))
        elif event.key == "3":
            response = ToolConfirmationResponse(approved=False, skip_future=False, abort=True)
            self.rich_log.write(Text("Rejected", style=STYLE_ERROR))

        if response is not None:
            self.pending_confirmation.future.set_result(response)
            self.pending_confirmation = None
            event.stop()


async def run_textual_repl(state_manager: StateManager, show_setup: bool = False) -> None:
    app = TextualReplApp(state_manager=state_manager, show_setup=show_setup)
    await app.run_async()


def build_textual_tool_callback(app: TextualReplApp, state_manager: StateManager):
    async def _callback(part: Any, _node: Any = None) -> None:
        tool_handler = state_manager.tool_handler or ToolHandler(state_manager)
        state_manager.set_tool_handler(tool_handler)

        if not tool_handler.should_confirm(part.tool_name):
            return

        from tunacode.exceptions import UserAbortError
        from tunacode.utils.parsing.command_parser import parse_args

        args = parse_args(part.args)
        request = tool_handler.create_confirmation_request(part.tool_name, args)
        response = await app.request_tool_confirmation(request)
        if not tool_handler.process_confirmation(response, part.tool_name):
            raise UserAbortError("User aborted tool execution")

    return _callback


FILE_EDIT_TOOLS = frozenset({"write_file", "update_file"})


def _truncate_for_safety(content: str | None) -> str | None:
    """Emergency truncation - prevents UI freeze on massive outputs."""
    if content is None:
        return None
    if len(content) <= MAX_CALLBACK_CONTENT:
        return content
    return content[:MAX_CALLBACK_CONTENT] + "\n... [truncated for safety]"


def build_tool_result_callback(app: TextualReplApp):
    def _callback(
        tool_name: str,
        status: str,
        args: dict,
        result: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        if tool_name in FILE_EDIT_TOOLS and status == "completed":
            filepath = args.get("filepath")
            if filepath:
                app.status_bar.add_edited_file(filepath)

        app.status_bar.update_last_action(tool_name)

        # Emergency safety truncation before display processing
        safe_result = _truncate_for_safety(result)

        app.post_message(
            ToolResultDisplay(
                tool_name=tool_name,
                status=status,
                args=args,
                result=safe_result,
                duration_ms=duration_ms,
            )
        )

    return _callback


def build_tool_start_callback(app: TextualReplApp) -> Callable[[str], None]:
    """Build callback for tool start notifications."""

    def _callback(tool_name: str) -> None:
        app.status_bar.update_running_action(tool_name)

    return _callback


def build_tool_progress_callback(app: TextualReplApp) -> Callable[[str, str, int, int], None]:
    """Build callback for subagent tool progress notifications.

    Args:
        app: The TextualReplApp instance

    Returns:
        Callback function that updates status bar with subagent progress
    """

    def _callback(subagent: str, operation: str, current: int, total: int) -> None:
        app.status_bar.update_subagent_progress(subagent, operation, current, total)

    return _callback
