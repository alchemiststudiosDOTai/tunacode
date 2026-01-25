"""Unit tests for canonical types."""

from datetime import datetime

import pytest

from tunacode.types.canonical import (
    CanonicalMessage,
    CanonicalToolCall,
    MessageRole,
    PartKind,
    ReActEntryKind,
    ReActScratchpad,
    RecursiveContext,
    SystemPromptPart,
    TextPart,
    ThoughtPart,
    TodoItem,
    TodoStatus,
    ToolCallPart,
    ToolCallStatus,
    ToolReturnPart,
    UsageMetrics,
)


class TestMessageParts:
    """Tests for message part types."""

    def test_text_part_creation(self) -> None:
        part = TextPart(content="hello world")
        assert part.content == "hello world"
        assert part.kind == PartKind.TEXT

    def test_thought_part_creation(self) -> None:
        part = ThoughtPart(content="thinking...")
        assert part.content == "thinking..."
        assert part.kind == PartKind.THOUGHT

    def test_system_prompt_part_creation(self) -> None:
        part = SystemPromptPart(content="You are helpful.")
        assert part.content == "You are helpful."
        assert part.kind == PartKind.SYSTEM_PROMPT

    def test_tool_call_part_creation(self) -> None:
        part = ToolCallPart(
            tool_call_id="tc_123",
            tool_name="read_file",
            args={"filepath": "/tmp/test.txt"},
        )
        assert part.tool_call_id == "tc_123"
        assert part.tool_name == "read_file"
        assert part.args == {"filepath": "/tmp/test.txt"}
        assert part.kind == PartKind.TOOL_CALL

    def test_tool_return_part_creation(self) -> None:
        part = ToolReturnPart(
            tool_call_id="tc_123",
            content="file contents here",
        )
        assert part.tool_call_id == "tc_123"
        assert part.content == "file contents here"
        assert part.kind == PartKind.TOOL_RETURN

    def test_parts_are_frozen(self) -> None:
        part = TextPart(content="immutable")
        with pytest.raises(AttributeError):
            part.content = "modified"  # type: ignore[misc]


class TestCanonicalMessage:
    """Tests for CanonicalMessage."""

    def test_message_creation(self) -> None:
        msg = CanonicalMessage(
            role=MessageRole.USER,
            parts=(TextPart(content="hello"),),
        )
        assert msg.role == MessageRole.USER
        assert len(msg.parts) == 1
        assert msg.timestamp is None

    def test_message_with_timestamp(self) -> None:
        now = datetime.now()
        msg = CanonicalMessage(
            role=MessageRole.ASSISTANT,
            parts=(TextPart(content="response"),),
            timestamp=now,
        )
        assert msg.timestamp == now

    def test_get_text_content(self) -> None:
        msg = CanonicalMessage(
            role=MessageRole.ASSISTANT,
            parts=(
                TextPart(content="Hello"),
                ThoughtPart(content="thinking"),
                TextPart(content="World"),
            ),
        )
        # Should concatenate text and thought parts
        assert msg.get_text_content() == "Hello thinking World"

    def test_get_text_content_ignores_tool_parts(self) -> None:
        msg = CanonicalMessage(
            role=MessageRole.ASSISTANT,
            parts=(
                TextPart(content="Before"),
                ToolCallPart(tool_call_id="tc_1", tool_name="bash", args={}),
                TextPart(content="After"),
            ),
        )
        assert msg.get_text_content() == "Before After"

    def test_get_tool_call_ids(self) -> None:
        msg = CanonicalMessage(
            role=MessageRole.ASSISTANT,
            parts=(
                ToolCallPart(tool_call_id="tc_1", tool_name="bash", args={}),
                ToolCallPart(tool_call_id="tc_2", tool_name="read_file", args={}),
            ),
        )
        assert msg.get_tool_call_ids() == {"tc_1", "tc_2"}

    def test_get_tool_return_ids(self) -> None:
        msg = CanonicalMessage(
            role=MessageRole.TOOL,
            parts=(
                ToolReturnPart(tool_call_id="tc_1", content="result 1"),
                ToolReturnPart(tool_call_id="tc_2", content="result 2"),
            ),
        )
        assert msg.get_tool_return_ids() == {"tc_1", "tc_2"}

    def test_message_is_frozen(self) -> None:
        msg = CanonicalMessage(
            role=MessageRole.USER,
            parts=(TextPart(content="test"),),
        )
        with pytest.raises(AttributeError):
            msg.role = MessageRole.ASSISTANT  # type: ignore[misc]


class TestCanonicalToolCall:
    """Tests for CanonicalToolCall."""

    def test_tool_call_creation(self) -> None:
        call = CanonicalToolCall(
            tool_call_id="tc_123",
            tool_name="read_file",
            args={"filepath": "/tmp/test.txt"},
        )
        assert call.tool_call_id == "tc_123"
        assert call.tool_name == "read_file"
        assert call.status == ToolCallStatus.PENDING
        assert call.result is None
        assert call.error is None

    def test_tool_call_is_complete(self) -> None:
        pending = CanonicalToolCall(
            tool_call_id="tc_1",
            tool_name="bash",
            args={},
            status=ToolCallStatus.PENDING,
        )
        assert not pending.is_complete

        running = CanonicalToolCall(
            tool_call_id="tc_2",
            tool_name="bash",
            args={},
            status=ToolCallStatus.RUNNING,
        )
        assert not running.is_complete

        completed = CanonicalToolCall(
            tool_call_id="tc_3",
            tool_name="bash",
            args={},
            status=ToolCallStatus.COMPLETED,
            result="done",
        )
        assert completed.is_complete

        failed = CanonicalToolCall(
            tool_call_id="tc_4",
            tool_name="bash",
            args={},
            status=ToolCallStatus.FAILED,
            error="something went wrong",
        )
        assert failed.is_complete


