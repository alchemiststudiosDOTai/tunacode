"""Characterization tests for edge cases across file, git, and token utilities."""

import sys

import pytest

from tunacode.utils import file_utils, token_counter


def test_dotdict_non_string_keys():
    d = file_utils.DotDict({1: "one"})
    assert d[1] == "one"
    d[2] = "two"
    assert d[2] == "two"


def test_dotdict_nested_access():
    d = file_utils.DotDict({"outer": file_utils.DotDict({"inner": 42})})
    assert d.outer.inner == 42


def test_capture_stdout_with_exception():
    original_stdout = sys.stdout
    try:
        with file_utils.capture_stdout():
            print("before error")
            raise ValueError("fail!")
    except ValueError:
        pass
    # Current behavior: stdout is restored to what it was before capture
    assert sys.stdout is original_stdout


@pytest.mark.parametrize(
    "text,expected",
    [
        ("你好世界", 1),  # 4 chars / 4 = 1 token
        ("😀" * 8, 2),  # 8 chars / 4 = 2 tokens
    ],
)
def test_estimate_tokens_unicode(text, expected):
    assert token_counter.estimate_tokens(text) == expected


def test_format_token_count_negative():
    # Current behavior: no comma formatting for negative numbers
    assert token_counter.format_token_count(-1000) == "-1000"


def test_format_token_count_large():
    assert token_counter.format_token_count(10**9) == "1,000,000,000"
