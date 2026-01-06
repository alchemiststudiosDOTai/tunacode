"""Tests for token counting heuristic."""

from tunacode.utils.messaging.token_counter import estimate_tokens


class TestEstimateTokens:
    def test_empty_string_returns_zero(self):
        assert estimate_tokens("") == 0

    def test_none_returns_zero(self):
        assert estimate_tokens(None) == 0

    def test_short_string(self):
        # 5 chars // 4 = 1
        assert estimate_tokens("hello") == 1

    def test_longer_string(self):
        # 100 chars // 4 = 25
        assert estimate_tokens("a" * 100) == 25

    def test_model_name_ignored(self):
        # model_name param kept for API compat but unused
        assert estimate_tokens("hello", "anthropic:claude-3") == 1
        assert estimate_tokens("hello", "openai:gpt-4") == 1
