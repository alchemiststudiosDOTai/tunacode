"""Tests for recent models tracking."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tunacode.configuration.user_config import _MAX_RECENT_MODELS, track_recent_model


def _make_state_manager(recent: list[str] | None = None) -> MagicMock:
    """Create a minimal state-manager mock with a user_config dict."""
    sm = MagicMock()
    sm.session.user_config = {"recent_models": list(recent) if recent else []}
    return sm


class TestTrackRecentModel:
    def test_adds_model_to_empty_list(self) -> None:
        sm = _make_state_manager()
        track_recent_model("openai:gpt-4o", sm)
        assert sm.session.user_config["recent_models"] == ["openai:gpt-4o"]

    def test_most_recent_first(self) -> None:
        sm = _make_state_manager(["openai:gpt-4o"])
        track_recent_model("anthropic:claude-3.5-sonnet", sm)
        assert sm.session.user_config["recent_models"][0] == "anthropic:claude-3.5-sonnet"
        assert sm.session.user_config["recent_models"][1] == "openai:gpt-4o"

    def test_duplicate_moves_to_front(self) -> None:
        sm = _make_state_manager(["a:m1", "a:m2", "a:m3"])
        track_recent_model("a:m3", sm)
        assert sm.session.user_config["recent_models"] == ["a:m3", "a:m1", "a:m2"]

    def test_caps_at_max(self) -> None:
        existing = [f"p:model-{i}" for i in range(_MAX_RECENT_MODELS)]
        sm = _make_state_manager(existing)
        track_recent_model("p:brand-new", sm)
        result = sm.session.user_config["recent_models"]
        assert len(result) == _MAX_RECENT_MODELS
        assert result[0] == "p:brand-new"
        assert f"p:model-{_MAX_RECENT_MODELS - 1}" not in result

    def test_handles_missing_key(self) -> None:
        sm = MagicMock()
        sm.session.user_config = {}
        track_recent_model("openai:gpt-4o", sm)
        assert sm.session.user_config["recent_models"] == ["openai:gpt-4o"]
