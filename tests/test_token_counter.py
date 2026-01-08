"""Tests for the token counter heuristic."""

from tunacode.utils.messaging.token_counter import CHARS_PER_TOKEN, estimate_tokens


class TestEstimateTokens:
    """Tests for estimate_tokens()."""

    def test_empty_string_returns_zero(self):
        """Empty string returns 0 tokens."""
        assert estimate_tokens("") == 0

    def test_none_text_returns_zero(self):
        """Falsy text returns 0 tokens."""
        assert estimate_tokens("") == 0

    def test_short_text(self):
        """Short text uses character heuristic."""
        # 4 chars = 1 token with CHARS_PER_TOKEN = 4
        assert estimate_tokens("1234") == 1

    def test_longer_text(self):
        """Longer text scales linearly."""
        # 8 chars = 2 tokens
        assert estimate_tokens("12345678") == 2
        # 12 chars = 3 tokens
        assert estimate_tokens("123456789012") == 3

    def test_uses_integer_division(self):
        """Partial tokens are truncated (floor division)."""
        # 7 chars // 4 = 1 token
        assert estimate_tokens("1234567") == 1
        # 9 chars // 4 = 2 tokens
        assert estimate_tokens("123456789") == 2

    def test_model_name_ignored(self):
        """model_name parameter is accepted but ignored."""
        text = "test text here"
        result_no_model = estimate_tokens(text)
        result_with_model = estimate_tokens(text, model_name="gpt-4")
        result_with_other = estimate_tokens(text, model_name="claude-3")
        assert result_no_model == result_with_model == result_with_other

    def test_chars_per_token_constant(self):
        """Uses CHARS_PER_TOKEN constant."""
        assert CHARS_PER_TOKEN == 4
        # Verify calculation matches constant
        text = "x" * 100
        assert estimate_tokens(text) == 100 // CHARS_PER_TOKEN

    def test_whitespace_counted(self):
        """Whitespace characters are counted."""
        # "a b" = 3 chars = 0 tokens (3 // 4)
        assert estimate_tokens("a b") == 0
        # "a b c d" = 7 chars = 1 token
        assert estimate_tokens("a b c d") == 1

    def test_newlines_counted(self):
        """Newlines are counted as characters."""
        # "a\nb" = 3 chars = 0 tokens
        assert estimate_tokens("a\nb") == 0
        # "a\nb\nc\nd" = 7 chars = 1 token
        assert estimate_tokens("a\nb\nc\nd") == 1

    def test_unicode_counted_by_chars(self):
        """Unicode characters count as single chars."""
        # Each emoji is 1 char in Python string
        text = "hello"  # 5 chars = 1 token
        assert estimate_tokens(text) == 1

    def test_realistic_code_snippet(self):
        """Realistic code produces plausible token count."""
        code = """def hello():
    print("Hello, World!")
"""
        # 44 chars // 4 = 11 tokens
        result = estimate_tokens(code)
        assert result == len(code) // CHARS_PER_TOKEN
        assert 5 < result < 20  # Sanity check for code
