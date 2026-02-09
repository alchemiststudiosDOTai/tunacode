from __future__ import annotations

from tunacode.types.canonical import UsageMetrics

from tunacode.core.agents import main as agents_main


def test_parse_openrouter_usage_parses_prompt_and_completion_tokens() -> None:
    raw = {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46}
    metrics = agents_main._parse_openrouter_usage(raw)

    assert metrics == UsageMetrics(
        prompt_tokens=12,
        completion_tokens=34,
        cached_tokens=0,
        cost=0.0,
    )


def test_parse_openrouter_usage_returns_none_for_zero_usage() -> None:
    metrics = agents_main._parse_openrouter_usage({"prompt_tokens": 0, "completion_tokens": 0})
    assert metrics is None


def test_parse_openrouter_usage_supports_camelcase_keys_and_cost() -> None:
    raw = {
        "promptTokens": "10",
        "completionTokens": "5",
        "total_cost": "0.02",
        "promptTokensDetails": {"cachedTokens": 7},
    }

    metrics = agents_main._parse_openrouter_usage(raw)

    assert metrics == UsageMetrics(
        prompt_tokens=10,
        completion_tokens=5,
        cached_tokens=7,
        cost=0.02,
    )
