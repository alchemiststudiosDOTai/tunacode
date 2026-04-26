from __future__ import annotations

from tinyagent.agent_types import AgentToolResult, TextContent

from tunacode.constants import MAX_CALLBACK_CONTENT

from tunacode.ui import repl_support

FILLER_UNIT: str = "x"


def test_truncate_for_safety_truncates_long_content() -> None:
    content: str = FILLER_UNIT * (MAX_CALLBACK_CONTENT + 50)

    truncated: str | None = repl_support._truncate_for_safety(content)

    assert truncated is not None
    assert len(truncated) == MAX_CALLBACK_CONTENT
    assert truncated.endswith(repl_support.CALLBACK_TRUNCATION_NOTICE)


class _FakeApp:
    def __init__(self) -> None:
        self.posted_messages: list[object] = []

    def post_message(self, message: object) -> bool:
        self.posted_messages.append(message)
        return True


def test_tool_result_callback_posts_message_for_completed_file_edit() -> None:
    app = _FakeApp()
    result_callback = repl_support.build_tool_result_callback(app)

    result_callback(
        "write_file",
        "completed",
        {"filepath": " src/example.py "},
        AgentToolResult(content=[TextContent(text="ok")], details={}),
        12.0,
    )

    assert len(app.posted_messages) == 1
