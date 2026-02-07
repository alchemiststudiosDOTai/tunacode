"""Tests for tunacode.configuration.pricing."""

import pytest

from tunacode.configuration.pricing import (
    TOKENS_PER_MILLION,
    calculate_cost,
    format_pricing_display,
    get_model_pricing,
)
from tunacode.types import ModelPricing

from tunacode.infrastructure.cache.caches.models_registry import (
    clear_registry_cache,
    set_registry,
)

SAMPLE_REGISTRY = {
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "models": {
            "gpt-4": {
                "name": "GPT-4",
                "cost": {"input": 30.0, "output": 60.0, "cache_read": 15.0},
            },
            "gpt-3.5": {
                "name": "GPT-3.5",
                "cost": {},
            },
            "no-cost": {
                "name": "No Cost Model",
            },
        },
    },
}


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_registry_cache()
    yield
    clear_registry_cache()


class TestGetModelPricing:
    def test_returns_pricing_for_known_model(self):
        set_registry(SAMPLE_REGISTRY)
        pricing = get_model_pricing("openai:gpt-4")
        assert pricing is not None
        assert pricing.input == 30.0
        assert pricing.output == 60.0
        assert pricing.cached_input == 15.0

    def test_returns_none_when_no_cache(self):
        assert get_model_pricing("openai:gpt-4") is None

    def test_returns_none_for_invalid_model_string(self):
        set_registry(SAMPLE_REGISTRY)
        assert get_model_pricing("no-colon") is None

    def test_returns_none_for_unknown_provider(self):
        set_registry(SAMPLE_REGISTRY)
        assert get_model_pricing("unknown:model") is None

    def test_returns_none_for_unknown_model(self):
        set_registry(SAMPLE_REGISTRY)
        assert get_model_pricing("openai:unknown") is None

    def test_returns_none_for_empty_cost(self):
        set_registry(SAMPLE_REGISTRY)
        assert get_model_pricing("openai:gpt-3.5") is None

    def test_returns_none_for_model_without_cost_key(self):
        set_registry(SAMPLE_REGISTRY)
        assert get_model_pricing("openai:no-cost") is None

    def test_defaults_missing_cost_fields_to_zero(self):
        registry = {
            "prov": {
                "models": {
                    "m1": {
                        "name": "m1",
                        "cost": {"input": 5.0},
                    },
                },
            },
        }
        set_registry(registry)
        pricing = get_model_pricing("prov:m1")
        assert pricing is not None
        assert pricing.input == 5.0
        assert pricing.output == 0.0
        assert pricing.cached_input == 0.0


class TestCalculateCost:
    def test_basic_cost_calculation(self):
        pricing = ModelPricing(input=30.0, output=60.0, cached_input=15.0)
        cost = calculate_cost(
            pricing,
            input_tokens=1_000_000,
            cached_tokens=0,
            output_tokens=1_000_000,
        )
        assert cost == pytest.approx(90.0)

    def test_zero_tokens(self):
        pricing = ModelPricing(input=30.0, output=60.0, cached_input=15.0)
        assert calculate_cost(pricing, 0, 0, 0) == 0.0

    def test_only_cached_tokens(self):
        pricing = ModelPricing(input=30.0, output=60.0, cached_input=15.0)
        cost = calculate_cost(pricing, input_tokens=0, cached_tokens=1_000_000, output_tokens=0)
        assert cost == pytest.approx(15.0)

    def test_mixed_tokens(self):
        pricing = ModelPricing(input=10.0, output=20.0, cached_input=5.0)
        cost = calculate_cost(
            pricing,
            input_tokens=500_000,
            cached_tokens=200_000,
            output_tokens=100_000,
        )
        input_cost = (500_000 * 10.0) / TOKENS_PER_MILLION
        cached_cost = (200_000 * 5.0) / TOKENS_PER_MILLION
        output_cost = (100_000 * 20.0) / TOKENS_PER_MILLION
        expected = input_cost + cached_cost + output_cost
        assert cost == pytest.approx(expected)


class TestFormatPricingDisplay:
    def test_formats_pricing(self):
        pricing = ModelPricing(input=2.0, output=8.0, cached_input=1.0)
        assert format_pricing_display(pricing) == "$2.00/$8.00"

    def test_formats_zero_pricing(self):
        pricing = ModelPricing(input=0.0, output=0.0, cached_input=0.0)
        assert format_pricing_display(pricing) == "$0.00/$0.00"

    def test_formats_large_pricing(self):
        pricing = ModelPricing(input=100.5, output=200.25, cached_input=50.0)
        assert format_pricing_display(pricing) == "$100.50/$200.25"
