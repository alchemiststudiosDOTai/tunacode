"""Characterization tests for token counting utilities in token_counter.py."""

import pytest

from tunacode.utils import token_counter


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", 0),
        ("abcd", 2),
        ("abcdefgh", 3),
        ("a" * 100, 14),
        ("hello world", 3),
        ("    ", 2),
        ("a" * 3999, 502),
        ("a" * 4000, 501),
    ],
)
def test_estimate_tokens_various_lengths(text, expected):
    assert token_counter.estimate_tokens(text) == expected


def test_estimate_tokens_none():
    assert token_counter.estimate_tokens("") == 0


@pytest.mark.parametrize(
    "count,expected",
    [
        (0, "0"),
        (999, "999"),
        (1000, "1k"),
        (1234567, "1234k"),
    ],
)
def test_format_token_count(count, expected):
    assert token_counter.format_token_count(count) == expected
