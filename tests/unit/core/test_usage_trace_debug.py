from __future__ import annotations

from dataclasses import dataclass, field

from tunacode.types.canonical import UsageMetrics

from tunacode.core.debug import (
    build_resource_bar_lifecycle_message,
    build_usage_lifecycle_message,
    log_resource_bar_update,
    log_usage_update,
)


@dataclass
class _FakeLifecycleLogger:
    messages: list[str] = field(default_factory=list)

    def lifecycle(self, message: str) -> None:
        self.messages.append(message)


def _usage(
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read: int,
    cache_write: int,
    total_tokens: int,
    cost_total: float,
) -> UsageMetrics:
    return UsageMetrics.from_dict(
        {
            "input": input_tokens,
            "output": output_tokens,
            "cache_read": cache_read,
            "cache_write": cache_write,
            "total_tokens": total_tokens,
            "cost": {
                "input": 0.0,
                "output": 0.0,
                "cache_read": 0.0,
                "cache_write": 0.0,
                "total": cost_total,
            },
        }
    )


def test_build_usage_lifecycle_message_contains_last_call_and_session_total() -> None:
    last_call = _usage(
        input_tokens=10,
        output_tokens=5,
        cache_read=2,
        cache_write=1,
        total_tokens=15,
        cost_total=0.02,
    )
    session_total = _usage(
        input_tokens=100,
        output_tokens=50,
        cache_read=20,
        cache_write=5,
        total_tokens=150,
        cost_total=0.2,
    )

    message = build_usage_lifecycle_message(
        request_id="abcd1234",
        event_name="message_end",
        last_call_usage=last_call,
        session_total_usage=session_total,
    )

    assert "Usage:" in message
    assert "event=message_end" in message
    assert "req=abcd1234" in message
    assert "last_call(in=10,out=5,cache_read=2,cache_write=1,total=15,cost=0.020000)" in message
    assert (
        "session_total(in=100,out=50,cache_read=20,cache_write=5,total=150,cost=0.200000)"
        in message
    )


def test_build_resource_bar_lifecycle_message_clamps_remaining_percentage() -> None:
    message = build_resource_bar_lifecycle_message(
        model="openrouter:openai/gpt-4.1-mini",
        estimated_tokens=250000,
        max_tokens=200000,
        session_cost=0.1234567,
    )

    assert "Resource:" in message
    assert "model=openrouter:openai/gpt-4.1-mini" in message
    assert "context=250000/200000" in message
    assert "remaining=0.0%" in message
    assert "session_cost=0.123457" in message


def test_log_usage_update_emits_single_lifecycle_message() -> None:
    logger = _FakeLifecycleLogger()
    usage = _usage(
        input_tokens=1,
        output_tokens=2,
        cache_read=0,
        cache_write=0,
        total_tokens=3,
        cost_total=0.0,
    )

    log_usage_update(
        logger=logger,
        request_id="r1",
        event_name="debug_toggle",
        last_call_usage=usage,
        session_total_usage=usage,
    )

    assert len(logger.messages) == 1
    assert logger.messages[0].startswith("Usage: event=debug_toggle")


def test_log_resource_bar_update_emits_single_lifecycle_message() -> None:
    logger = _FakeLifecycleLogger()

    log_resource_bar_update(
        logger=logger,
        model="openrouter:openai/gpt-4.1-mini",
        estimated_tokens=100,
        max_tokens=200,
        session_cost=1.5,
    )

    assert len(logger.messages) == 1
    assert logger.messages[0] == (
        "Resource: model=openrouter:openai/gpt-4.1-mini "
        "context=100/200 remaining=50.0% session_cost=1.500000"
    )
