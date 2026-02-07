"""Tests for tunacode.configuration.models."""

import copy
import json
from unittest.mock import mock_open, patch

import pytest

from tunacode.configuration import models
from tunacode.constants import DEFAULT_CONTEXT_WINDOW

from tunacode.infrastructure.cache.caches.models_registry import (
    clear_registry_cache,
    set_registry,
)


class TestParseModelString:
    def test_valid_provider_model(self):
        assert models.parse_model_string("openai:gpt-4") == ("openai", "gpt-4")

    def test_valid_with_slash_in_model(self):
        assert models.parse_model_string("openrouter:openai/gpt-4.1") == (
            "openrouter",
            "openai/gpt-4.1",
        )

    def test_multiple_colons_splits_once(self):
        assert models.parse_model_string("a:b:c") == ("a", "b:c")

    def test_missing_colon_raises(self):
        with pytest.raises(ValueError, match="Invalid model string format"):
            models.parse_model_string("no-colon-here")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Invalid model string format"):
            models.parse_model_string("")

    def test_colon_only(self):
        with pytest.raises(ValueError, match="Invalid model string format"):
            models.parse_model_string(":")

    def test_whitespace_no_colon_raises(self):
        with pytest.raises(ValueError, match="Invalid model string format"):
            models.parse_model_string("   ")


SAMPLE_REGISTRY = {
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "env": ["OPENAI_API_KEY"],
        "api": "https://api.openai.com/v1",
        "models": {
            "gpt-4": {
                "name": "GPT-4",
                "limit": {"context": 8192},
                "cost": {"input": 30.0, "output": 60.0, "cache_read": 15.0},
            },
        },
    },
    "anthropic": {
        "id": "anthropic",
        "name": "Anthropic",
        "env": ["ANTHROPIC_API_KEY"],
        "models": {},
    },
}


@pytest.fixture(autouse=True)
def _clear_registry_cache():
    clear_registry_cache()
    yield
    clear_registry_cache()


class TestLoadModelsRegistry:
    def test_loads_json_from_file(self):
        json_data = json.dumps(SAMPLE_REGISTRY)
        with patch("builtins.open", mock_open(read_data=json_data)):
            result = models.load_models_registry()
            assert isinstance(result, dict)
            assert "openai" in result

    def test_caches_on_subsequent_calls(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        result = models.load_models_registry()
        assert result == SAMPLE_REGISTRY

    def test_non_dict_raises_type_error(self):
        json_data = json.dumps([1, 2])
        with (
            patch("builtins.open", mock_open(read_data=json_data)),
            pytest.raises(TypeError, match="models registry must be a dict"),
        ):
            models.load_models_registry()

    def test_get_cached_returns_none_when_not_loaded(self):
        assert models.get_cached_models_registry() is None

    def test_get_cached_returns_cache_when_loaded(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        assert models.get_cached_models_registry() == SAMPLE_REGISTRY


class TestGetProviders:
    def test_returns_sorted_providers(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        providers = models.get_providers()
        names = [name for name, _ in providers]
        assert names == sorted(names, key=str.lower)

    def test_returns_name_id_tuples(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        providers = models.get_providers()
        assert ("Anthropic", "anthropic") in providers
        assert ("OpenAI", "openai") in providers


class TestGetModelsForProvider:
    def test_returns_models_for_known_provider(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        result = models.get_models_for_provider("openai")
        assert ("GPT-4", "gpt-4") in result

    def test_returns_empty_for_unknown_provider(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        assert models.get_models_for_provider("nonexistent") == []

    def test_returns_empty_for_provider_with_no_models(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        assert models.get_models_for_provider("anthropic") == []


class TestGetProviderEnvVar:
    def test_returns_env_from_registry(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        assert models.get_provider_env_var("openai") == "OPENAI_API_KEY"

    def test_falls_back_to_uppercase_convention(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        assert models.get_provider_env_var("unknown") == "UNKNOWN_API_KEY"

    def test_falls_back_when_no_cache(self):
        assert models.get_provider_env_var("openai") == "OPENAI_API_KEY"


class TestValidateProviderApiKey:
    def test_valid_key(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        config = {"env": {"OPENAI_API_KEY": "sk-abc123"}}
        valid, env_var = models.validate_provider_api_key("openai", config)
        assert valid is True
        assert env_var == "OPENAI_API_KEY"

    def test_empty_key_is_invalid(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        config = {"env": {"OPENAI_API_KEY": ""}}
        valid, _ = models.validate_provider_api_key("openai", config)
        assert valid is False

    def test_whitespace_only_key_is_invalid(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        config = {"env": {"OPENAI_API_KEY": "   "}}
        valid, _ = models.validate_provider_api_key("openai", config)
        assert valid is False

    def test_missing_env_section(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        valid, _ = models.validate_provider_api_key("openai", {})
        assert valid is False


class TestGetProviderBaseUrl:
    def test_returns_url_from_registry(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        assert models.get_provider_base_url("openai") == "https://api.openai.com/v1"

    def test_returns_none_for_unknown(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        assert models.get_provider_base_url("unknown") is None

    def test_returns_none_when_no_cache(self):
        assert models.get_provider_base_url("openai") is None

    def test_returns_none_for_provider_without_api(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        assert models.get_provider_base_url("anthropic") is None


class TestGetModelContextWindow:
    def test_returns_context_from_registry(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        assert models.get_model_context_window("openai:gpt-4") == 8192

    def test_falls_back_when_no_cache(self):
        assert models.get_model_context_window("openai:gpt-4") == DEFAULT_CONTEXT_WINDOW

    def test_falls_back_for_unknown_model(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        assert models.get_model_context_window("openai:unknown") == DEFAULT_CONTEXT_WINDOW

    def test_falls_back_for_invalid_model_string(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        assert models.get_model_context_window("no-colon") == DEFAULT_CONTEXT_WINDOW

    def test_falls_back_for_unknown_provider(self):
        set_registry(copy.deepcopy(SAMPLE_REGISTRY))
        assert models.get_model_context_window("unknown:model") == DEFAULT_CONTEXT_WINDOW
