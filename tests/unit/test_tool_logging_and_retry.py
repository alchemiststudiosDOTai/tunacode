from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_patch_model_history_skips_when_retry_present():
    from pydantic_ai.messages import ModelResponse, RetryPromptPart, ToolCallPart

    from tunacode.core.agents.agent_components.message_handler import (
        patch_tool_messages_in_history,
    )

    # Given: one tool_call and a retry prompt referencing the same tool_call_id
    call = ToolCallPart(tool_name="grep", args="{}", tool_call_id="call_retry")
    retry = RetryPromptPart(content="retry it", tool_name="grep", tool_call_id="call_retry")
    history = [ModelResponse(parts=[call, retry])]

    # When: patching message history
    patch_tool_messages_in_history(history, "Should not inject")

    # Then: no new ModelRequest appended (retry covers pairing)
    assert len(history) == 1
    assert isinstance(history[0], ModelResponse)


class DummyUI:
    def __init__(self):
        self.messages = []

    async def muted(self, msg: str):
        self.messages.append(msg)

    async def warning(self, msg: str):
        self.messages.append(msg)

    async def update_spinner_message(self, msg: str, _state_manager):
        # record spinner updates for visibility
        self.messages.append(f"SPINNER: {msg}")


@pytest.mark.asyncio
async def test_tool_call_and_return_logging_with_thoughts(monkeypatch):
    # Patch UI console to capture logs
    from tunacode import ui as ui_pkg

    dummy = DummyUI()
    monkeypatch.setattr(ui_pkg, "console", dummy)

    # Prepare message parts: a tool-call and a tool-return
    from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart

    tool_call = ToolCallPart(
        tool_name="read_file",
        args='{"file_path":"README.md"}',
        tool_call_id="call_12345",
    )
    tool_return = ToolReturnPart(
        tool_name="read_file",
        content={"ok": True, "data": "..."},
        tool_call_id="call_12345",
    )

    node = SimpleNamespace(model_response=ModelResponse(parts=[tool_call, tool_return]))

    # Create minimal state manager stub
    session = SimpleNamespace(show_thoughts=True)
    state_manager = SimpleNamespace(session=session, is_plan_mode=lambda: False)

    # Import functions under test
    from tunacode.core.agents.agent_components.node_processor import (
        _display_raw_api_response,
        _process_tool_calls,
    )
    from tunacode.core.agents.agent_components.tool_buffer import ToolBuffer

    # When: displaying raw response (should log tool-return)
    await _display_raw_api_response(node, dummy)

    # And: processing tool calls (should log tool-call with args)
    await _process_tool_calls(
        node,
        tool_callback=None,
        state_manager=state_manager,
        tool_buffer=ToolBuffer(),
        response_state=None,
    )

    # Then: verify logs contain both tool call and tool return details
    combined = "\n".join(dummy.messages)
    assert "TOOL CALL" in combined and "read_file" in combined and "call_12345" in combined
    assert "README.md" in combined  # pretty-printed args
    assert "TOOL RETURN" in combined and "ok" in combined
