"""Tests for converting TunaCode tools to tinyAgent AgentTool objects."""

import asyncio

import pytest

from tunacode.exceptions import ToolRetryError

from tunacode.tools.decorators import base_tool, to_tinyagent_tool


class TestToTinyagentTool:
    async def test_execute_returns_agenttoolresult_text(self, mock_no_xml_prompt):
        @base_tool
        async def echo(text: str) -> str:
            return f"echo: {text}"

        tool = to_tinyagent_tool(echo)

        result = await tool.execute(  # type: ignore[union-attr]
            "call-1",
            {"text": "hi"},
            None,
            lambda _update: None,
        )

        assert result.content[0]["type"] == "text"
        assert "echo: hi" in result.content[0]["text"]

    async def test_execute_validates_arguments(self, mock_no_xml_prompt):
        @base_tool
        async def needs_two(a: int, b: int) -> str:
            return str(a + b)

        tool = to_tinyagent_tool(needs_two)

        with pytest.raises(ToolRetryError, match="Invalid arguments"):
            await tool.execute(  # type: ignore[union-attr]
                "call-1",
                {"a": 1},
                None,
                lambda _update: None,
            )

    async def test_execute_aborts_on_signal(self, mock_no_xml_prompt):
        @base_tool
        async def slow() -> str:
            await asyncio.sleep(0)
            return "ok"

        tool = to_tinyagent_tool(slow)
        signal = asyncio.Event()
        signal.set()

        from tunacode.exceptions import UserAbortError

        with pytest.raises(UserAbortError):
            await tool.execute(  # type: ignore[union-attr]
                "call-1",
                {},
                signal,
                lambda _update: None,
            )
