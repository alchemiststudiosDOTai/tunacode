import pytest


@pytest.mark.asyncio
async def test_patch_model_history_injects_tool_return(monkeypatch):
    # Import pydantic-ai message classes
    from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart

    # Build a fake history with a single assistant response that has a tool call
    tool_call = ToolCallPart(tool_name="read_file", args="{}", tool_call_id="call_abc")
    history = [ModelResponse(parts=[tool_call])]

    # Import the function under test
    from tunacode.core.agents.agent_components.message_handler import (
        patch_tool_messages_in_history,
    )

    # Sanity: no tool-return present yet
    assert not any(
        isinstance(p, ToolReturnPart)
        for m in history
        if hasattr(m, "parts")
        for p in getattr(m, "parts", [])
    )

    # Patch with a synthetic error message
    patch_tool_messages_in_history(history, "Synthetic tool error")

    # Assert a new ModelRequest with a ToolReturnPart was appended
    assert isinstance(history[-1], ModelRequest), "Expected a ModelRequest appended to history"
    parts = history[-1].parts
    assert len(parts) == 1 and isinstance(parts[0], ToolReturnPart)
    trp = parts[0]
    assert trp.tool_name == "read_file"
    assert trp.tool_call_id == "call_abc"
    assert "Synthetic tool error" in trp.model_response_str()


@pytest.mark.asyncio
async def test_patch_model_history_noop_when_already_returned():
    from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart

    tool_call = ToolCallPart(tool_name="grep", args="{}", tool_call_id="call_1")
    tool_return = ToolReturnPart(tool_name="grep", content="ok", tool_call_id="call_1")
    history = [ModelResponse(parts=[tool_call]), ModelRequest(parts=[tool_return])]

    from tunacode.core.agents.agent_components.message_handler import (
        patch_tool_messages_in_history,
    )

    patch_tool_messages_in_history(history, "Should not add")

    # Ensure no extra message appended
    assert history[-1] is not None
    assert isinstance(history[-1], ModelRequest)
    assert len(history) == 2
