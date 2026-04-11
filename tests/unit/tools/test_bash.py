from __future__ import annotations

import pytest

from tunacode.tools.bash import CMD_OUTPUT_TRUNCATED, build_bash_tool


@pytest.mark.asyncio
async def test_build_bash_tool_truncates_using_injected_max_command_output() -> None:
    bash_tool = build_bash_tool(max_command_output=64)

    result = await bash_tool.execute(
        "tool-call-1",
        {"command": "python -c \"print('x' * 4000)\""},
        None,
        lambda *_args, **_kwargs: None,
    )

    assert result.content[0].text is not None
    assert CMD_OUTPUT_TRUNCATED in result.content[0].text
    assert result.content[0].text.startswith("Command: python -c")
