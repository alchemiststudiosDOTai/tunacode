"""Unit tests for CompactionController outcome contracts."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from tunacode.core.compaction.controller import CompactionController, build_compaction_notice
from tunacode.core.compaction.summarizer import ContextSummarizer
from tunacode.core.compaction.types import (
    COMPACTION_REASON_MISSING_API_KEY,
    COMPACTION_REASON_NO_VALID_BOUNDARY,
    COMPACTION_REASON_SUMMARIZATION_FAILED,
    COMPACTION_REASON_UNSUPPORTED_PROVIDER,
    COMPACTION_STATUS_FAILED,
    COMPACTION_STATUS_SKIPPED,
)
from tunacode.core.session import StateManager

DEFAULT_MAX_TOKENS = 220


def _build_state_manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StateManager:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    state_manager = StateManager()
    state_manager.session.project_id = "project-test"
    state_manager.session.created_at = "2026-02-11T00:00:00+00:00"
    state_manager.session.working_directory = "/tmp"
    state_manager.session.conversation.max_tokens = DEFAULT_MAX_TOKENS
    return state_manager


def _build_compactable_history() -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [{"type": "text", "text": "old"}],
            "timestamp": None,
        },
        {
            "role": "assistant",
            "stop_reason": "complete",
            "content": [{"type": "text", "text": "recent"}],
            "timestamp": None,
        },
    ]


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


@pytest.mark.asyncio
async def test_force_compact_empty_history_returns_no_boundary_skip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    controller = CompactionController(state_manager=state_manager)

    outcome = await controller.force_compact(
        [],
        max_tokens=DEFAULT_MAX_TOKENS,
        signal=None,
    )

    assert outcome.status == COMPACTION_STATUS_SKIPPED
    assert outcome.reason == COMPACTION_REASON_NO_VALID_BOUNDARY
    assert outcome.messages == []


@pytest.mark.asyncio
async def test_force_compact_non_openrouter_provider_without_api_endpoint_returns_unsupported_skip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    state_manager.session.current_model = "azure:gpt-4.1"
    state_manager.session.user_config["env"] = {}

    history = _build_compactable_history()
    _patch_token_estimates(monkeypatch, history, token_counts=[5, 10])

    controller = CompactionController(
        state_manager=state_manager,
        keep_recent_tokens=10,
    )

    outcome = await controller.force_compact(
        history,
        max_tokens=DEFAULT_MAX_TOKENS,
        signal=None,
    )

    assert outcome.status == COMPACTION_STATUS_SKIPPED
    assert outcome.reason == COMPACTION_REASON_UNSUPPORTED_PROVIDER
    assert outcome.detail == "azure"
    assert outcome.messages == history
    assert state_manager.session.compaction is None

    user_notice = build_compaction_notice(outcome)
    assert user_notice is not None
    assert "unsupported summarization provider" in user_notice


@pytest.mark.asyncio
async def test_force_compact_missing_api_key_returns_capability_skip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    state_manager.session.current_model = "openrouter:openai/gpt-4.1"
    state_manager.session.user_config["env"] = {}

    history = _build_compactable_history()
    _patch_token_estimates(monkeypatch, history, token_counts=[5, 10])

    controller = CompactionController(
        state_manager=state_manager,
        keep_recent_tokens=10,
    )

    outcome = await controller.force_compact(
        history,
        max_tokens=DEFAULT_MAX_TOKENS,
        signal=None,
    )

    assert outcome.status == COMPACTION_STATUS_SKIPPED
    assert outcome.reason == COMPACTION_REASON_MISSING_API_KEY
    assert outcome.detail is not None
    assert outcome.messages == history
    assert state_manager.session.compaction is None

    user_notice = build_compaction_notice(outcome)
    assert user_notice is not None
    assert outcome.detail in user_notice


@pytest.mark.asyncio
async def test_force_compact_summary_failure_returns_failed_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)

    history = _build_compactable_history()
    _patch_token_estimates(monkeypatch, history, token_counts=[5, 10])

    async def _raise_summary_failure(_prompt: str, _signal: asyncio.Event | None) -> str:
        raise RuntimeError("summary backend unavailable")

    summarizer = ContextSummarizer(_raise_summary_failure)
    controller = CompactionController(
        state_manager=state_manager,
        summarizer=summarizer,
        keep_recent_tokens=10,
    )

    outcome = await controller.force_compact(
        history,
        max_tokens=DEFAULT_MAX_TOKENS,
        signal=None,
    )

    assert outcome.status == COMPACTION_STATUS_FAILED
    assert outcome.reason == COMPACTION_REASON_SUMMARIZATION_FAILED
    assert outcome.detail is not None
    assert "summary backend unavailable" in outcome.detail
    assert outcome.messages == history
    assert state_manager.session.compaction is None

    user_notice = build_compaction_notice(outcome)
    assert user_notice is not None
