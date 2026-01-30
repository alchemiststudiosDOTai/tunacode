"""Token and cost tracking for agent responses."""

from typing import Any

from tunacode.configuration.pricing import calculate_cost, get_model_pricing
from tunacode.types.canonical import UsageMetrics, normalize_request_usage

from tunacode.core.logging import get_logger
from tunacode.core.types import SessionStateProtocol

DEFAULT_COST = 0.0
MIN_TOKEN_COUNT = 0


def update_usage(session: SessionStateProtocol, usage: Any | None, model_name: str) -> None:
    """Update session usage tracking from model response usage."""
    logger = get_logger()
    normalized_usage = normalize_request_usage(usage)
    if normalized_usage is None:
        return

    prompt_tokens = normalized_usage.request_tokens
    completion_tokens = normalized_usage.response_tokens
    cached_tokens = normalized_usage.cached_tokens

    pricing = get_model_pricing(model_name)
    if pricing is None:
        cost = DEFAULT_COST
    else:
        non_cached_input = max(
            MIN_TOKEN_COUNT,
            prompt_tokens - cached_tokens,
        )
        cost = calculate_cost(
            pricing,
            non_cached_input,
            cached_tokens,
            completion_tokens,
        )

    # Update last call usage with new metrics
    session.usage.last_call_usage = UsageMetrics(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        cost=cost,
    )

    # Accumulate into session totals
    session.usage.session_total_usage.add(session.usage.last_call_usage)

    # Debug logging for token counts
    logger.lifecycle(
        f"Tokens: in={prompt_tokens} out={completion_tokens} "
        f"cached={cached_tokens} cost=${cost:.4f}"
    )
