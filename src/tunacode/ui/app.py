"""Textual-based REPL shell - Application entry point."""

from __future__ import annotations

# ruff: noqa: I001

import asyncio
import time
from typing import TYPE_CHECKING, Never

from rich.console import RenderableType
from rich.text import Text
from tinyagent.agent_types import AgentMessage
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.timer import Timer
from textual.widgets import LoadingIndicator, Static

if TYPE_CHECKING:
    from textual.theme import Theme

    from tunacode.core.session import StateManager
    from tunacode.ui.lifecycle import AppLifecycle
    from tunacode.ui.shell_runner import ShellRunner

from tunacode.core.ui_api.constants import (
    MIN_TOOL_PANEL_LINE_WIDTH,
    RESOURCE_BAR_COST_FORMAT,
    RICHLOG_CLASS_STREAMING,
    SUPPORTED_THEME_NAMES,
    THEME_NAME,
    TOOL_PANEL_HORIZONTAL_INSET,
    build_nextstep_theme,
    build_tunacode_theme,
    wrap_builtin_themes,
)
from tunacode.ui.context_panel import (
    build_context_gauge,
    build_context_panel_widgets,
    build_files_field,
    build_skills_field,
    is_widget_within_field,
    token_color,
    token_remaining_pct,
)
from tunacode.ui.esc.handler import EscHandler
from tunacode.ui.esc.types import RequestTask
from tunacode.ui.renderers.thinking import (
    DEFAULT_THINKING_MAX_CHARS,
    DEFAULT_THINKING_MAX_LINES,
)
from tunacode.ui.repl_support import (
    FILE_EDIT_TOOLS,
    build_tool_result_callback,
    format_user_message,
    normalize_agent_message_text,
)
from tunacode.ui.request_debug import RequestDebugTracer, SubmissionTrace
from tunacode.ui.request_bridge import RequestUiBridge
from tunacode.ui.slopgotchi import (
    SlopgotchiHandler,
    SlopgotchiPanelState,
)
from tunacode.ui.streaming import StreamingHandler
from tunacode.ui.styles import STYLE_PRIMARY, STYLE_SUCCESS, STYLE_WARNING
from tunacode.ui.widgets import (
    ChatContainer,
    CommandAutoComplete,
    CompactionStatusChanged,
    Editor,
    EditorSubmitRequested,
    FileAutoComplete,
    ResourceBar,
    SkillsAutoComplete,
    SystemNoticeDisplay,
    ToolResultDisplay,
    TuiLogDisplay,
)


def copy_selection_to_clipboard(app: App[None], show_toast: bool = True) -> str | None:
    """Lazily import clipboard helpers to avoid startup cost on launch."""
    from tunacode.ui.clipboard import copy_selection_to_clipboard as _copy_selection_to_clipboard

    return _copy_selection_to_clipboard(app, show_toast=show_toast)


