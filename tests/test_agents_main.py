from types import SimpleNamespace
from typing import Any, List, Tuple

import pytest

from tunacode.core.agents import agent_components as ac
from tunacode.core.agents import main
from tunacode.core.state import StateManager


def _make_node(parts: list) -> SimpleNamespace:
    return SimpleNamespace(model_response=SimpleNamespace(parts=parts))


def test_iteration_had_tool_use_true_when_tool_call_present() -> None:
    part = SimpleNamespace(part_kind="tool-call")
    node = _make_node([part])

    assert main._iteration_had_tool_use(node) is True


def test_iteration_had_tool_use_false_without_tool_call() -> None:
    regular_part = SimpleNamespace(part_kind="text")
    empty_parts_node = _make_node([])
    text_only_node = _make_node([regular_part])
    missing_attribute_node = SimpleNamespace()

    assert main._iteration_had_tool_use(empty_parts_node) is False
    assert main._iteration_had_tool_use(text_only_node) is False
    assert main._iteration_had_tool_use(missing_attribute_node) is False


@pytest.mark.asyncio
async def test_finalize_buffered_tasks_executes_and_flushes(monkeypatch) -> None:
    state = main.StateFacade(StateManager())
    tool_buffer = ac.ToolBuffer()

    part_a = SimpleNamespace(tool_name="read_file", args={"file_path": "README.md"})
    part_b = SimpleNamespace(tool_name="grep", args={"pattern": "TODO"})
    node_a, node_b = object(), object()
    tool_buffer.add(part_a, node_a)
    tool_buffer.add(part_b, node_b)

    captured: dict[str, Any] = {"tool_calls": []}
    callback_invocations: List[Tuple[Any, Any]] = []

    async def fake_execute(tool_calls, callback):
        captured["tool_calls"] = list(tool_calls)
        results = []
        for part, node in tool_calls:
            results.append(await callback(part, node))
        return results

    async def fake_tool_callback(part, node):
        callback_invocations.append((part, node))
        return f"ok:{getattr(part, 'tool_name', '?')}"

    async def noop_ui(*_args, **_kwargs):
        return None

    monkeypatch.setattr(ac, "execute_tools_parallel", fake_execute)
    monkeypatch.setattr(main.ui, "muted", noop_ui)
    monkeypatch.setattr(main.ui, "update_spinner_message", noop_ui)

    await main._finalize_buffered_tasks(tool_buffer, fake_tool_callback, state)

    assert captured["tool_calls"] == [(part_a, node_a), (part_b, node_b)]
    assert callback_invocations == [(part_a, node_a), (part_b, node_b)]
    assert tool_buffer.has_tasks() is False


@pytest.mark.asyncio
async def test_finalize_buffered_tasks_noop_without_callback(monkeypatch) -> None:
    state = main.StateFacade(StateManager())
    tool_buffer = ac.ToolBuffer()
    part = SimpleNamespace(tool_name="read_file", args={})
    tool_buffer.add(part, object())

    called = False

    async def fake_execute(tool_calls, callback):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(ac, "execute_tools_parallel", fake_execute)

    await main._finalize_buffered_tasks(tool_buffer, None, state)

    assert called is False
    # Buffer should remain untouched because we never flush without callback
    assert tool_buffer.has_tasks() is True
