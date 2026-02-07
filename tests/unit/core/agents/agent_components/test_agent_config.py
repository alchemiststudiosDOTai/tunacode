"""Tests for pure helper functions in tunacode.core.agents.agent_components.agent_config."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from tunacode.infrastructure.cache import clear_all, get_cache
from tunacode.infrastructure.cache.caches import tunacode_context as context_cache
from tunacode.infrastructure.cache.caches.agents import AGENTS_CACHE_NAME
from tunacode.infrastructure.cache.caches.tunacode_context import (
    TUNACODE_CONTEXT_CACHE_NAME,
)

from tunacode.core.agents.agent_components.agent_config import (
    REQUEST_HOOK_KEY,
    RESPONSE_HOOK_KEY,
    _build_event_hooks,
    _build_request_delay_hooks,
    _build_response_hooks,
    _coerce_global_request_timeout,
    _coerce_optional_str,
    _coerce_request_delay,
    _compute_agent_version,
    _get_provider_config_from_registry,
    _ProviderConfig,
    load_system_prompt,
)


@pytest.fixture(autouse=True)
def _clear_caches() -> Generator[None, None, None]:
    clear_all()
    yield
    clear_all()


def _make_session(settings: dict | None = None) -> MagicMock:
    session = MagicMock()
    user_config = {"settings": settings or {}}
    session.user_config = user_config
    return session


class TestCoerceRequestDelay:
    def test_default_zero(self):
        assert _coerce_request_delay(_make_session()) == 0.0

    def test_valid_delay(self):
        assert _coerce_request_delay(_make_session({"request_delay": 1.5})) == 1.5

    def test_negative_raises(self):
        with pytest.raises(ValueError, match=r"between 0\.0 and 60\.0"):
            _coerce_request_delay(_make_session({"request_delay": -1.0}))

    def test_too_high_raises(self):
        with pytest.raises(ValueError, match=r"between 0\.0 and 60\.0"):
            _coerce_request_delay(_make_session({"request_delay": 100.0}))

    def test_boundary_values(self):
        assert _coerce_request_delay(_make_session({"request_delay": 0.0})) == 0.0
        assert _coerce_request_delay(_make_session({"request_delay": 60.0})) == 60.0


class TestCoerceGlobalRequestTimeout:
    def test_default_value(self):
        result = _coerce_global_request_timeout(_make_session())
        assert result == 90.0

    def test_custom_value(self):
        result = _coerce_global_request_timeout(_make_session({"global_request_timeout": 120.0}))
        assert result == 120.0

    def test_zero_returns_none(self):
        result = _coerce_global_request_timeout(_make_session({"global_request_timeout": 0.0}))
        assert result is None

    def test_negative_raises(self):
        with pytest.raises(ValueError, match=r">= 0\.0"):
            _coerce_global_request_timeout(_make_session({"global_request_timeout": -1.0}))


class TestCoerceOptionalStr:
    def test_none_returns_none(self):
        assert _coerce_optional_str(None, "label") is None

    def test_non_string_raises(self):
        with pytest.raises(ValueError, match="must be a string"):
            _coerce_optional_str(123, "label")

    def test_empty_string_returns_none(self):
        assert _coerce_optional_str("", "label") is None

    def test_whitespace_only_returns_none(self):
        assert _coerce_optional_str("   ", "label") is None

    def test_valid_string(self):
        assert _coerce_optional_str("  value  ", "label") == "value"


class TestComputeAgentVersion:
    def test_deterministic(self):
        settings = {"max_retries": 3}
        v1 = _compute_agent_version(settings, 0.0)
        v2 = _compute_agent_version(settings, 0.0)
        assert v1 == v2

    def test_different_settings_different_version(self):
        v1 = _compute_agent_version({"max_retries": 3}, 0.0)
        v2 = _compute_agent_version({"max_retries": 5}, 0.0)
        assert v1 != v2

    def test_different_delay_different_version(self):
        v1 = _compute_agent_version({}, 0.0)
        v2 = _compute_agent_version({}, 1.0)
        assert v1 != v2


class TestBuildRequestDelayHooks:
    def test_no_delay_returns_empty(self):
        assert _build_request_delay_hooks(0.0) == []

    def test_negative_delay_returns_empty(self):
        assert _build_request_delay_hooks(-1.0) == []

    def test_positive_delay_returns_hook(self):
        hooks = _build_request_delay_hooks(1.0)
        assert len(hooks) == 1
        assert callable(hooks[0])


class TestBuildResponseHooks:
    def test_returns_hooks(self):
        hooks = _build_response_hooks()
        assert len(hooks) == 1
        assert callable(hooks[0])


class TestBuildEventHooks:
    def test_returns_dict_with_keys(self):
        hooks = _build_event_hooks(0.0)
        assert REQUEST_HOOK_KEY in hooks
        assert RESPONSE_HOOK_KEY in hooks

    def test_no_delay_empty_request_hooks(self):
        hooks = _build_event_hooks(0.0)
        assert hooks[REQUEST_HOOK_KEY] == []

    def test_with_delay_has_request_hook(self):
        hooks = _build_event_hooks(1.0)
        assert len(hooks[REQUEST_HOOK_KEY]) == 1


class TestClearAllCaches:
    def test_clears_caches(self, tmp_path):
        agent_cache = get_cache(AGENTS_CACHE_NAME)
        agent_cache.set("test-model", MagicMock())
        agent_cache.set_metadata("test-model", 1)

        context_file = tmp_path / "test.md"
        context_file.write_text("test context")
        context_cache.get_context(context_file)

        assert agent_cache.get("test-model") is not None
        context_raw = get_cache(TUNACODE_CONTEXT_CACHE_NAME)
        assert context_raw.get(context_file.resolve()) is not None

        clear_all()

        assert agent_cache.get("test-model") is None
        assert context_raw.get(context_file.resolve()) is None


class TestLoadSystemPrompt:
    def test_loads_from_file(self, tmp_path):
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        prompt_file = prompt_dir / "system_prompt.md"
        prompt_file.write_text("You are a helpful agent.")

        result = load_system_prompt(tmp_path)
        assert result == "You are a helpful agent."

    def test_raises_for_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_system_prompt(tmp_path)


class TestProviderConfig:
    def test_attributes(self):
        config = _ProviderConfig(api="https://api.example.com", env=["API_KEY"])
        assert config.api == "https://api.example.com"
        assert config.env == ["API_KEY"]

    def test_none_api(self):
        config = _ProviderConfig(api=None, env=[])
        assert config.api is None
        assert config.env == []


class TestGetProviderConfigFromRegistry:
    def test_known_provider(self):
        registry = {
            "openai": {
                "api": "https://api.openai.com/v1",
                "env": ["OPENAI_API_KEY"],
            }
        }
        with patch(
            "tunacode.core.agents.agent_components.agent_config.load_models_registry",
            return_value=registry,
        ):
            config = _get_provider_config_from_registry("openai")
            assert config.api == "https://api.openai.com/v1"
            assert config.env == ["OPENAI_API_KEY"]

    def test_unknown_provider(self):
        with patch(
            "tunacode.core.agents.agent_components.agent_config.load_models_registry",
            return_value={},
        ):
            config = _get_provider_config_from_registry("unknown")
            assert config.api is None
            assert config.env == []