class TestTodoItem:
    """Tests for TodoItem."""

    def test_todo_item_creation(self) -> None:
        item = TodoItem(
            content="Write tests",
            status=TodoStatus.PENDING,
            active_form="Writing tests",
        )
        assert item.content == "Write tests"
        assert item.status == TodoStatus.PENDING
        assert item.active_form == "Writing tests"

    def test_todo_item_from_dict(self) -> None:
        data = {
            "content": "Fix bug",
            "status": "in_progress",
            "activeForm": "Fixing bug",
        }
        item = TodoItem.from_dict(data)
        assert item.content == "Fix bug"
        assert item.status == TodoStatus.IN_PROGRESS
        assert item.active_form == "Fixing bug"

    def test_todo_item_from_dict_snake_case(self) -> None:
        data = {
            "content": "Review PR",
            "status": "completed",
            "active_form": "Reviewing PR",
        }
        item = TodoItem.from_dict(data)
        assert item.active_form == "Reviewing PR"

    def test_todo_item_to_dict(self) -> None:
        item = TodoItem(
            content="Deploy",
            status=TodoStatus.COMPLETED,
            active_form="Deploying",
        )
        result = item.to_dict()
        assert result == {
            "content": "Deploy",
            "status": "completed",
            "activeForm": "Deploying",
        }

    def test_todo_item_round_trip(self) -> None:
        original = TodoItem(
            content="Test round trip",
            status=TodoStatus.IN_PROGRESS,
            active_form="Testing round trip",
        )
        as_dict = original.to_dict()
        restored = TodoItem.from_dict(as_dict)
        assert restored == original


class TestUsageMetrics:
    """Tests for UsageMetrics."""

    def test_usage_metrics_defaults(self) -> None:
        usage = UsageMetrics()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.cached_tokens == 0
        assert usage.cost == 0.0
        assert usage.total_tokens == 0

    def test_usage_metrics_total_tokens(self) -> None:
        usage = UsageMetrics(prompt_tokens=100, completion_tokens=50)
        assert usage.total_tokens == 150

    def test_usage_metrics_add(self) -> None:
        usage1 = UsageMetrics(prompt_tokens=100, completion_tokens=50, cost=0.01)
        usage2 = UsageMetrics(prompt_tokens=200, completion_tokens=100, cost=0.02)

        usage1.add(usage2)

        assert usage1.prompt_tokens == 300
        assert usage1.completion_tokens == 150
        assert usage1.cost == pytest.approx(0.03)

    def test_usage_metrics_from_dict(self) -> None:
        data = {
            "prompt_tokens": 500,
            "completion_tokens": 200,
            "cached_tokens": 100,
            "cost": 0.05,
        }
        usage = UsageMetrics.from_dict(data)
        assert usage.prompt_tokens == 500
        assert usage.completion_tokens == 200
        assert usage.cached_tokens == 100
        assert usage.cost == 0.05

    def test_usage_metrics_to_dict(self) -> None:
        usage = UsageMetrics(
            prompt_tokens=100,
            completion_tokens=50,
            cached_tokens=25,
            cost=0.01,
        )
        result = usage.to_dict()
        assert result == {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cached_tokens": 25,
            "cost": 0.01,
        }


class TestReActScratchpad:
    """Tests for ReActScratchpad."""

    def test_scratchpad_defaults(self) -> None:
        pad = ReActScratchpad()
        assert pad.timeline == []
        assert pad.forced_calls == 0
        assert pad.guidance == []

    def test_scratchpad_append(self) -> None:
        pad = ReActScratchpad()
        pad.append(ReActEntryKind.THINK, "I should read the file")
        pad.append(ReActEntryKind.ACT, "Reading file...")
        pad.append(ReActEntryKind.OBSERVE, "File contains: hello")

        assert len(pad.timeline) == 3
        assert pad.timeline[0].kind == ReActEntryKind.THINK
        assert pad.timeline[1].kind == ReActEntryKind.ACT
        assert pad.timeline[2].kind == ReActEntryKind.OBSERVE

    def test_scratchpad_clear(self) -> None:
        pad = ReActScratchpad()
        pad.append(ReActEntryKind.THINK, "something")
        pad.forced_calls = 5
        pad.guidance = ["hint 1", "hint 2"]

        pad.clear()

        assert pad.timeline == []
        assert pad.forced_calls == 0
        assert pad.guidance == []


class TestRecursiveContext:
    """Tests for RecursiveContext."""

    def test_recursive_context_creation(self) -> None:
        now = datetime.now()
        ctx = RecursiveContext(
            task_id="task_123",
            parent_task_id="task_000",
            depth=2,
            iteration_budget=10,
            created_at=now,
        )
        assert ctx.task_id == "task_123"
        assert ctx.parent_task_id == "task_000"
        assert ctx.depth == 2
        assert ctx.iteration_budget == 10
        assert ctx.created_at == now

    def test_recursive_context_root_task(self) -> None:
        now = datetime.now()
        ctx = RecursiveContext(
            task_id="root",
            parent_task_id=None,
            depth=0,
            iteration_budget=20,
            created_at=now,
        )
        assert ctx.parent_task_id is None
        assert ctx.depth == 0
