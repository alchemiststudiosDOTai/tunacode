from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch

from rich.text import Text

from tunacode.core.session import StateManager

from tunacode.ui.app import TextualReplApp
from tunacode.ui.esc.handler import EscHandler
from tunacode.ui.lifecycle import AppLifecycle
from tunacode.ui.repl_support import build_tool_result_callback
from tunacode.ui.request_bridge import RequestUiBridge
from tunacode.ui.widgets.messages import ToolResultDisplay, TuiLogDisplay


class _FakeChatContainer:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.insertion_anchor_cleared = False
        self.insertion_anchor: object | None = None

    def clear_insertion_anchor(self) -> None:
        self.insertion_anchor_cleared = True

    def set_insertion_anchor(self, widget: object) -> None:
        self.insertion_anchor = widget

    def write(self, content: object, **_kwargs: object) -> None:
        self.calls.append(content)


class _FakeLogger:
    def __init__(self) -> None:
        self.state_manager: StateManager | None = None
        self.tui_callback: object | None = None

    def set_state_manager(self, state_manager: StateManager) -> None:
        self.state_manager = state_manager

    def set_tui_callback(self, callback: object) -> None:
        self.tui_callback = callback


class _FakeBridgeApp:
    def __init__(self) -> None:
        self.messages: list[object] = []

    def post_message(self, message: object) -> bool:
        self.messages.append(message)
        return True


class _FakeThinkingState:
    def __init__(self) -> None:
        self.chunks: list[str] = []
        self.cleared = False
        self.finalized = False

    async def callback(self, chunk: str) -> None:
        self.chunks.append(chunk)

    def clear(self) -> None:
        self.cleared = True

    def finalize(self) -> None:
        self.finalized = True


class _FakeToolCallbackApp:
    def __init__(self) -> None:
        self.messages: list[object] = []

    def post_message(self, message: object) -> bool:
        self.messages.append(message)
        return True


class _FakeStreamingHandler:
    def __init__(self) -> None:
        self.chunks: list[str] = []
        self.reset_called = False

    async def callback(self, chunk: str) -> None:
        self.chunks.append(chunk)

    def reset(self) -> None:
        self.reset_called = True


class _FakeWorkerHandle:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class _FakeViewport:
    def __init__(self) -> None:
        self.removed_classes: list[str] = []

    def remove_class(self, class_name: str) -> None:
        self.removed_classes.append(class_name)


class _FakeTimer:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _FakeWorker:
    def __init__(self, app: TextualReplApp, work: object) -> None:
        self._app = app
        self._work = work
        self.cancelled = False
        self.wait_called = False

    def cancel(self) -> None:
        self.cancelled = True

    async def wait(self) -> object:
        self.wait_called = True
        assert self._app._current_request_task is self
        if inspect.isawaitable(self._work):
            return await self._work
        if callable(self._work):
            result = self._work()
            if inspect.isawaitable(result):
                return await result
            return result
        return self._work


def test_tui_log_display_is_written_via_message_handler() -> None:
    app = TextualReplApp(state_manager=StateManager())
    app.chat_container = _FakeChatContainer()  # type: ignore[assignment]

    renderable = Text("thread-safe log")
    app.on_tui_log_display(TuiLogDisplay(renderable=renderable))

    assert app.chat_container.calls == [renderable]


def test_logger_tui_callback_posts_message_not_widget_write() -> None:
    app = TextualReplApp(state_manager=StateManager())
    app.chat_container = _FakeChatContainer()  # type: ignore[assignment]
    posted_messages: list[object] = []
    app.post_message = posted_messages.append  # type: ignore[method-assign]
    fake_logger = _FakeLogger()

    with patch("tunacode.core.logging.get_logger", return_value=fake_logger):
        AppLifecycle(app)._setup_logger()

    assert fake_logger.state_manager is app.state_manager
    assert callable(fake_logger.tui_callback)

    renderable = Text("queued log")
    fake_logger.tui_callback(renderable)

    assert app.chat_container.calls == []
    assert len(posted_messages) == 1
    message = posted_messages[0]
    assert isinstance(message, TuiLogDisplay)
    assert message.renderable == renderable


async def test_request_ui_bridge_drains_all_chunks_in_order() -> None:
    bridge = RequestUiBridge(_FakeBridgeApp())

    await bridge.streaming_callback("hello")
    await bridge.streaming_callback(" ")
    await bridge.streaming_callback("world")
    await bridge.thinking_callback("thinking")
    await bridge.thinking_callback("...")

    streaming_batch = bridge.drain_streaming()
    assert streaming_batch.text == "hello world"
    assert streaming_batch.chunk_count == 3
    assert bridge.drain_streaming().has_data is False

    thinking_batch = bridge.drain_thinking()
    assert thinking_batch.text == "thinking..."
    assert thinking_batch.chunk_count == 2
    assert bridge.drain_thinking().has_data is False


