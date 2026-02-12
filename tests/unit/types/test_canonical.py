"""Unit tests for canonical types."""

from datetime import datetime

import pytest

from tunacode.types.canonical import (
    CanonicalMessage,
    CanonicalToolCall,
    MessageRole,
    PartKind,
    RecursiveContext,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThoughtPart,
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

    def test_retry_prompt_part_creation(self) -> None:
        part = RetryPromptPart(
            tool_call_id="tc_123",
            tool_name="read_file",
            content="Try again",
        )
        assert part.tool_call_id == "tc_123"
        assert part.tool_name == "read_file"
        assert part.content == "Try again"
        assert part.kind == PartKind.RETRY_PROMPT

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
                SystemPromptPart(content="System"),
                ThoughtPart(content="thinking"),
                ToolReturnPart(tool_call_id="tc_1", content="result"),
                RetryPromptPart(tool_call_id="tc_2", tool_name="bash", content="retry"),
                TextPart(content="World"),
            ),
        )
        assert msg.get_text_content() == "Hello System thinking result retry World"

    def test_get_text_content_ignores_tool_parts(self) -> None:
        msg = CanonicalMessage(
            role=MessageRole.ASSISTANT,
            parts=(
                TextPart(content="Before"),
                ToolCallPart(tool_call_id="tc_1", tool_name="bash", args={}),
                TextPart(content="After"),
            ),
        )
        assert msg.get_text_content() == "Before  After"

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


class TestUsageMetrics:
    """Tests for UsageMetrics."""

    def test_usage_metrics_defaults(self) -> None:
        usage = UsageMetrics()
        assert usage.input == 0
        assert usage.output == 0
        assert usage.cache_read == 0
        assert usage.cache_write == 0
        assert usage.total_tokens == 0
        assert usage.cost.input == 0.0
        assert usage.cost.output == 0.0
        assert usage.cost.cache_read == 0.0
        assert usage.cost.cache_write == 0.0
        assert usage.cost.total == 0.0

    def test_usage_metrics_total_tokens_stored_value(self) -> None:
        usage = UsageMetrics(total_tokens=150)
        assert usage.total_tokens == 150

    def test_usage_metrics_add(self) -> None:
        usage1 = UsageMetrics.from_dict(
            {
                "input": 100,
                "output": 50,
                "cache_read": 10,
                "cache_write": 5,
                "total_tokens": 150,
                "cost": {
                    "input": 0.01,
                    "output": 0.02,
                    "cache_read": 0.001,
                    "cache_write": 0.0005,
                    "total": 0.0315,
                },
            }
        )
        usage2 = UsageMetrics.from_dict(
            {
                "input": 200,
                "output": 100,
                "cache_read": 20,
                "cache_write": 8,
                "total_tokens": 300,
                "cost": {
                    "input": 0.03,
                    "output": 0.04,
                    "cache_read": 0.002,
                    "cache_write": 0.001,
                    "total": 0.073,
                },
            }
        )

        usage1.add(usage2)

        assert usage1.input == 300
        assert usage1.output == 150
        assert usage1.cache_read == 30
        assert usage1.cache_write == 13
        assert usage1.total_tokens == 450
        assert usage1.cost.input == pytest.approx(0.04)
        assert usage1.cost.output == pytest.approx(0.06)
        assert usage1.cost.cache_read == pytest.approx(0.003)
        assert usage1.cost.cache_write == pytest.approx(0.0015)
        assert usage1.cost.total == pytest.approx(0.1045)

    def test_usage_metrics_from_dict(self) -> None:
        data = {
            "input": 500,
            "output": 200,
            "cache_read": 100,
            "cache_write": 15,
            "total_tokens": 700,
            "cost": {
                "input": 0.03,
                "output": 0.05,
                "cache_read": 0.01,
                "cache_write": 0.002,
                "total": 0.092,
            },
        }
        usage = UsageMetrics.from_dict(data)
        assert usage.input == 500
        assert usage.output == 200
        assert usage.cache_read == 100
        assert usage.cache_write == 15
        assert usage.total_tokens == 700
        assert usage.cost.total == pytest.approx(0.092)

    def test_usage_metrics_from_dict_rejects_legacy_schema(self) -> None:
        with pytest.raises(ValueError, match=r"usage missing key\(s\)"):
            UsageMetrics.from_dict(
                {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "cached_tokens": 10,
                    "cost": 0.01,
                }
            )

    def test_usage_metrics_from_dict_requires_cost_keys(self) -> None:
        with pytest.raises(ValueError, match=r"usage\.cost missing key\(s\)"):
            UsageMetrics.from_dict(
                {
                    "input": 100,
                    "output": 50,
                    "cache_read": 25,
                    "cache_write": 9,
                    "total_tokens": 150,
                    "cost": {
                        "input": 0.01,
                        "output": 0.02,
                        "cache_read": 0.003,
                        "total": 0.034,
                    },
                }
            )

    def test_usage_metrics_to_dict(self) -> None:
        usage = UsageMetrics.from_dict(
            {
                "input": 100,
                "output": 50,
                "cache_read": 25,
                "cache_write": 9,
                "total_tokens": 150,
                "cost": {
                    "input": 0.01,
                    "output": 0.02,
                    "cache_read": 0.003,
                    "cache_write": 0.001,
                    "total": 0.034,
                },
            }
        )
        result = usage.to_dict()
        assert result == {
            "input": 100,
            "output": 50,
            "cache_read": 25,
            "cache_write": 9,
            "total_tokens": 150,
            "cost": {
                "input": 0.01,
                "output": 0.02,
                "cache_read": 0.003,
                "cache_write": 0.001,
                "total": 0.034,
            },
        }


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
