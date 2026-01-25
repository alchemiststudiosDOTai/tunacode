"""Token and cost tracking for agent responses."""

from typing import Any

from tunacode.configuration.pricing import calculate_cost, get_model_pricing
from tunacode.core.logging import get_logger
from tunacode.core.state import SessionState
from tunacode.types.pydantic_ai import normalize_request_usage

DEFAULT_COST = 0.0
MIN_TOKEN_COUNT = 0

SESSION_USAGE_KEY_PROMPT_TOKENS = "prompt_tokens"
SESSION_USAGE_KEY_COMPLETION_TOKENS = "completion_tokens"
SESSION_USAGE_KEY_COST = "cost"


def update_usage(session: SessionState, usage: Any | None, model_name: str) -> None:
    """Update session usage tracking from model response usage."""
    logger = get_logger()
    normalized_usage = normalize_request_usage(usage)
    if normalized_usage is None:
        return

    prompt_tokens = normalized_usage.request_tokens
    completion_tokens = normalized_usage.response_tokens
    cached_tokens = normalized_usage.cached_tokens

    usage_state = session.usage
    last_call_usage = usage_state.last_call_usage
    session_total_usage = usage_state.session_total_usage

    last_call_usage[SESSION_USAGE_KEY_PROMPT_TOKENS] = prompt_tokens
    last_call_usage[SESSION_USAGE_KEY_COMPLETION_TOKENS] = completion_tokens

    pricing = get_model_pricing(model_name)
    if pricing is None:
        last_call_usage[SESSION_USAGE_KEY_COST] = DEFAULT_COST
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
        last_call_usage[SESSION_USAGE_KEY_COST] = cost
        session_total_usage[SESSION_USAGE_KEY_COST] += cost

    session_total_usage[SESSION_USAGE_KEY_PROMPT_TOKENS] += prompt_tokens
    session_total_usage[SESSION_USAGE_KEY_COMPLETION_TOKENS] += completion_tokens

    # Debug logging for token counts
    logger.lifecycle(
        f"Tokens: in={prompt_tokens} out={completion_tokens} "
        f"cached={cached_tokens} cost=${cost:.4f}"
    )
