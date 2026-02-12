from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from tunacode.types.canonical import UsageMetrics

from tunacode.core.agents import main as agents_main
from tunacode.core.agents.main import _TinyAgentStreamState
from tunacode.core.types.state_structures import RuntimeState, UsageState


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


def test_parse_openrouter_usage_supports_normalized_cache_read() -> None:
    raw = {
        "prompt_tokens": 11,
        "completion_tokens": 9,
        "cacheRead": 4,
    }

    metrics = agents_main._parse_openrouter_usage(raw)

    assert metrics == UsageMetrics(
        prompt_tokens=11,
        completion_tokens=9,
        cached_tokens=4,
        cost=0.0,
    )


def test_parse_openrouter_usage_supports_alchemy_usage_shape() -> None:
    raw = {
        "input": 80,
        "output": 20,
        "cache_read": 12,
        "cost": {
            "input": 0.01,
            "output": 0.02,
            "cache_read": 0.0,
            "cache_write": 0.0,
            "total": 0.03,
        },
    }

    metrics = agents_main._parse_openrouter_usage(raw)

    assert metrics == UsageMetrics(
        prompt_tokens=80,
        completion_tokens=20,
        cached_tokens=12,
        cost=0.03,
    )


def test_parse_openrouter_usage_supports_openrouter_cache_read_input_tokens() -> None:
    raw = {
        "prompt_tokens": 50,
        "completion_tokens": 15,
        "cache_read_input_tokens": 6,
    }

    metrics = agents_main._parse_openrouter_usage(raw)

    assert metrics == UsageMetrics(
        prompt_tokens=50,
        completion_tokens=15,
        cached_tokens=6,
        cost=0.0,
    )


def _build_mock_orchestrator() -> agents_main.RequestOrchestrator:
    """Build a minimal RequestOrchestrator with mock state for unit tests."""
    usage_state = UsageState()
    session = SimpleNamespace(
        usage=usage_state,
        runtime=RuntimeState(),
        conversation=SimpleNamespace(messages=[], max_tokens=200_000),
        task=SimpleNamespace(original_query=""),
        user_config={},
        current_model="test/model",
        _compaction_controller=None,
        _debug_raw_stream_accum="",
    )
    state_manager = SimpleNamespace(session=session)
    return agents_main.RequestOrchestrator(
        message="test",
        model="test/model",
        state_manager=state_manager,
        tool_callback=None,
        streaming_callback=None,
    )


def _build_assistant_message(usage: dict[str, Any]) -> dict[str, Any]:
    return {"role": "assistant", "content": [], "usage": usage}


def test_dedup_guard_prevents_double_counting_same_usage_dict() -> None:
    """Calling _record_usage twice with the same message dict accumulates once."""
    orch = _build_mock_orchestrator()
    stream_state = _TinyAgentStreamState(runtime=RuntimeState(), tool_start_times={})

    usage_dict = {"prompt_tokens": 100, "completion_tokens": 50}
    msg = _build_assistant_message(usage_dict)

    orch._record_usage_from_assistant_message(
        msg, source_event="message_end", stream_state=stream_state
    )
    orch._record_usage_from_assistant_message(
        msg, source_event="turn_end", stream_state=stream_state
    )

    totals = orch.state_manager.session.usage.session_total_usage
    assert totals.prompt_tokens == 100
    assert totals.completion_tokens == 50

    # last_call_usage should always be updated (no dedup)
    last = orch.state_manager.session.usage.last_call_usage
    assert last.prompt_tokens == 100
    assert last.completion_tokens == 50


def test_dedup_guard_accumulates_different_usage_dicts() -> None:
    """Two different message dicts are both accumulated."""
    orch = _build_mock_orchestrator()
    stream_state = _TinyAgentStreamState(runtime=RuntimeState(), tool_start_times={})

    msg_a = _build_assistant_message({"prompt_tokens": 100, "completion_tokens": 50})
    msg_b = _build_assistant_message({"prompt_tokens": 200, "completion_tokens": 75})

    orch._record_usage_from_assistant_message(
        msg_a, source_event="message_end", stream_state=stream_state
    )
    orch._record_usage_from_assistant_message(
        msg_b, source_event="message_end", stream_state=stream_state
    )

    totals = orch.state_manager.session.usage.session_total_usage
    assert totals.prompt_tokens == 300
    assert totals.completion_tokens == 125