async def test_flush_timer_applies_queued_deltas_to_streaming_handler() -> None:
    app = TextualReplApp(state_manager=StateManager())
    app._request_bridge = RequestUiBridge(_FakeBridgeApp())
    app.streaming = _FakeStreamingHandler()  # type: ignore[assignment]
    thinking_state = _FakeThinkingState()
    app._thinking_state = thinking_state  # type: ignore[assignment]

    await app._request_bridge.streaming_callback("hello")
    await app._request_bridge.streaming_callback(" world")
    await app._request_bridge.thinking_callback("trace")
    await app._request_bridge.thinking_callback(" data")
    await app._flush_request_deltas()

    assert app.streaming.chunks == ["hello world"]
    assert thinking_state.chunks == ["trace data"]


def test_escape_handler_cancels_worker_handle() -> None:
    worker = _FakeWorkerHandle()

    EscHandler().handle_escape(current_request_task=worker, shell_runner=None)

    assert worker.cancelled is True


async def test_process_request_runs_in_worker_and_sets_current_request_handle() -> None:
    app = TextualReplApp(state_manager=StateManager())
    app.chat_container = _FakeChatContainer()  # type: ignore[assignment]
    app.streaming = _FakeStreamingHandler()  # type: ignore[assignment]
    viewport = _FakeViewport()
    timer = _FakeTimer()
    compaction_updates: list[bool] = []
    notifications: list[str] = []
    worker_calls: list[dict[str, object]] = []
    process_request_calls: list[dict[str, object]] = []
    tool_result_callback = object()

    async def _fake_process_request(**kwargs: object) -> None:
        process_request_calls.append(kwargs)

    def _fake_run_worker(work: object, **kwargs: object) -> _FakeWorker:
        worker_calls.append({"work": work, **kwargs})
        return _FakeWorker(app, work)

    app.run_worker = _fake_run_worker  # type: ignore[method-assign]
    app.query_one = lambda *_args, **_kwargs: viewport  # type: ignore[method-assign]
    app.set_interval = lambda *_args, **_kwargs: timer  # type: ignore[method-assign]
    app._show_loading_indicator = lambda: None  # type: ignore[method-assign]
    app._hide_loading_indicator = lambda: None  # type: ignore[method-assign]
    app._thinking_state = _FakeThinkingState()  # type: ignore[assignment]
    app._update_resource_bar = lambda: None  # type: ignore[method-assign]
    app._get_latest_response_text = lambda: None  # type: ignore[method-assign]
    app._update_compaction_status = compaction_updates.append  # type: ignore[method-assign]
    app.notify = notifications.append  # type: ignore[method-assign]
    app.state_manager.save_session = AsyncMock()  # type: ignore[method-assign]

    with (
        patch("tunacode.core.agents.main.process_request", new=_fake_process_request),
        patch("tunacode.ui.app.build_tool_result_callback", return_value=tool_result_callback),
    ):
        await app._process_request("hello")

    assert len(worker_calls) == 1
    worker_call = worker_calls[0]
    assert worker_call["exit_on_error"] is False
    assert worker_call["name"] == "process_request"
    assert worker_call["thread"] is True
    assert len(process_request_calls) == 1
    process_request_call = process_request_calls[0]
    assert process_request_call["message"] == "hello"
    assert process_request_call["tool_result_callback"] is tool_result_callback
    assert process_request_call["thinking_callback"] is not None
    assert process_request_call["notice_callback"] is not None
    assert process_request_call["compaction_status_callback"] is not None
    assert app._current_request_task is None
    assert app._request_bridge is None
    assert timer.stopped is True
    assert viewport.removed_classes
    assert notifications == []


def test_tool_result_callback_posts_tool_result_display_from_request_thread() -> None:
    app = _FakeToolCallbackApp()

    callback = build_tool_result_callback(app)
    callback(
        "write_file",
        "completed",
        {"filepath": "src/example.py"},
        result=None,
        duration_ms=12.0,
    )

    assert len(app.messages) == 1
    message = app.messages[0]
    assert isinstance(message, ToolResultDisplay)
    assert message.tool_name == "write_file"
    assert message.status == "completed"
    assert message.args == {"filepath": "src/example.py"}


def test_on_tool_result_display_tracks_edited_files_on_ui_thread() -> None:
    app = TextualReplApp(state_manager=StateManager())
    app.chat_container = _FakeChatContainer()  # type: ignore[assignment]
    refresh_calls: list[bool] = []
    app._refresh_context_panel = lambda: refresh_calls.append(True)  # type: ignore[method-assign]
    app.tool_panel_max_width = lambda: 80  # type: ignore[method-assign]

    with patch(
        "tunacode.ui.renderers.panels.tool_panel_smart",
        return_value=("rendered", {"title": "tool"}),
    ):
        app.on_tool_result_display(
            ToolResultDisplay(
                tool_name="write_file",
                status="completed",
                args={"filepath": "src/example.py"},
                result=None,
                result_text="ok",
                duration_ms=4.0,
            )
        )

    assert app.chat_container.calls == ["rendered"]
    assert "src/example.py" in app._edited_files
    assert refresh_calls == [True]
