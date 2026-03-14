from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tunacode.ui.lifecycle import TEST_READY_FILE_ENV_VAR, AppLifecycle


class FakeLogger:
    def __init__(self) -> None:
        self.state_manager = None
        self.tui_callback = None

    def set_state_manager(self, state_manager: object) -> None:
        self.state_manager = state_manager

    def set_tui_callback(self, callback: object) -> None:
        self.tui_callback = callback


def _build_app() -> SimpleNamespace:
    return SimpleNamespace(
        state_manager=SimpleNamespace(session=SimpleNamespace(user_config={})),
        editor=object(),
        chat_container=SimpleNamespace(write=lambda _renderable: None),
        _request_worker=object(),
        _slopgotchi_timer=None,
        _update_resource_bar=lambda: None,
        _update_slopgotchi=lambda: None,
        set_focus=lambda _target: None,
        run_worker=lambda _worker, exclusive=False: None,
        set_interval=lambda _interval, _callback: "timer",
    )


def test_start_repl_writes_ready_file_when_env_var_is_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready_file = tmp_path / "ready.txt"
    logger = FakeLogger()
    app = _build_app()

    monkeypatch.setenv(TEST_READY_FILE_ENV_VAR, str(ready_file))
    monkeypatch.setattr("tunacode.core.logging.get_logger", lambda: logger)
    monkeypatch.setattr("tunacode.ui.welcome.show_welcome", lambda _container: None)

    lifecycle = AppLifecycle(app)
    lifecycle._start_repl()

    assert ready_file.is_file()
    contents = ready_file.read_text(encoding="utf-8")
    assert contents.startswith("ready\n")
    assert f"cwd={Path.cwd()}" in contents


def test_start_repl_does_not_write_ready_file_without_env_var(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready_file = tmp_path / "ready.txt"
    logger = FakeLogger()
    app = _build_app()

    monkeypatch.delenv(TEST_READY_FILE_ENV_VAR, raising=False)
    monkeypatch.setattr("tunacode.core.logging.get_logger", lambda: logger)
    monkeypatch.setattr("tunacode.ui.welcome.show_welcome", lambda _container: None)

    lifecycle = AppLifecycle(app)
    lifecycle._start_repl()

    assert not ready_file.exists()
