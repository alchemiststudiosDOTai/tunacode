from __future__ import annotations

import pytest

from tunacode.types.canonical import UsageMetrics

from tunacode.core.agents import main as agents_main


def test_parse_canonical_usage_accepts_canonical_usage_payload() -> None:
    raw = {
        "input": 12,
        "output": 34,
        "cache_read": 3,
        "cache_write": 1,
        "total_tokens": 46,
        "cost": {
            "input": 0.01,
            "output": 0.02,
            "cache_read": 0.003,
            "cache_write": 0.001,
            "total": 0.034,
        },
    }

    metrics = agents_main._parse_canonical_usage(raw)

    assert metrics == UsageMetrics.from_dict(raw)


def test_parse_canonical_usage_rejects_missing_usage_payload() -> None:
    with pytest.raises(RuntimeError, match="missing usage payload"):
        agents_main._parse_canonical_usage(None)


def test_parse_canonical_usage_rejects_legacy_usage_payload() -> None:
    legacy_payload = {
        "prompt_tokens": 12,
        "completion_tokens": 34,
        "cached_tokens": 3,
        "cost": 0.02,
    }

    with pytest.raises(RuntimeError, match="usage contract violation"):
        agents_main._parse_canonical_usage(legacy_payload)
