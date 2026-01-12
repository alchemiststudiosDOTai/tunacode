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

    assert session.last_call_usage[usage_tracker.SESSION_USAGE_KEY_PROMPT_TOKENS] == PROMPT_TOKENS
    assert (
        session.last_call_usage[usage_tracker.SESSION_USAGE_KEY_COMPLETION_TOKENS]
        == COMPLETION_TOKENS
    )
    assert session.last_call_usage[usage_tracker.SESSION_USAGE_KEY_COST] == EXPECTED_COST
    assert (
        session.session_total_usage[usage_tracker.SESSION_USAGE_KEY_PROMPT_TOKENS] == PROMPT_TOKENS
    )
    assert (
        session.session_total_usage[usage_tracker.SESSION_USAGE_KEY_COMPLETION_TOKENS]
        == COMPLETION_TOKENS
    )