class TextualReplApp(App[None]):
    TITLE = "TunaCode"
    CSS_PATH = [
        "styles/layout.tcss",
        "styles/widgets.tcss",
        "styles/modals.tcss",
        "styles/panels.tcss",
    ]

    BINDINGS = [
        Binding("escape", "cancel_request", "Cancel", show=False, priority=True),
        Binding("ctrl+e", "toggle_context_panel", "Context", show=False, priority=True),
        Binding("ctrl+y", "copy_selection", "Copy", show=False, priority=True),
        Binding("ctrl+shift+c", "copy_selection", "Copy", show=False, priority=True),
    ]

    STREAM_THROTTLE_MS: float = 100.0
    MILLISECONDS_PER_SECOND: float = 1000.0
    THINKING_BUFFER_CHAR_LIMIT: int = 2400
    THINKING_MAX_RENDER_LINES: int = DEFAULT_THINKING_MAX_LINES
    THINKING_MAX_RENDER_CHARS: int = DEFAULT_THINKING_MAX_CHARS
    THINKING_THROTTLE_MS: float = STREAM_THROTTLE_MS
    THINKING_THROTTLE_WHILE_DRAFTING_MS: float = 275.0
    THINKING_DEFER_AFTER_KEYPRESS_MS: float = 150.0
    CONTEXT_PANEL_COLLAPSED_CLASS = "hidden"
    DEFAULT_CONTEXT_MAX_TOKENS: int = 200000
    CONTEXT_PANEL_MIN_TERMINAL_WIDTH: int = 80

    def __init__(self, *, state_manager: StateManager, show_setup: bool = False) -> None:
        super().__init__()
        self.register_theme(build_tunacode_theme())
        self.register_theme(build_nextstep_theme())
        for theme in wrap_builtin_themes(self.available_themes):
            self.register_theme(theme)
        self.theme = THEME_NAME
        self.state_manager: StateManager = state_manager
        self._show_setup: bool = show_setup
        self._lifecycle: AppLifecycle | None = None
        self.request_queue: asyncio.Queue[str] = asyncio.Queue()
        self._current_request_task: RequestTask | None = None
        self._loading_indicator_shown: bool = False
        self._request_start_time: float = 0.0
        self._esc_handler: EscHandler = EscHandler()
        self._shell_runner: ShellRunner | None = None
        self.chat_container: ChatContainer
        self.editor: Editor
        self.resource_bar: ResourceBar
        self.streaming_output: Static
        self._thinking_panel_widget: Static | None = None
        self._context_panel_visible: bool = False
        self._edited_files: set[str] = set()
        self._field_model: Static | None = None
        self._field_context: Static | None = None
        self._field_cost: Static | None = None
        self._field_files: Static | None = None
        self._field_skills: Static | None = None
        self._slopgotchi_state: SlopgotchiPanelState = SlopgotchiPanelState()
        self._field_slopgotchi: Static | None = None
        self._slopgotchi_handler: SlopgotchiHandler | None = None
        self._slopgotchi_timer: Timer | None = None
        self._request_bridge: RequestUiBridge | None = None
        self._delta_flush_timer: Timer | None = None

        self._current_thinking_text: str = ""
        self._last_thinking_update: float = 0.0
        self._last_editor_keypress_at: float = 0.0
        self._request_debug = RequestDebugTracer(self)

    def compose(self) -> ComposeResult:
        self.resource_bar = ResourceBar()
        self.chat_container = ChatContainer(id="chat-container", auto_scroll=True)
        self.streaming_output = Static("", id="streaming-output")
        self._thinking_panel_widget = Static("", id="thinking-output", classes="thinking-panel")
        self.streaming = StreamingHandler(self.streaming_output, self.STREAM_THROTTLE_MS)
        self.loading_indicator = LoadingIndicator()
        self.editor = Editor()
        yield self.resource_bar
        with Container(id="workspace"):
            with Container(id="viewport"):
                yield self.chat_container
                yield self.loading_indicator
                yield self._thinking_panel_widget
                yield self.streaming_output
            with (
                Container(id="context-rail", classes=self.CONTEXT_PANEL_COLLAPSED_CLASS) as rail,
                Container(id="context-panel"),
            ):
                rail.border_title = "Session Inspector"
                context_panel_widgets = build_context_panel_widgets()
                self._field_slopgotchi = context_panel_widgets.field_slopgotchi
                self._slopgotchi_handler = SlopgotchiHandler(
                    self._slopgotchi_state, self._field_slopgotchi
                )
                self._field_model = context_panel_widgets.field_model
                self._field_context = context_panel_widgets.field_context
                self._field_cost = context_panel_widgets.field_cost
                self._field_files = context_panel_widgets.field_files
                self._field_skills = context_panel_widgets.field_skills
                yield from context_panel_widgets.widgets
        yield self.editor
        yield FileAutoComplete(self.editor)
        yield CommandAutoComplete(self.editor)
        yield SkillsAutoComplete(self.editor)

    @property
    def supported_themes(self) -> dict[str, Theme]:
        return {
            theme_name: self.available_themes[theme_name]
            for theme_name in SUPPORTED_THEME_NAMES
            if theme_name in self.available_themes
        }

    @property
    def shell_runner(self) -> ShellRunner:
        shell_runner = self._shell_runner
        if shell_runner is None:
            from tunacode.ui.shell_runner import ShellRunner

            shell_runner = ShellRunner(self)
            self._shell_runner = shell_runner
        return shell_runner

    def on_mount(self) -> None:
        from tunacode.ui.lifecycle import AppLifecycle

        lifecycle = AppLifecycle(self)
        self._lifecycle = lifecycle
        lifecycle.mount()

    async def on_unmount(self) -> None:
        lifecycle = self._lifecycle
        if lifecycle is None:
            raise RuntimeError("AppLifecycle was not initialized before unmount")
        await lifecycle.unmount()

    async def _request_worker(self) -> Never:
        while True:
            request = await self.request_queue.get()
            submission_trace = self._request_debug.pop_next_submission_trace()
            try:
                await self._process_request(request, submission_trace)
            except Exception as e:
                from tunacode.ui.renderers.errors import render_exception

                content, meta = render_exception(e)
                self.chat_container.write(content, panel_meta=meta)
            finally:
                self.request_queue.task_done()

    def _should_stream_agent_text(self) -> bool:
        return self.state_manager.session.user_config["settings"]["stream_agent_text"]

    def _show_loading_indicator(self) -> None:
        if self._loading_indicator_shown:
            return
        self._loading_indicator_shown = True
        self.loading_indicator.add_class("active")

    def _hide_loading_indicator(self) -> None:
        if not self._loading_indicator_shown:
            return
        self._loading_indicator_shown = False
        self.loading_indicator.remove_class("active")

    def _queue_request_after_refresh(
        self,
        message: str,
        submission_trace: SubmissionTrace | None = None,
    ) -> None:
        def _enqueue() -> None:
            self.request_queue.put_nowait(message)
            self._request_debug.request_enqueued_after_refresh(submission_trace)

        self.call_after_refresh(_enqueue)

    def _start_delta_flush_timer(self) -> None:
        self._delta_flush_timer = self.set_interval(
            self.STREAM_THROTTLE_MS / self.MILLISECONDS_PER_SECOND,
            self._flush_request_deltas,
        )
        self._request_debug.note_delta_timer_started()

    def _stop_delta_flush_timer(self) -> None:
        timer = self._delta_flush_timer
        if timer is None:
            return
        timer.stop()
        self._delta_flush_timer = None
        self._request_debug.note_delta_timer_stopped()

    async def _flush_request_deltas(self) -> None:
        bridge = self._request_bridge
        if bridge is None:
            return

        self._request_debug.note_delta_timer_tick()
        flush_started_at = time.monotonic()
        stream_batch = bridge.drain_streaming()
        thinking_batch = bridge.drain_thinking()

        stream_callback_ms = 0.0
        if stream_batch.has_data:
            stream_started_at = time.monotonic()
            await self.streaming.callback(stream_batch.text)
            stream_callback_ms = (
                time.monotonic() - stream_started_at
            ) * self.MILLISECONDS_PER_SECOND

        thinking_callback_ms = 0.0
        if thinking_batch.has_data:
            thinking_started_at = time.monotonic()
            await self._thinking_callback(thinking_batch.text)
            thinking_callback_ms = (
                time.monotonic() - thinking_started_at
            ) * self.MILLISECONDS_PER_SECOND

        flush_duration_ms = (time.monotonic() - flush_started_at) * self.MILLISECONDS_PER_SECOND
        self._request_debug.note_delta_flush(
            stream_batch=stream_batch,
            thinking_batch=thinking_batch,
            flush_duration_ms=flush_duration_ms,
            stream_callback_ms=stream_callback_ms,
            thinking_callback_ms=thinking_callback_ms,
        )

    async def _process_request(
        self,
        message: str,
        submission_trace: SubmissionTrace | None = None,
    ) -> None:
        session = self.state_manager.session
        self._request_start_time = time.monotonic()
        self.query_one("#viewport").remove_class(RICHLOG_CLASS_STREAMING)
        self.chat_container.clear_insertion_anchor()
        self._update_compaction_status(False)
        self._request_debug.request_started(submission_trace)
        if not self._loading_indicator_shown:
            self._request_debug.loading_shown(reason="request_start")
        self._show_loading_indicator()
        self._clear_thinking_state()
        bridge = RequestUiBridge(self)
        self._request_bridge = bridge
        self._start_delta_flush_timer()
        try:
            model_name = session.current_model or "openai/gpt-4o"
            should_stream_agent_text = self._should_stream_agent_text()
            from textual.worker import Worker, WorkerCancelled, WorkerFailed

            from tunacode.core.agents.main import process_request
            from tunacode.core.ui_api.shared_types import ModelName

            worker: Worker[object] = self.run_worker(
                process_request(
                    message=message,
                    model=ModelName(model_name),
                    state_manager=self.state_manager,
                    streaming_callback=(
                        bridge.streaming_callback if should_stream_agent_text else None
                    ),
                    thinking_callback=bridge.thinking_callback,
                    tool_result_callback=build_tool_result_callback(self),
                    tool_start_callback=None,
                    notice_callback=bridge.notice_callback,
                    compaction_status_callback=bridge.compaction_status_callback,
                ),
                exit_on_error=False,
                name="process_request",
                thread=True,
            )
            self._current_request_task = worker
            worker_started_at = time.monotonic()
            try:
                await worker.wait()
            finally:
                worker_duration_ms = (
                    time.monotonic() - worker_started_at
                ) * self.MILLISECONDS_PER_SECOND
                self._request_debug.note_request_worker_completed(duration_ms=worker_duration_ms)
        except WorkerCancelled:
            self.notify("Cancelled")
        except WorkerFailed as e:
            from tunacode.ui.renderers.errors import render_exception

            error = e.error
            if not isinstance(error, Exception):
                error = RuntimeError(f"Worker failed with non-exception error: {error!r}")
            content, meta = render_exception(error)
            self.chat_container.write(content, panel_meta=meta)
        except Exception as e:
            from tunacode.ui.renderers.errors import render_exception

            content, meta = render_exception(e)
            self.chat_container.write(content, panel_meta=meta)
        finally:
            post_stream_started_at = time.monotonic()

            final_flush_started_at = time.monotonic()
            try:
                await self._flush_request_deltas()
            finally:
                final_flush_ms = (
                    time.monotonic() - final_flush_started_at
                ) * self.MILLISECONDS_PER_SECOND
                self._stop_delta_flush_timer()
                self._request_bridge = None
                self._current_request_task = None
            if self._loading_indicator_shown:
                self._request_debug.loading_hidden(reason="request_complete")
            self._hide_loading_indicator()
            self.query_one("#viewport").remove_class(RICHLOG_CLASS_STREAMING)
            self.streaming.reset()
            self._finalize_thinking_state_after_request()
            self._update_compaction_status(False)
            response_panel_ms = 0.0
            response_char_count = 0
            response_panel_started_at = time.monotonic()
            output_text = self._get_latest_response_text()
            if output_text is not None:
                from tunacode.ui.renderers.agent_response import render_agent_response

                duration_ms = (
                    time.monotonic() - self._request_start_time
                ) * self.MILLISECONDS_PER_SECOND
                session = self.state_manager.session
                tokens = session.usage.last_call_usage.output
                content, meta = render_agent_response(
                    content=output_text,
                    tokens=tokens,
                    duration_ms=duration_ms,
                )
                self.chat_container.write("")
                response_widget = self.chat_container.write(content, expand=True, panel_meta=meta)
                self.chat_container.set_insertion_anchor(response_widget)
                response_char_count = len(output_text)
            response_panel_ms = (
                time.monotonic() - response_panel_started_at
            ) * self.MILLISECONDS_PER_SECOND
            resource_bar_started_at = time.monotonic()
            self._update_resource_bar()
            resource_bar_update_ms = (
                time.monotonic() - resource_bar_started_at
            ) * self.MILLISECONDS_PER_SECOND
            # Auto-save session after processing
            save_session_started_at = time.monotonic()
            await self.state_manager.save_session()
            save_session_ms = (
                time.monotonic() - save_session_started_at
            ) * self.MILLISECONDS_PER_SECOND
            post_stream_cleanup_ms = (
                time.monotonic() - post_stream_started_at
            ) * self.MILLISECONDS_PER_SECOND
            self._request_debug.note_post_stream_cleanup(
                final_flush_ms=final_flush_ms,
                response_panel_ms=response_panel_ms,
                response_chars=response_char_count,
                resource_bar_update_ms=resource_bar_update_ms,
                save_session_ms=save_session_ms,
                message_count=len(session.conversation.messages),
                total_cleanup_ms=post_stream_cleanup_ms,
            )
            total_request_ms = (
                time.monotonic() - self._request_start_time
            ) * self.MILLISECONDS_PER_SECOND
            self._request_debug.request_finished(total_request_ms=total_request_ms)

    def _get_latest_response_text(self) -> str | None:
        from tinyagent.agent_types import AssistantMessage, TextContent

        messages = self.state_manager.session.conversation.messages
        for message in reversed(messages):
            if not isinstance(message, AssistantMessage):
                continue

            text_segments: list[str] = []
            for item in message.content:
                if not isinstance(item, TextContent):
                    continue

                text_value = item.text
                if not isinstance(text_value, str) or not text_value:
                    continue

                text_segments.append(text_value)

            normalized_content = " ".join(text_segments).strip()
            if not normalized_content:
                return None
            return normalized_content
        return None

    async def on_editor_submit_requested(self, message: EditorSubmitRequested) -> None:
        from tunacode.ui.commands import handle_command

        if await handle_command(self, message.text):
            return
        normalized_message = normalize_agent_message_text(message.text)
        submission_trace = self._request_debug.submit_received(
            raw_text=message.text,
            normalized_text=normalized_message,
        )
        if not self._loading_indicator_shown:
            self._request_debug.loading_shown(reason="submit")
        self._show_loading_indicator()
        from datetime import datetime

        timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")
        self.chat_container.write("")
        render_width = max(1, self.chat_container.size.width - 2)
        user_block = format_user_message(message.text, STYLE_PRIMARY, width=render_width)
        user_block.append(f"│ you {timestamp}", style=f"dim {STYLE_PRIMARY}")
        self.chat_container.write(user_block).add_class("user-message")
        self._queue_request_after_refresh(normalized_message, submission_trace)

    def on_tui_log_display(self, message: TuiLogDisplay) -> None:
        self.chat_container.write(message.renderable)

    def on_system_notice_display(self, message: SystemNoticeDisplay) -> None:
        self._show_system_notice(message.notice)

    def on_compaction_status_changed(self, message: CompactionStatusChanged) -> None:
        self._update_compaction_status(message.active)

    def on_tool_result_display(self, message: ToolResultDisplay) -> None:
        from tunacode.ui.renderers.panels import tool_panel_smart

        max_line_width = self.tool_panel_max_width()
        content, panel_meta = tool_panel_smart(
            name=message.tool_name,
            status=message.status,
            args=message.args,
            result=message.result,
            result_text=message.result_text,
            duration_ms=message.duration_ms,
            max_line_width=max_line_width,
        )
        self.chat_container.write(content, panel_meta=panel_meta)
        if message.status != "completed":
            return
        if message.tool_name not in FILE_EDIT_TOOLS:
            return
        filepath_value = message.args.get("filepath")
        if not isinstance(filepath_value, str):
            return
        filepath = filepath_value.strip()
        if not filepath:
            return
        self.update_lsp_for_file(filepath)
        self._edited_files.add(filepath)
        self._refresh_context_panel()

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
        self.chat_container.write(notice_text)

    def _replay_session_messages(self) -> None:
        """Render loaded session messages to ChatContainer."""
        from rich.markdown import Markdown
        from tinyagent.agent_types import AssistantMessage, UserMessage

        from tunacode.core.ui_api.messaging import get_content

        conversation = self.state_manager.session.conversation
        for message in conversation.messages:
            if isinstance(message, UserMessage):
                content = get_content(message)
                if not content:
                    continue

                user_block = Text()
                user_block.append(f"| {content}\n", style=STYLE_PRIMARY)
                user_block.append("| (restored)", style=f"dim {STYLE_PRIMARY}")
                self.chat_container.write(user_block)
                continue

            if not isinstance(message, AssistantMessage):
                continue

            content = get_content(message)
            if not content:
                continue

            self.chat_container.write(Text("agent:", style="accent"))
            self.chat_container.write(Markdown(content))

    def _context_panel_supported_for_width(self, width: int) -> bool:
        return width >= self.CONTEXT_PANEL_MIN_TERMINAL_WIDTH

    def _set_context_panel_visibility(self, *, visible: bool) -> None:
        context_rail = self.query_one("#context-rail", Container)
        self._context_panel_visible = visible
        if visible:
            context_rail.remove_class(self.CONTEXT_PANEL_COLLAPSED_CLASS)
            self.resource_bar.add_class(self.CONTEXT_PANEL_COLLAPSED_CLASS)
            self._refresh_context_panel()
            return
        context_rail.add_class(self.CONTEXT_PANEL_COLLAPSED_CLASS)
        self.resource_bar.remove_class(self.CONTEXT_PANEL_COLLAPSED_CLASS)

    def action_toggle_context_panel(self) -> None:
        should_show = not self._context_panel_visible
        if should_show and not self._context_panel_supported_for_width(self.size.width):
            self.notify(
                f"Context panel requires at least {self.CONTEXT_PANEL_MIN_TERMINAL_WIDTH} columns"
            )
            return

        self._set_context_panel_visibility(visible=should_show)

    def action_copy_selection(self) -> None:
        copy_selection_to_clipboard(self, show_toast=False)

    def on_resize(self, event: events.Resize) -> None:
        if not self._context_panel_visible:
            return

        if self._context_panel_supported_for_width(event.size.width):
            return

        self._set_context_panel_visibility(visible=False)
        self.notify(f"Context panel hidden below {self.CONTEXT_PANEL_MIN_TERMINAL_WIDTH} columns")

    def action_cancel_request(self) -> None:
        """Cancel the current request or shell command."""
        esc_handler = self._esc_handler
        current_request_task = self._current_request_task
        esc_handler.handle_escape(
            current_request_task=current_request_task,
            shell_runner=getattr(self, "_shell_runner", None),
        )

    def start_shell_command(self, raw_cmd: str) -> None:
        self.shell_runner.start(raw_cmd)

    def write_shell_output(self, renderable: RenderableType) -> None:
        self.chat_container.write(renderable)

    def reset_context_panel_state(self) -> None:
        self._edited_files.clear()
        self._refresh_context_panel()

    def _refresh_context_panel(self) -> None:
        field_model = self._field_model
        field_context = self._field_context
        field_cost = self._field_cost
        field_files = self._field_files
        field_skills = self._field_skills
        if (
            field_model is None
            or field_context is None
            or field_cost is None
            or field_files is None
            or field_skills is None
        ):
            return
        from tunacode.ui.model_display import format_model_for_display

        session = self.state_manager.session
        conversation = session.conversation
        raw_model = session.current_model or ""
        model_display = format_model_for_display(raw_model, max_length=30) if raw_model else "---"
        estimated_tokens = self._estimate_conversation_tokens(conversation.messages)
        max_tokens = conversation.max_tokens or self.DEFAULT_CONTEXT_MAX_TOKENS
        remaining_pct = token_remaining_pct(estimated_tokens, max_tokens)
        current_token_style = token_color(remaining_pct)
        session_cost = session.usage.session_total_usage.cost.total
        cost_display = RESOURCE_BAR_COST_FORMAT.format(cost=session_cost)
        field_model.update(Text(model_display, style=f"bold {STYLE_PRIMARY}"))
        field_context.update(
            build_context_gauge(
                tokens=estimated_tokens,
                max_tokens=max_tokens,
                remaining_pct=remaining_pct,
                token_style=current_token_style,
            )
        )
        field_cost.update(Text(cost_display, style=f"bold {STYLE_SUCCESS}"))
        files_title, files_content = build_files_field(self._edited_files)
        field_files.border_title = files_title
        field_files.update(files_content)

        skill_entries = self._build_skill_entries()
        skills_title, skills_content = build_skills_field(skill_entries)
        field_skills.border_title = skills_title
        field_skills.update(skills_content)

        handler = self._slopgotchi_handler
        if handler is not None:
            handler._refresh()

    def _estimate_conversation_tokens(self, messages: list[AgentMessage]) -> int:
        if not messages:
            return 0

        from tunacode.core.ui_api.messaging import estimate_messages_tokens

        conversation = self.state_manager.session.conversation
        if messages is conversation.messages:
            if conversation.total_tokens > 0:
                return conversation.total_tokens
            conversation.total_tokens = estimate_messages_tokens(messages)
            return conversation.total_tokens

        return estimate_messages_tokens(messages)

    def _build_skill_entries(self) -> list[tuple[str, str]]:
        from tunacode.skills.selection import resolve_selected_skill_summaries

        skill_entries: list[tuple[str, str]] = []
        resolved_summaries = resolve_selected_skill_summaries(
            self.state_manager.session.selected_skill_names
        )
        for resolved_summary in resolved_summaries:
            summary = resolved_summary.summary
            if summary is None:
                skill_entries.append((resolved_summary.requested_name, "missing"))
                continue
            skill_entries.append((summary.name, summary.source.value))
        return skill_entries

    def on_click(self, event: events.Click) -> None:
        if not is_widget_within_field(event.widget, self, field_id="field-pet"):
            return
        self._touch_slopgotchi()

    def _touch_slopgotchi(self) -> None:
        handler = self._slopgotchi_handler
        if handler is not None:
            handler.touch()

    def _update_slopgotchi(self) -> None:
        handler = self._slopgotchi_handler
        if handler is not None:
            handler.update()

    def _update_compaction_status(self, active: bool) -> None:
        self.resource_bar.update_compaction_status(active)

    def _update_resource_bar(self) -> None:
        from tunacode.core.debug import log_resource_bar_update
        from tunacode.core.logging import get_logger

        session = self.state_manager.session
        conversation = session.conversation
        # Use simplified token counter to estimate actual context window usage
        estimated_tokens = self._estimate_conversation_tokens(conversation.messages)
        model = session.current_model or "No model selected"
        max_tokens = conversation.max_tokens or self.DEFAULT_CONTEXT_MAX_TOKENS
        session_cost = session.usage.session_total_usage.cost.total
        self.resource_bar.update_stats(
            model=model,
            tokens=estimated_tokens,
            max_tokens=max_tokens,
            session_cost=session_cost,
        )
        logger = get_logger()
        log_resource_bar_update(
            logger=logger,
            model=model,
            estimated_tokens=estimated_tokens,
            max_tokens=max_tokens,
            session_cost=session_cost,
        )
        if self._context_panel_visible:
            self._refresh_context_panel()

    def _hide_thinking_output(self) -> None:
        from tunacode.ui.thinking_state import hide_thinking_output

        hide_thinking_output(self)

    def _clear_thinking_state(self) -> None:
        from tunacode.ui.thinking_state import clear_thinking_state

        clear_thinking_state(self)

    def _finalize_thinking_state_after_request(self) -> None:
        from tunacode.ui.thinking_state import finalize_thinking_state_after_request

        finalize_thinking_state_after_request(self)

    def _refresh_thinking_output(self, force: bool = False) -> None:
        from tunacode.ui.thinking_state import refresh_thinking_output

        refresh_thinking_output(self, force)

    async def _thinking_callback(self, delta: str) -> None:
        from tunacode.ui.thinking_state import thinking_callback

        await thinking_callback(self, delta)

    def update_lsp_for_file(self, filepath: str) -> None:
        """Update ResourceBar LSP status based on file type."""
        from tunacode.core.ui_api.lsp_status import get_lsp_server_info

        info = get_lsp_server_info(filepath)
        self.resource_bar.update_lsp_status(info.server_name, info.available)
