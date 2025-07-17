"""Characterization tests for token counting utilities in token_counter.py."""

import pytest

from tunacode.utils import token_counter


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", 0),
        ("abcd", 1),  # 4 chars / 4 = 1 token
        ("abcdefgh", 2),  # 8 chars / 4 = 2 tokens
        ("a" * 100, 25),  # 100 chars / 4 = 25 tokens
        ("hello world", 2),  # 11 chars / 4 = 2.75 -> 2 tokens
        ("    ", 1),  # 4 chars / 4 = 1 token
        ("a" * 3999, 999),  # 3999 chars / 4 = 999.75 -> 999 tokens
        ("a" * 4000, 1000),  # 4000 chars / 4 = 1000 tokens
    ],
)
def test_estimate_tokens_various_lengths(text, expected):
    # Test without model (character-based fallback)
    assert token_counter.estimate_tokens(text) == expected


def test_estimate_tokens_none():
    assert token_counter.estimate_tokens("") == 0


@pytest.mark.parametrize(
    "count,expected",
    [
        (0, "0"),
        (999, "999"),
        (1000, "1,000"),  # Now shows full number with commas
        (1234567, "1,234,567"),  # Full number with commas
    ],
)
def test_format_token_count(count, expected):
    assert token_counter.format_token_count(count) == expected
