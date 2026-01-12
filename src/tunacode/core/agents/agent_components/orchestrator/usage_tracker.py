"""Token and cost tracking for agent responses."""

from dataclasses import dataclass
from typing import Protocol

from tunacode.configuration.pricing import calculate_cost, get_model_pricing
from tunacode.core.state import SessionState

DEFAULT_TOKEN_COUNT = 0
DEFAULT_COST = 0.0
MIN_TOKEN_COUNT = 0

USAGE_ATTR_REQUEST_TOKENS = "request_tokens"
USAGE_ATTR_RESPONSE_TOKENS = "response_tokens"
USAGE_ATTR_CACHED_TOKENS = "cached_tokens"

SESSION_USAGE_KEY_PROMPT_TOKENS = "prompt_tokens"
SESSION_USAGE_KEY_COMPLETION_TOKENS = "completion_tokens"
SESSION_USAGE_KEY_COST = "cost"


class UsageLike(Protocol):
    """Minimal usage interface extracted from model responses."""

    request_tokens: int | None
    response_tokens: int | None
    cached_tokens: int | None


@dataclass(frozen=True, slots=True)
class UsageUpdate:
    """Normalized usage values for token/cost calculations."""

    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int


def _read_usage_value(usage: UsageLike, attribute: str) -> int:
    raw_value = getattr(usage, attribute, None)
    return int(raw_value or DEFAULT_TOKEN_COUNT)


def _normalize_usage(usage: UsageLike) -> UsageUpdate:
    prompt_tokens = _read_usage_value(usage, USAGE_ATTR_REQUEST_TOKENS)
    completion_tokens = _read_usage_value(usage, USAGE_ATTR_RESPONSE_TOKENS)
    cached_tokens = _read_usage_value(usage, USAGE_ATTR_CACHED_TOKENS)
    return UsageUpdate(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
    )


def update_usage(session: SessionState, usage: UsageLike | None, model_name: str) -> None:
    """Update session usage tracking from model response usage."""
    if not usage:
        return

    normalized_usage = _normalize_usage(usage)
    prompt_tokens = normalized_usage.prompt_tokens
    completion_tokens = normalized_usage.completion_tokens
    cached_tokens = normalized_usage.cached_tokens

    session.last_call_usage[SESSION_USAGE_KEY_PROMPT_TOKENS] = prompt_tokens
    session.last_call_usage[SESSION_USAGE_KEY_COMPLETION_TOKENS] = completion_tokens

    pricing = get_model_pricing(model_name)
    if pricing is None:
        session.last_call_usage[SESSION_USAGE_KEY_COST] = DEFAULT_COST
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
        session.last_call_usage[SESSION_USAGE_KEY_COST] = cost
        session.session_total_usage[SESSION_USAGE_KEY_COST] += cost

    session.session_total_usage[SESSION_USAGE_KEY_PROMPT_TOKENS] += prompt_tokens
    session.session_total_usage[SESSION_USAGE_KEY_COMPLETION_TOKENS] += completion_tokens
