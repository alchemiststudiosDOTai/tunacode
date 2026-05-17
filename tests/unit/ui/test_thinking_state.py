from __future__ import annotations

import time
from types import SimpleNamespace

from tunacode.ui.thinking_state import ThinkingState


class _FakeThinkingWidget:
    def __init__(self) -> None:
        self.updates: list[object] = []
        self.classes: set[str] = set()
        self.border_title = ""
        self.border_subtitle = ""

    def update(self, content: object) -> None:
        self.updates.append(content)

    def add_class(self, class_name: str) -> None:
        self.classes.add(class_name)

    def remove_class(self, class_name: str) -> None:
        self.classes.discard(class_name)


class _FakeChatContainer:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict[str, object]]] = []

    def write(self, content: object, **kwargs: object) -> None:
        self.calls.append((content, dict(kwargs)))


class _FakeApp:
    MILLISECONDS_PER_SECOND = 1000.0
    THINKING_THROTTLE_MS = 100.0
    THINKING_THROTTLE_WHILE_DRAFTING_MS = 300.0
    THINKING_DEFER_AFTER_KEYPRESS_MS = 150.0
    THINKING_MAX_RENDER_LINES = 10
    THINKING_MAX_RENDER_CHARS = 1200
    THINKING_BUFFER_CHAR_LIMIT = 2400

    def __init__(self) -> None:
        self.state_manager = SimpleNamespace(session=SimpleNamespace(show_thoughts=True))
        self.editor = SimpleNamespace(value="draft")
        self._last_editor_keypress_at = 0.0
        self._thinking_panel_widget = _FakeThinkingWidget()
        self.chat_container = _FakeChatContainer()
        self._thinking_state = ThinkingState(self)
        self._thinking_state._text = "live thought"


def test_refresh_defers_incremental_update_while_user_is_actively_typing() -> None:
    app = _FakeApp()
    app._thinking_state._last_update = time.monotonic() - 1.0
    app._last_editor_keypress_at = time.monotonic()

    app._thinking_state.refresh()

    assert app._thinking_panel_widget.updates == []


def test_refresh_force_bypasses_recent_keypress_deferral() -> None:
    app = _FakeApp()
    app._thinking_state._last_update = time.monotonic() - 1.0
    app._last_editor_keypress_at = time.monotonic()

    app._thinking_state.refresh(force=True)

    assert len(app._thinking_panel_widget.updates) == 1
    assert "active" in app._thinking_panel_widget.classes


def test_finalize_moves_final_thoughts_into_chat_history() -> None:
    app = _FakeApp()

    app._thinking_state.finalize()

    assert len(app.chat_container.calls) == 1
    _content, kwargs = app.chat_container.calls[0]
    assert kwargs["expand"] is True
    assert app._thinking_state._text == ""
    assert "active" not in app._thinking_panel_widget.classes
