"""Tests for TUI shell command ergonomics (! prefix + Escape)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from unittest.mock import MagicMock

import pytest
from textual._context import NoActiveAppError

from tunacode.ui.app import TextualReplApp
from tunacode.ui.commands import handle_command
from tunacode.ui.esc.handler import EscHandler
from tunacode.ui.widgets.editor import Editor


@dataclass
class _FakeKeyEvent:
    key: str
    character: str | None
    prevented: bool = False

    def prevent_default(self) -> None:
        self.prevented = True


@dataclass
class _EditorKeyHandlingStub:
    value: str
    cursor_position: int = 0
    _app: object | None = None
    _has_paste_buffer: bool = False

    BASH_MODE_PREFIX = Editor.BASH_MODE_PREFIX
    BASH_MODE_PREFIX_WITH_SPACE = Editor.BASH_MODE_PREFIX_WITH_SPACE

    @property
    def app(self) -> object:
        if self._app is None:
            raise NoActiveAppError()
        return self._app

    @property
    def has_paste_buffer(self) -> bool:
        return self._has_paste_buffer


@pytest.mark.asyncio
async def test_handle_command_bang_starts_shell_command() -> None:
    started: list[str] = []

    class FakeApp:
        def start_shell_command(self, raw_cmd: str) -> None:
            started.append(raw_cmd)

    handled = await handle_command(cast(TextualReplApp, FakeApp()), "! ls")
    assert handled is True
    assert [cmd.strip() for cmd in started] == ["ls"]


@pytest.mark.asyncio
async def test_handle_command_plain_exit_still_works() -> None:
    class FakeApp:
        def __init__(self) -> None:
            self.exit_called = False

        def exit(self) -> None:
            self.exit_called = True

    app = cast(TextualReplApp, FakeApp())
    handled = await handle_command(app, "exit")

    assert handled is True
    assert app.exit_called is True


@pytest.mark.asyncio
async def test_handle_command_slash_exit_invokes_exit() -> None:
    class FakeApp:
        def __init__(self) -> None:
            self.exit_called = False

        def exit(self) -> None:
            self.exit_called = True

    app = cast(TextualReplApp, FakeApp())
    handled = await handle_command(app, "/exit")

    assert handled is True
    assert app.exit_called is True


@pytest.mark.asyncio
async def test_handle_command_slash_cancel_invokes_cancel() -> None:
    class FakeApp:
        def __init__(self) -> None:
            self.cancel_called = False

        def action_cancel_request(self) -> None:
            self.cancel_called = True

    app = cast(TextualReplApp, FakeApp())
    handled = await handle_command(app, "/cancel")

    assert handled is True
    assert app.cancel_called is True


def test_escape_does_not_clear_editor_when_no_request_or_shell_running() -> None:
    fake_app = type(
        "FakeApp",
        (),
        {
            "_current_request_task": None,
            "_esc_handler": EscHandler(),
            "_shell_runner": None,
        },
    )()
    TextualReplApp.action_cancel_request(fake_app)
    assert fake_app._current_request_task is None


def test_escape_passes_shell_runner_to_handler() -> None:
    shell_runner = object()
    esc_handler = MagicMock()
    fake_app = type(
        "FakeApp",
        (),
        {
            "_current_request_task": "worker",
            "_esc_handler": esc_handler,
            "_shell_runner": shell_runner,
        },
    )()

    TextualReplApp.action_cancel_request(fake_app)

    esc_handler.handle_escape.assert_called_once_with(
        current_request_task="worker",
        shell_runner=shell_runner,
    )


def test_bang_toggles_on_when_empty() -> None:
    editor = _EditorKeyHandlingStub(value="", cursor_position=0)
    event = _FakeKeyEvent(key="!", character="!")
    Editor.on_key(cast(Editor, editor), event)
    assert event.prevented is True
    assert editor.value == Editor.BASH_MODE_PREFIX_WITH_SPACE
    assert editor.cursor_position == len(editor.value)


def test_bang_toggles_off_and_strips_prefix() -> None:
    editor = _EditorKeyHandlingStub(value="! ls", cursor_position=4)
    event = _FakeKeyEvent(key="!", character="!")
    Editor.on_key(cast(Editor, editor), event)
    assert event.prevented is True
    assert editor.value == "ls"
    assert editor.cursor_position == len(editor.value)


def test_bang_in_normal_text_does_not_toggle() -> None:
    editor = _EditorKeyHandlingStub(value="hello", cursor_position=5)
    event = _FakeKeyEvent(key="!", character="!")
    Editor.on_key(cast(Editor, editor), event)
    assert event.prevented is False
    assert editor.value == "hello"
