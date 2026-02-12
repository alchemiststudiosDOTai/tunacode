from __future__ import annotations

import asyncio
import os
from typing import Any, cast

import pytest
from tinyagent.agent_types import AssistantMessage, Context
from tinyagent.alchemy_provider import OpenAICompatModel, stream_alchemy_openai_completions

OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_TEST_MODEL_ID = "openai/gpt-4o-mini"
STREAM_TIMEOUT_SECONDS = 90
OPENROUTER_API_KEY = os.environ.get(OPENROUTER_API_KEY_ENV)
EXPECTED_USAGE_KEYS = frozenset(
    {"input", "output", "cache_read", "cache_write", "total_tokens", "cost"}
)
EXPECTED_COST_KEYS = frozenset({"input", "output", "cache_read", "cache_write", "total"})


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not OPENROUTER_API_KEY,
    reason="Requires OPENROUTER_API_KEY for live alchemy usage contract test",
)
async def test_tinyagent_alchemy_result_includes_canonical_usage_contract() -> None:
    model = OpenAICompatModel(
        provider="openrouter",
        id=OPENROUTER_TEST_MODEL_ID,
        base_url=OPENROUTER_CHAT_COMPLETIONS_URL,
        headers={"X-Title": "tunacode-live-alchemy-usage-contract-test"},
    )
    context = Context(
        system_prompt="Respond with exactly OK.",
        messages=[
            {
                "role": "user",
                "content": [{"type": "text", "text": "Reply with exactly: OK"}],
            }
        ],
        tools=None,
    )

    response = await asyncio.wait_for(
        stream_alchemy_openai_completions(
            model,
            context,
            {"api_key": OPENROUTER_API_KEY},
        ),
        timeout=STREAM_TIMEOUT_SECONDS,
    )

    saw_done_event = False
    async for event in response:
        event_dict = cast(dict[str, Any], event)
        saw_done_event = saw_done_event or event_dict.get("type") == "done"

    final_message = cast(
        AssistantMessage,
        await asyncio.wait_for(response.result(), timeout=STREAM_TIMEOUT_SECONDS),
    )

    assert saw_done_event

    usage_raw = final_message.get("usage")
    assert isinstance(usage_raw, dict)

    missing_usage_keys = EXPECTED_USAGE_KEYS.difference(usage_raw.keys())
    assert not missing_usage_keys

    assert "prompt_tokens" not in usage_raw
    assert "completion_tokens" not in usage_raw
    assert "cacheRead" not in usage_raw

    usage = cast(dict[str, Any], usage_raw)
    for key in ("input", "output", "cache_read", "cache_write", "total_tokens"):
        value = usage.get(key)
        assert isinstance(value, int)
        assert value >= 0

    cost_raw = usage.get("cost")
    assert isinstance(cost_raw, dict)

    missing_cost_keys = EXPECTED_COST_KEYS.difference(cost_raw.keys())
    assert not missing_cost_keys

    cost = cast(dict[str, Any], cost_raw)
    for key in EXPECTED_COST_KEYS:
        value = cost.get(key)
        assert isinstance(value, int | float)
        assert float(value) >= 0.0
