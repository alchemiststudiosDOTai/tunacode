from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_patch_history_mixed_calls_injects_only_missing():
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        RetryPromptPart,
        ToolCallPart,
        ToolReturnPart,
    )

    from tunacode.core.agents.agent_components.message_handler import (
        patch_tool_messages_in_history,
    )

    # Build a mixed scenario with three tool calls in one response
    call_a = ToolCallPart(tool_name="glob", args="{}", tool_call_id="A")
    call_b = ToolCallPart(tool_name="grep", args="{}", tool_call_id="B")
    call_c = ToolCallPart(tool_name="read_file", args="{}", tool_call_id="C")
    resp = ModelResponse(parts=[call_a, call_b, call_c])

    # One return already present for C
    ret_c = ToolReturnPart(tool_name="read_file", content={"ok": True}, tool_call_id="C")
    # One retry present for B (validation failure)
    retry_b = RetryPromptPart(content="retry", tool_name="grep", tool_call_id="B")

    history = [resp, ModelRequest(parts=[ret_c, retry_b])]

    # Patch history: should inject only for A
    patch_tool_messages_in_history(history, "Synthetic failure")

    # Verify: last message is a ModelRequest with a ToolReturnPart for A only
    last = history[-1]
    assert isinstance(last, ModelRequest)
    assert len(last.parts) == 1
    part = last.parts[0]
    assert isinstance(part, ToolReturnPart)
    assert part.tool_name == "glob" and part.tool_call_id == "A"
    assert "Synthetic failure" in part.model_response_str()


class DummyUI:
    def __init__(self):
        self.messages = []

    async def muted(self, msg: str):
        self.messages.append(msg)


@pytest.mark.asyncio
async def test_tool_return_logging_with_error_content(monkeypatch):
    # Patch UI console to capture messages
    from tunacode import ui as ui_pkg

    dummy = DummyUI()
    monkeypatch.setattr(ui_pkg, "console", dummy)

    # Compose a tool-return with structured error content
    from pydantic_ai.messages import ModelResponse, ToolReturnPart

    error_payload = {"ok": False, "error": {"code": "COMMAND_FAILED", "message": "boom"}}
    ret = ToolReturnPart(tool_name="run_command", content=error_payload, tool_call_id="ERR1")
    node = SimpleNamespace(model_response=ModelResponse(parts=[ret]))

    # show_thoughts must be True to see tool-return logs

    from tunacode.core.agents.agent_components.node_processor import _display_raw_api_response

    await _display_raw_api_response(node, dummy)

    combined = "\n".join(dummy.messages)
    assert "TOOL RETURN" in combined and "run_command" in combined and "ERR1" in combined
    assert "COMMAND_FAILED" in combined or "boom" in combined
