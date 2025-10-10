"""Characterization tests for ToolUI confirmation flows."""

from unittest.mock import AsyncMock, patch

import pytest

import tunacode.ui.tool_ui as tool_ui_mod
from tunacode.core.tool_handler import ToolConfirmationRequest


@pytest.mark.asyncio
async def test_toolui_option_three_aborts_without_feedback(monkeypatch):
    """Golden test: option 3 aborts without capturing user guidance."""

    tool_ui = tool_ui_mod.ToolUI()
    request = ToolConfirmationRequest(tool_name="bash", args={}, filepath=None)

    monkeypatch.setattr(tool_ui_mod.ui, "tool_confirm", AsyncMock())
    monkeypatch.setattr(tool_ui_mod.ui, "print", AsyncMock())
    monkeypatch.setattr(tool_ui_mod.ui, "usage", AsyncMock())
    monkeypatch.setattr(tool_ui_mod.ui, "input", AsyncMock(side_effect=["3", ""]))

    response = await tool_ui.show_confirmation(request)

    assert response.approved is False
    assert response.abort is True
    assert response.instructions == ""


def test_toolui_get_tool_title_internal():
    tool_ui = tool_ui_mod.ToolUI()
    with patch("tunacode.ui.tool_ui.ApplicationSettings") as mock_settings:
        mock_settings.return_value.internal_tools = ["foo"]
        assert tool_ui._get_tool_title("foo") == "Tool(foo)"
        assert tool_ui._get_tool_title("bar") == "MCP(bar)"


def test_toolui_create_code_block_returns_markdown():
    tool_ui = tool_ui_mod.ToolUI()
    with patch("tunacode.ui.tool_ui.ext_to_lang", return_value="python"):
        # Import the actual markdown function
        from tunacode.ui import console

        with patch.object(console, "markdown") as mock_md:
            mock_md.return_value = "MARKDOWN_OBJ"
            result = tool_ui._create_code_block("file.py", "print(1)")
            assert result == "MARKDOWN_OBJ"
            mock_md.assert_called_once()
