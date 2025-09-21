from __future__ import annotations

from typing import Any, Dict

from tunacode.utils.models_registry import ModelsRegistry


def _minimal_data() -> Dict[str, Any]:
    return {
        "testprov": {
            "name": "Test Provider",
            "env": ["TEST_API_KEY"],
            "doc": "https://example.invalid",
            "models": {
                "m1": {
                    "name": "Model One",
                    "attachment": True,
                    "reasoning": False,
                    "tool_call": True,
                    "temperature": True,
                    "knowledge": "2024-01",
                    "cost": {"input": 1.5, "output": 2.5},
                    "limit": {"context": 32000, "output": 2048},
                },
            },
        }
    }


def test_parse_data_populates_models_and_providers() -> None:
    registry = ModelsRegistry()
    registry._parse_data(_minimal_data())

    # Providers indexed
    assert "testprov" in registry.providers
    provider = registry.providers["testprov"]
    assert provider.name == "Test Provider"
    assert provider.env == ["TEST_API_KEY"]

    # Models indexed by full_id
    assert "testprov:m1" in registry.models
    model = registry.models["testprov:m1"]
    assert model.id == "m1"
    assert model.name == "Model One"
    assert model.provider == "testprov"
    # Capabilities, cost, and limits mapped correctly
    assert model.capabilities.attachment is True
    assert model.capabilities.reasoning is False
    assert model.cost.input == 1.5 and model.cost.output == 2.5
    assert model.limits.context == 32000 and model.limits.output == 2048


def test_format_display_and_matches_search_with_fallback_models() -> None:
    registry = ModelsRegistry()
    # Use deterministic fallback data (no network)
    registry._load_fallback_models()

    # Pick a known fallback model
    mid = "openai:gpt-4"
    assert mid in registry.models
    model = registry.models[mid]

    # full_id and display formatting
    assert model.full_id == mid
    # Includes cost and context summary when include_details=True
    display = model.format_display(include_details=True)
    assert "openai:gpt-4 - GPT-4" in display
    assert "$30.0/60.0 per 1M tokens" in display
    # 128000 -> 128k context in current behavior
    assert "128k context" in display

    # Without details, only id and name
    assert model.format_display(include_details=False) == "openai:gpt-4 - GPT-4"

    # matches_search exact/substring priorities
    assert model.matches_search("gpt-4") == 1.0  # substring in id returns exact-match score
    assert model.matches_search("GPT-4") == 1.0  # case-insensitive
    assert model.matches_search("openai") == 0.8  # provider match


def test_get_model_variants_sorts_by_effective_cost() -> None:
    registry = ModelsRegistry()
    registry._load_fallback_models()

    variants = registry.get_model_variants("gpt-4")
    # Expect at least turbo and base
    ids = [m.full_id for m in variants]
    assert "openai:gpt-4-turbo" in ids
    assert "openai:gpt-4" in ids

    # Sorted by free first, then ascending input cost
    turbo_index = ids.index("openai:gpt-4-turbo")
    base_index = ids.index("openai:gpt-4")
    assert turbo_index < base_index
