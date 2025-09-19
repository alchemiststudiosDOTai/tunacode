from types import SimpleNamespace

import pytest

# Import target function and types
from tunacode.core.agents.agent_components.node_processor import (
    _process_tool_calls,
)
from tunacode.core.agents.agent_components.tool_buffer import ToolBuffer


class DummyUI:
    async def muted(self, *args, **kwargs):
        return None

    async def warning(self, *args, **kwargs):
        return None

    async def update_spinner_message(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_openai_strict_pairing_executes_tools_immediately(monkeypatch):
    # Patch UI console used inside node_processor
    from tunacode import ui as ui_pkg

    monkeypatch.setattr(ui_pkg, "console", DummyUI())

    # Build a fake tool-call part and node
    part = SimpleNamespace(
        part_kind="tool-call",
        tool_name="read_file",
        args={"file_path": "README.md"},
        tool_call_id="call_123",
    )

    model_response = SimpleNamespace(parts=[part])
    node = SimpleNamespace(model_response=model_response)

    # State manager/session mock
    session = SimpleNamespace(
        show_thoughts=False,
        current_model="openai:gpt-4.1",
        batch_counter=0,
        tool_calls=[],
    )

    state_manager = SimpleNamespace(
        session=session,
        is_plan_mode=lambda: False,
    )

    # Track tool callback invocations
    calls: list[tuple] = []

    async def tool_callback(p, n):
        calls.append((p, n))
        # Simulate tool returning structured success. Return value is ignored by node_processor.
        return {"ok": True, "data": "dummy"}

    # Provide a buffer (should not be used for strict pairing)
    buffer = ToolBuffer()

    # Run
    await _process_tool_calls(
        node=node,
        tool_callback=tool_callback,
        state_manager=state_manager,
        tool_buffer=buffer,
        response_state=None,
    )

    # Assert tool executed immediately and buffer is empty
    assert len(calls) == 1, "Tool callback should be executed immediately for OpenAI models"
    assert not buffer.has_tasks(), "No tasks should remain buffered under strict pairing"
