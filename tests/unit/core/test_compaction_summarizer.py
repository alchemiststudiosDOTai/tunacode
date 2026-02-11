"""Unit tests for compaction retention boundary policy."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tunacode.core.compaction.summarizer import ContextSummarizer


async def _unused_summary_generator(_prompt: str, _signal: asyncio.Event | None) -> str:
    raise AssertionError("summary generation should not run in boundary tests")


def _patch_token_estimates(
    monkeypatch: pytest.MonkeyPatch,
    messages: list[dict[str, Any]],
    token_counts: list[int],
) -> None:
    if len(messages) != len(token_counts):
        raise AssertionError("messages and token_counts must be the same length")

    token_by_message_identity = {
        id(message): token_count
        for message, token_count in zip(messages, token_counts, strict=True)
    }

    def _fake_estimate_message_tokens(message: object) -> int:
        message_id = id(message)
        if message_id not in token_by_message_identity:
            raise AssertionError(f"Unexpected message identity: {message_id}")
        return token_by_message_identity[message_id]

    monkeypatch.setattr(
        "tunacode.core.compaction.summarizer.estimate_message_tokens",
        _fake_estimate_message_tokens,
    )


def test_retention_boundary_treats_threshold_equality_as_satisfied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Equality contract: retained suffix tokens == threshold keeps current boundary."""

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "old"}],
            "timestamp": None,
        },
        {
            "role": "assistant",
            "stop_reason": "complete",
            "content": [{"type": "text", "text": "recent-a"}],
            "timestamp": None,
        },
        {
            "role": "user",
            "content": [{"type": "text", "text": "recent-b"}],
            "timestamp": None,
        },
    ]
    _patch_token_estimates(monkeypatch, messages, token_counts=[5, 7, 13])

    summarizer = ContextSummarizer(_unused_summary_generator)
    threshold_tokens = 20

    boundary = summarizer.calculate_retention_boundary(messages, threshold_tokens)

    assert boundary == 1


def test_retention_boundary_snaps_to_zero_when_no_valid_boundary_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boundary contracts must never split at invalid assistant positions."""

    messages: list[dict[str, Any]] = [
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "thinking"}],
            "timestamp": None,
        },
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "still thinking"}],
            "timestamp": None,
        },
    ]
    _patch_token_estimates(monkeypatch, messages, token_counts=[2, 8])

    summarizer = ContextSummarizer(_unused_summary_generator)

    boundary = summarizer.calculate_retention_boundary(messages, keep_recent_tokens=5)

    assert boundary == 0


def test_retention_boundary_never_starts_with_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compaction must retain tool call/result pairs atomically."""

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "first"}],
            "timestamp": None,
        },
        {
            "role": "assistant",
            "stop_reason": "tool_calls",
            "content": [
                {
                    "type": "tool_call",
                    "id": "tc-1",
                    "name": "bash",
                    "arguments": {"command": "ls"},
                }
            ],
            "timestamp": None,
        },
        {
            "role": "tool_result",
            "tool_call_id": "tc-1",
            "tool_name": "bash",
            "content": [{"type": "text", "text": "ok"}],
            "timestamp": None,
        },
        {
            "role": "assistant",
            "stop_reason": "complete",
            "content": [{"type": "text", "text": "done"}],
            "timestamp": None,
        },
    ]
    _patch_token_estimates(monkeypatch, messages, token_counts=[1, 1, 6, 4])

    summarizer = ContextSummarizer(_unused_summary_generator)

    boundary = summarizer.calculate_retention_boundary(messages, keep_recent_tokens=10)

    assert boundary == 1
    assert messages[boundary]["role"] != "tool_result"
