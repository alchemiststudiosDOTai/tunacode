"""Textual-based REPL shell - Application entry point."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Never

from rich.console import RenderableType
from rich.markdown import Markdown
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import LoadingIndicator, Static

if TYPE_CHECKING:
    from textual.theme import Theme

from tunacode.core.agents.main import process_request
from tunacode.core.debug import log_resource_bar_update
from tunacode.core.logging import get_logger
from tunacode.core.session import StateManager
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
from tunacode.core.ui_api.messaging import estimate_messages_tokens
from tunacode.core.ui_api.shared_types import ModelName

from tunacode.ui.esc.handler import EscHandler
from tunacode.ui.model_display import format_model_for_display
from tunacode.ui.renderers.errors import render_exception
from tunacode.ui.renderers.panels import tool_panel_smart
from tunacode.ui.repl_support import (
    FILE_EDIT_TOOLS,
    StatusBarLike,
    build_textual_tool_callback,
    build_tool_result_callback,
    build_tool_start_callback,
    format_user_message,
)
from tunacode.ui.shell_runner import ShellRunner
from tunacode.ui.styles import (
    STYLE_ACCENT,
    STYLE_ERROR,
    STYLE_MUTED,
    STYLE_PRIMARY,
    STYLE_SUCCESS,
    STYLE_WARNING,
)
from tunacode.ui.tamagochi import (
    SLOPBAR_HEALTH_NAME,
    TAMAGOCHI_ART_STATES,
    TAMAGOCHI_NAME,
    TamagochiPanelState,
    render_slopbar_health,
    render_tamagochi,
    touch_tamagochi,
)
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
    ]

    BINDINGS = [
        Binding("escape", "cancel_request", "Cancel", show=False, priority=True),
        Binding("ctrl+e", "toggle_context_panel", "Context", show=False, priority=True),
    ]

    STREAM_THROTTLE_MS: float = 100.0
    CONTEXT_PANEL_COLLAPSED_CLASS = "hidden"
    DEFAULT_CONTEXT_MAX_TOKENS: int = 200000

    def __init__(self, *, state_manager: StateManager, show_setup: bool = False) -> None:
        super().__init__()

        self.register_theme(build_tunacode_theme())
        self.register_theme(build_nextstep_theme())
        for theme in wrap_builtin_themes(self.available_themes):
            self.register_theme(theme)
        self.theme = THEME_NAME

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
        self._context_panel_visible: bool = False
        self._edited_files: set[str] = set()
        self._field_model: Static | None = None
        self._field_context: Static | None = None
        self._field_cost: Static | None = None
        self._field_files: Static | None = None
        self._tamagochi_state: TamagochiPanelState = TamagochiPanelState()

        self._field_tamagochi: Static | None = None
        self._field_slopbar_health: Static | None = None

        self._current_stream_text: str = ""
        self._last_stream_update: float = 0.0

    def compose(self) -> ComposeResult:
        self.resource_bar = ResourceBar()
        self.chat_container = ChatContainer(id="chat-container", auto_scroll=True)
        self.streaming_output = Static("", id="streaming-output")
        self.loading_indicator = LoadingIndicator()
        self.editor = Editor()
        self.status_bar = StatusBar()
        yield self.resource_bar
        with Container(id="workspace"):
            with Container(id="viewport"):
                yield self.chat_container
                yield self.loading_indicator
            with (
                Container(id="context-rail", classes=self.CONTEXT_PANEL_COLLAPSED_CLASS),
                Container(id="context-panel"),
            ):
                yield Static("Session Inspector", id="inspector-title")
                self._field_tamagochi = Static(
                    f"{TAMAGOCHI_ART_STATES[0]}",
                    id="field-pet",
                    classes="inspector-field",
                )
                self._field_tamagochi.border_title = TAMAGOCHI_NAME
                yield self._field_tamagochi

                self._field_slopbar_health = Static(
                    "",
                    id="field-slopbar-health",
                    classes="inspector-field",
                )
                self._field_slopbar_health.border_title = SLOPBAR_HEALTH_NAME
                yield self._field_slopbar_health

                self._field_model = Static("---", id="field-model", classes="inspector-field")
                self._field_model.border_title = "Model"
                yield self._field_model
                self._field_context = Static("", id="field-context", classes="inspector-field")
                self._field_context.border_title = "Context"
                yield self._field_context
                self._field_cost = Static("", id="field-cost", classes="inspector-field")
                self._field_cost.border_title = "Cost"
                yield self._field_cost
                self._field_files = Static("", id="field-files", classes="inspector-field")
                self._field_files.border_title = "Files"
                yield self._field_files
        yield self.streaming_output
        yield self.editor
        yield FileAutoComplete(self.editor)
        yield CommandAutoComplete(self.editor)
        yield self.status_bar

    @property
    def rich_log(self) -> ChatContainer:
        """Backward compatibility alias for chat_container."""
        return self.chat_container

    @property
    def supported_themes(self) -> dict[str, Theme]:
        return {
            theme_name: self.available_themes[theme_name]
            for theme_name in SUPPORTED_THEME_NAMES
            if theme_name in self.available_themes
        }

    def on_mount(self) -> None:
        user_config = self.state_manager.session.user_config
        saved_theme = user_config.get("settings", {}).get("theme", THEME_NAME)
        if saved_theme not in SUPPORTED_THEME_NAMES:
            saved_theme = THEME_NAME
        self.theme = saved_theme

        # Initialize session persistence metadata
        from tunacode.core.ui_api.system_paths import get_project_id

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
                content, meta = render_exception(e)
                self.rich_log.write(content, panel_meta=meta)
            finally:
                self.request_queue.task_done()

    async def _process_request(self, message: str) -> None:
        session = self.state_manager.session

        self._request_start_time = time.monotonic()
        self.query_one("#viewport").remove_class(RICHLOG_CLASS_STREAMING)
        self.chat_container.clear_insertion_anchor()
        self._update_compaction_status(False)

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
                    streaming_callback=self._streaming_callback,
                    tool_result_callback=build_tool_result_callback(self),
                    tool_start_callback=build_tool_start_callback(self),
                    notice_callback=self._show_system_notice,
                    compaction_status_callback=self._update_compaction_status,
                )
            )
            await self._current_request_task
        except asyncio.CancelledError:
            self.notify("Cancelled")
        except Exception as e:
            content, meta = render_exception(e)
            self.rich_log.write(content, panel_meta=meta)
        finally:
            self._current_request_task = None
            self._loading_indicator_shown = False
            self.loading_indicator.remove_class("active")
            self.query_one("#viewport").remove_class(RICHLOG_CLASS_STREAMING)
            self.streaming_output.update("")
            self.streaming_output.remove_class("active")
            self._current_stream_text = ""
            self._last_stream_update = 0.0
            self._update_compaction_status(False)

            output_text = self._get_latest_response_text()

            if output_text is not None:
                from tunacode.ui.renderers.agent_response import render_agent_response

                duration_ms = (time.monotonic() - self._request_start_time) * 1000
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

            self._update_resource_bar()

            # Auto-save session after processing
            await self.state_manager.save_session()

    def _get_latest_response_text(self) -> str | None:
        from tunacode.core.ui_api.messaging import get_content

        messages = self.state_manager.session.conversation.messages
        for message in reversed(messages):
            if not isinstance(message, dict):
                continue

            if message.get("role") != "assistant":
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
        content, panel_meta = tool_panel_smart(
            name=message.tool_name,
            status=message.status,
            args=message.args,
            result=message.result,
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
        self.rich_log.write(notice_text)

    def _replay_session_messages(self) -> None:
        """Render loaded session messages to ChatContainer."""
        from tunacode.core.ui_api.messaging import get_content

        conversation = self.state_manager.session.conversation
        for msg in conversation.messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role == "user":
                content = get_content(msg)
                if not content:
                    continue
                user_block = Text()
                user_block.append(f"| {content}\n", style=STYLE_PRIMARY)
                user_block.append("| (restored)", style=f"dim {STYLE_PRIMARY}")
                self.rich_log.write(user_block)
                continue
            if role != "assistant":
                continue

            content = get_content(msg)
            if not content:
                continue
            self.rich_log.write(Text("agent:", style="accent"))
            self.rich_log.write(Markdown(content))

    def action_toggle_context_panel(self) -> None:
        self._context_panel_visible = not self._context_panel_visible
        context_rail = self.query_one("#context-rail", Container)
        if self._context_panel_visible:
            context_rail.remove_class(self.CONTEXT_PANEL_COLLAPSED_CLASS)
            self._refresh_context_panel()
            return

        context_rail.add_class(self.CONTEXT_PANEL_COLLAPSED_CLASS)

    def action_cancel_request(self) -> None:
        """Cancel the current request or shell command."""
        esc_handler = self._esc_handler
        current_request_task = self._current_request_task
        shell_runner = getattr(self, "shell_runner", None)
        esc_handler.handle_escape(
            current_request_task=current_request_task,
            shell_runner=shell_runner,
        )

    def start_shell_command(self, raw_cmd: str) -> None:
        self.shell_runner.start(raw_cmd)

    def write_shell_output(self, renderable: RenderableType) -> None:
        self.rich_log.write(renderable)

    def shell_status_running(self) -> None:
        self.status_bar.update_running_action("shell")

    def shell_status_last(self) -> None:
        self.status_bar.update_last_action("shell")

    def reset_context_panel_state(self) -> None:
        self._edited_files.clear()
        self._refresh_context_panel()

    GAUGE_WIDTH: int = 24

    def _refresh_context_panel(self) -> None:
        if self._field_model is None:
            return

        session = self.state_manager.session
        conversation = session.conversation

        raw_model = session.current_model or ""
        model_display = format_model_for_display(raw_model, max_length=30) if raw_model else "---"
        estimated_tokens = estimate_messages_tokens(conversation.messages)
        max_tokens = conversation.max_tokens or self.DEFAULT_CONTEXT_MAX_TOKENS
        remaining_pct = self._token_remaining_pct(estimated_tokens, max_tokens)
        token_style = self._token_color(remaining_pct)
        session_cost = session.usage.session_total_usage.cost.total
        cost_display = RESOURCE_BAR_COST_FORMAT.format(cost=session_cost)

        self._field_model.update(Text(model_display, style=f"bold {STYLE_PRIMARY}"))

        self._refresh_context_gauge(
            estimated_tokens,
            max_tokens,
            remaining_pct,
            token_style,
        )

        self._field_cost.update(Text(cost_display, style=f"bold {STYLE_SUCCESS}"))
        self._refresh_tamagochi()
        self._refresh_slopbar_health()

        self._refresh_files_field()

    def _refresh_context_gauge(
        self,
        tokens: int,
        max_tokens: int,
        remaining_pct: float,
        token_style: str,
    ) -> None:
        used_pct = 100.0 - remaining_pct
        filled = round(self.GAUGE_WIDTH * used_pct / 100)
        empty = self.GAUGE_WIDTH - filled

        gauge = Text()
        gauge.append("\u2588" * filled, style=token_style)
        gauge.append("\u2591" * empty, style=STYLE_MUTED)
        gauge.append(f" {remaining_pct:.0f}%\n", style=f"bold {token_style}")
        gauge.append(f"{tokens:,}", style=token_style)
        gauge.append(f" / {max_tokens:,}", style=STYLE_MUTED)

        self._field_context.update(gauge)

    def _refresh_files_field(self) -> None:
        edited_files = sorted(self._edited_files)
        file_count = len(edited_files)
        self._field_files.border_title = f"Files [{file_count}]"

        if not edited_files:
            self._field_files.update(Text("(none)", style=f"dim {STYLE_MUTED}"))
            return

        content = Text()
        for i, filepath in enumerate(edited_files):
            content.append("\u25b8 ", style=STYLE_ACCENT)
            content.append(filepath, style=STYLE_PRIMARY)
            if i < file_count - 1:
                content.append("\n")
        self._field_files.update(content)

    def on_click(self, event: events.Click) -> None:
        widget = event.widget
        # Walk up from the clicked widget to see if it's inside the pet field
        while widget is not None and widget is not self:
            if getattr(widget, "id", None) == "field-pet":
                self._touch_tamagochi()
                return
            widget = widget.parent

    def _touch_tamagochi(self) -> None:
        if self._field_tamagochi is None:
            return

        touch_tamagochi(self._tamagochi_state)
        self._refresh_tamagochi()

    def _refresh_tamagochi(self) -> None:
        if self._field_tamagochi is None:
            return

        art = render_tamagochi(self._tamagochi_state)
        self._field_tamagochi.styles.margin = (0, 0, 0, self._tamagochi_state.offset)
        self._field_tamagochi.update(art)

    def _refresh_slopbar_health(self) -> None:
        if self._field_slopbar_health is None:
            return

        self._field_slopbar_health.update(render_slopbar_health(self._tamagochi_state))

    @staticmethod
    def _token_remaining_pct(tokens: int, max_tokens: int) -> float:
        if max_tokens == 0:
            return 0.0
        raw = (max_tokens - tokens) / max_tokens * 100
        return max(0.0, min(100.0, raw))

    @staticmethod
    def _token_color(remaining_pct: float) -> str:
        if remaining_pct > 60:
            return STYLE_SUCCESS
        if remaining_pct > 30:
            return STYLE_WARNING
        return STYLE_ERROR

    def _update_compaction_status(self, active: bool) -> None:
        self.resource_bar.update_compaction_status(active)

    def _update_resource_bar(self) -> None:
        session = self.state_manager.session
        conversation = session.conversation
        # Use simplified token counter to estimate actual context window usage
        estimated_tokens = estimate_messages_tokens(conversation.messages)

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
        self._refresh_context_panel()

    async def _streaming_callback(self, chunk: str) -> None:
        """Handle streaming text chunks from the agent.
        Accumulates chunks and updates the streaming output panel
        with throttled UI updates to reduce visual churn.
        """
        self._current_stream_text += chunk
        is_first_chunk = not self.streaming_output.has_class("active")
        if is_first_chunk:
            self.streaming_output.add_class("active")
        now = time.monotonic()
        elapsed_ms = (now - self._last_stream_update) * 1000
        if elapsed_ms >= self.STREAM_THROTTLE_MS or is_first_chunk:
            self._last_stream_update = now
            self.streaming_output.update(self._current_stream_text)

    def update_lsp_for_file(self, filepath: str) -> None:
        """Update ResourceBar LSP status based on file type.

        Args:
            filepath: Path to the file being edited
        """
        from tunacode.core.ui_api.lsp_status import get_lsp_server_info

        info = get_lsp_server_info(filepath)
        self.resource_bar.update_lsp_status(info.server_name, info.available)
