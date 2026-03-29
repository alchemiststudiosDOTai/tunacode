from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from tinyagent.agent_types import AssistantMessage, TextContent

from tunacode.core.session import StateManager

from tunacode.ui.app import TextualReplApp


async def _wait_until(predicate: object, *, timeout: float, step: float = 0.01) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if callable(predicate) and predicate():
            return
        await asyncio.sleep(step)
    raise AssertionError(f"Condition not met within {timeout:.2f}s")


@pytest.mark.asyncio
async def test_submit_loading_indicator_lifecycle_remains_responsive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home_dir = tmp_path / "home"
    data_dir = tmp_path / "xdg-data"
    ready_file = tmp_path / "ready.txt"
    data_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_dir))
    monkeypatch.setenv("TUNACODE_TEST_READY_FILE", str(ready_file))

    state_manager = StateManager()
    state_manager.save_session = AsyncMock(return_value=True)  # type: ignore[method-assign]
    app = TextualReplApp(state_manager=state_manager)

    started_events = [threading.Event(), threading.Event()]
    release_events = [threading.Event(), threading.Event()]
    calls: list[str] = []

    async def _fake_process_request(
        *,
        message: str,
        state_manager: StateManager,
        **_: object,
    ) -> None:
        call_index = len(calls)
        calls.append(message)
        started_events[call_index].set()
        await asyncio.to_thread(release_events[call_index].wait)
        state_manager.session.conversation.messages.append(
            AssistantMessage(content=[TextContent(text=f"response-{call_index + 1}")])
        )

    async with app.run_test() as pilot:
        with patch(
            "tunacode.core.agents.main.process_request",
            new=_fake_process_request,
        ):
            app.editor.value = "first prompt"
            await pilot.press("enter")

            await _wait_until(lambda: app.loading_indicator.has_class("active"), timeout=0.5)
            await _wait_until(started_events[0].is_set, timeout=0.5)
            assert calls == ["first prompt"]

            release_events[0].set()

            await _wait_until(lambda: not app.loading_indicator.has_class("active"), timeout=1.0)
            await _wait_until(lambda: len(list(app.query(".agent-panel"))) >= 1, timeout=1.0)

            app.editor.value = "second prompt"
            await pilot.press("enter")

            await _wait_until(lambda: app.loading_indicator.has_class("active"), timeout=0.5)
            await _wait_until(started_events[1].is_set, timeout=0.5)
            assert calls == ["first prompt", "second prompt"]

            release_events[1].set()

            await _wait_until(lambda: not app.loading_indicator.has_class("active"), timeout=1.0)
            await _wait_until(lambda: len(list(app.query(".agent-panel"))) >= 2, timeout=1.0)
