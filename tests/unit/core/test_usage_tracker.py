from tunacode.core.agents.agent_components.orchestrator import usage_tracker
from tunacode.core.state import SessionState

PROMPT_TOKENS = 12
COMPLETION_TOKENS = 7
EXPECTED_COST = 0.0


class UsageWithoutCachedTokens:
    def __init__(self, request_tokens: int, response_tokens: int) -> None:
        self.request_tokens = request_tokens
        self.response_tokens = response_tokens


def test_update_usage_handles_missing_cached_tokens(monkeypatch) -> None:
    session = SessionState()
    usage = UsageWithoutCachedTokens(PROMPT_TOKENS, COMPLETION_TOKENS)

    monkeypatch.setattr(usage_tracker, "get_model_pricing", lambda _model: None)

    usage_tracker.update_usage(session, usage, session.current_model)

    usage_state = session.usage
    # Use attribute access on typed UsageMetrics
    assert usage_state.last_call_usage.prompt_tokens == PROMPT_TOKENS
    assert usage_state.last_call_usage.completion_tokens == COMPLETION_TOKENS
    assert usage_state.last_call_usage.cost == EXPECTED_COST
    assert usage_state.session_total_usage.prompt_tokens == PROMPT_TOKENS
    assert usage_state.session_total_usage.completion_tokens == COMPLETION_TOKENS
