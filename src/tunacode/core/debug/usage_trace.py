"""Usage/cost lifecycle tracing helpers used by /debug mode."""

from __future__ import annotations

from typing import Protocol

from tunacode.types.canonical import UsageMetrics

PERCENT_MULTIPLIER = 100.0
COST_PRECISION = 6


class LifecycleLogger(Protocol):
    """Minimal logger contract required for lifecycle tracing."""

    def lifecycle(self, message: str) -> None: ...


def build_usage_lifecycle_message(
    *,
    request_id: str,
    event_name: str,
    last_call_usage: UsageMetrics,
    session_total_usage: UsageMetrics,
) -> str:
    """Build a compact lifecycle line for usage updates."""
    return (
        "Usage: "
        f"event={event_name} "
        f"req={request_id} "
        "last_call("
        f"in={last_call_usage.input},"
        f"out={last_call_usage.output},"
        f"cache_read={last_call_usage.cache_read},"
        f"cache_write={last_call_usage.cache_write},"
        f"total={last_call_usage.total_tokens},"
        f"cost={last_call_usage.cost.total:.{COST_PRECISION}f}"
        ") "
        "session_total("
        f"in={session_total_usage.input},"
        f"out={session_total_usage.output},"
        f"cache_read={session_total_usage.cache_read},"
        f"cache_write={session_total_usage.cache_write},"
        f"total={session_total_usage.total_tokens},"
        f"cost={session_total_usage.cost.total:.{COST_PRECISION}f}"
        ")"
    )


def log_usage_update(
    *,
    logger: LifecycleLogger,
    request_id: str,
    event_name: str,
    last_call_usage: UsageMetrics,
    session_total_usage: UsageMetrics,
) -> None:
    """Emit a lifecycle log line for a usage update event."""
    lifecycle_message = build_usage_lifecycle_message(
        request_id=request_id,
        event_name=event_name,
        last_call_usage=last_call_usage,
        session_total_usage=session_total_usage,
    )
    logger.lifecycle(lifecycle_message)


def build_resource_bar_lifecycle_message(
    *,
    model: str,
    estimated_tokens: int,
    max_tokens: int,
    session_cost: float,
) -> str:
    """Build a compact lifecycle line for resource bar refreshes."""
    if max_tokens <= 0:
        remaining_pct = 0.0
    else:
        remaining_tokens = max_tokens - estimated_tokens
        remaining_pct = (remaining_tokens / max_tokens) * PERCENT_MULTIPLIER

    clamped_remaining_pct = max(0.0, min(PERCENT_MULTIPLIER, remaining_pct))

    return (
        "Resource: "
        f"model={model} "
        f"context={estimated_tokens}/{max_tokens} "
        f"remaining={clamped_remaining_pct:.1f}% "
        f"session_cost={session_cost:.{COST_PRECISION}f}"
    )


def log_resource_bar_update(
    *,
    logger: LifecycleLogger,
    model: str,
    estimated_tokens: int,
    max_tokens: int,
    session_cost: float,
) -> None:
    """Emit a lifecycle log line for resource bar refreshes."""
    lifecycle_message = build_resource_bar_lifecycle_message(
        model=model,
        estimated_tokens=estimated_tokens,
        max_tokens=max_tokens,
        session_cost=session_cost,
    )
    logger.lifecycle(lifecycle_message)
