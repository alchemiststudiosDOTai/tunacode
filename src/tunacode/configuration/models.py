"""
Module: tunacode.configuration.models

Configuration for loading model data from models_registry.json.
"""

from dataclasses import dataclass
from typing import cast

from tunacode.constants import DEFAULT_CONTEXT_WINDOW, MODEL_PICKER_UNFILTERED_LIMIT
from tunacode.types import (
    ModelsRegistryDocument,
    RegistryModelEntry,
    RegistryProviderEntry,
    UserConfig,
)

from tunacode.infrastructure.cache.caches import models_registry as models_registry_cache

# --- Models.dev Registry Functions ---

MODELS_REGISTRY_FILE_NAME = "models_registry.json"


@dataclass(frozen=True, slots=True)
class ModelPickerEntry:
    """Flattened provider/model metadata used by the model picker."""

    full_model: str
    provider_id: str
    provider_name: str
    model_id: str
    model_name: str


def _build_model_search_text(entry: ModelPickerEntry) -> str:
    return " ".join(
        (
            entry.full_model,
            entry.provider_id,
            entry.provider_name,
            entry.model_id,
            entry.model_name,
        )
    ).lower()


def _matches_model_query(entry: ModelPickerEntry, normalized_query: str) -> bool:
    query_tokens = normalized_query.split()
    if not query_tokens:
        return True

    search_text = _build_model_search_text(entry)
    return all(token in search_text for token in query_tokens)


def parse_model_string(model_string: str) -> tuple[str, str]:
    """Parse 'provider:model_id' into (provider_id, model_id).

    Args:
        model_string: Full model identifier (e.g., "openrouter:openai/gpt-4.1")

    Returns:
        Tuple of (provider_id, model_id)

    Raises:
        ValueError: If model_string doesn't contain a colon separator
    """
    if ":" not in model_string:
        raise ValueError(f"Invalid model string format: {model_string}")
    parts = model_string.split(":", 1)
    return (parts[0], parts[1])


def load_models_registry() -> ModelsRegistryDocument:
    """Load bundled models.dev registry from JSON file.

    Returns cached data on subsequent calls for performance.
    """

    cached = models_registry_cache.get_registry()
    if cached is not None:
        return cached

    import json
    from pathlib import Path

    registry_path = Path(__file__).parent / MODELS_REGISTRY_FILE_NAME
    with open(registry_path, encoding="utf-8") as f:
        registry = json.load(f)

    if not isinstance(registry, dict):
        raise TypeError(f"models registry must be a dict, got {type(registry).__name__}")

    typed_registry = cast(ModelsRegistryDocument, registry)
    models_registry_cache.set_registry(typed_registry)
    return typed_registry


def get_cached_models_registry() -> ModelsRegistryDocument | None:
    """Return cached registry data if already loaded, without loading it."""

    return models_registry_cache.get_registry()


def _get_registry_for_read() -> ModelsRegistryDocument:
    """Return registry data for normal read paths, loading it on demand."""
    cached = get_cached_models_registry()
    if cached is not None:
        return cached
    return load_models_registry()


def _get_provider_entry(
    registry: ModelsRegistryDocument,
    provider_id: str,
) -> RegistryProviderEntry | None:
    """Return the provider entry for a provider id, if present."""
    return registry.get(provider_id)


def _get_model_entry(
    provider: RegistryProviderEntry | None,
    model_id: str,
) -> RegistryModelEntry | None:
    """Return the model entry for a provider/model pair, if present."""
    if provider is None:
        return None
    return provider["models"].get(model_id)


def get_providers() -> list[tuple[str, str]]:
    """Return (display_name, id) tuples for all providers.

    Sorted alphabetically by display name.
    """
    registry = load_models_registry()
    providers = [(p["name"], p["id"]) for p in registry.values()]
    return sorted(providers, key=lambda x: x[0].lower())


def get_models_for_provider(provider_id: str) -> list[tuple[str, str]]:
    """Return (display_name, id) tuples for a provider's models.

    Args:
        provider_id: The provider identifier (e.g., "openai", "anthropic")

    Returns:
        List of (model_name, model_id) tuples, sorted alphabetically.
    """
    registry = load_models_registry()
    provider = _get_provider_entry(registry, provider_id)
    models = provider["models"] if provider is not None else {}
    result = [(m["name"], mid) for mid, m in models.items()]
    return sorted(result, key=lambda x: x[0].lower())


def get_model_picker_entries() -> list[ModelPickerEntry]:
    """Return flattened model picker entries across all providers."""
    registry = load_models_registry()
    entries: list[ModelPickerEntry] = []

    for provider in registry.values():
        provider_id = provider["id"]
        provider_name = provider["name"]
        provider_models = provider.get("models", {})

        for model_id, model in provider_models.items():
            entries.append(
                ModelPickerEntry(
                    full_model=f"{provider_id}:{model_id}",
                    provider_id=provider_id,
                    provider_name=provider_name,
                    model_id=model_id,
                    model_name=model["name"],
                )
            )

    return sorted(
        entries,
        key=lambda entry: (
            entry.model_name.lower(),
            entry.provider_name.lower(),
            entry.model_id.lower(),
        ),
    )


def rank_model_picker_entries(
    entries: list[ModelPickerEntry],
    *,
    current_model: str,
    recent_models: list[str],
    filter_query: str,
    limit: int = MODEL_PICKER_UNFILTERED_LIMIT,
) -> tuple[list[ModelPickerEntry], bool]:
    """Rank model entries for the picker and report unfiltered truncation."""
    normalized_query = filter_query.strip().lower()
    has_query = bool(normalized_query)
    recent_order = {model_name: index for index, model_name in enumerate(recent_models)}
    matching_entries: list[ModelPickerEntry] = []

    for entry in entries:
        if has_query and not _matches_model_query(entry, normalized_query):
            continue
        matching_entries.append(entry)

    matching_entries.sort(
        key=lambda entry: (
            (
                0
                if entry.full_model == current_model
                else 1
                if entry.full_model in recent_order
                else 2
            ),
            recent_order.get(entry.full_model, limit),
            entry.model_name.lower(),
            entry.provider_name.lower(),
            entry.model_id.lower(),
        )
    )

    if has_query:
        return matching_entries, False

    pinned_entries: list[ModelPickerEntry] = []
    general_entries: list[ModelPickerEntry] = []

    for entry in matching_entries:
        if entry.full_model == current_model or entry.full_model in recent_order:
            pinned_entries.append(entry)
            continue
        general_entries.append(entry)

    is_truncated = len(general_entries) > limit
    return pinned_entries + general_entries[:limit], is_truncated


def get_provider_env_var(provider_id: str) -> str:
    """Return the environment variable name for a provider's API key.

    Args:
        provider_id: The provider identifier

    Returns:
        Environment variable name (e.g., "OPENAI_API_KEY")
    """
    registry = _get_registry_for_read()
    provider = _get_provider_entry(registry, provider_id)
    env_vars = provider.get("env", []) if provider is not None else []
    if env_vars:
        return env_vars[0]
    return f"{provider_id.upper().replace('-', '_')}_API_KEY"


def validate_provider_api_key(provider_id: str, user_config: UserConfig) -> tuple[bool, str]:
    """Check if API key exists for provider.

    Checks user config first, then falls back to OS environment variables.

    Args:
        provider_id: The provider identifier (e.g., "openai", "anthropic")
        user_config: User configuration dict containing env keys

    Returns:
        Tuple of (is_valid, env_var_name) - True if key exists and is non-empty
    """
    import os

    env_var = get_provider_env_var(provider_id)
    env = user_config["env"]
    config_key = env.get(env_var, "")
    if config_key and config_key.strip():
        return (True, env_var)
    os_key = os.environ.get(env_var, "")
    return (bool(os_key and os_key.strip()), env_var)


def get_provider_base_url(provider_id: str) -> str | None:
    """Return the API base URL for a provider.

    Args:
        provider_id: The provider identifier

    Returns:
        Base URL string or None if not specified
    """
    registry = _get_registry_for_read()
    provider = _get_provider_entry(registry, provider_id)
    return provider.get("api") if provider is not None else None


def get_provider_alchemy_api(provider_id: str) -> str | None:
    """Return the alchemy API routing identifier for a provider."""
    registry = _get_registry_for_read()
    provider = _get_provider_entry(registry, provider_id)
    if provider is None:
        return None

    alchemy_api = provider.get("alchemy_api")
    if not isinstance(alchemy_api, str):
        return None

    normalized_alchemy_api = alchemy_api.strip()
    if not normalized_alchemy_api:
        return None

    return normalized_alchemy_api


def get_model_context_window(model_string: str) -> int:
    """Get context window limit for a model from models_registry data.

    Args:
        model_string: Full model identifier (e.g., "openrouter:openai/gpt-4.1")

    Returns:
        Context window size in tokens. Falls back to DEFAULT_CONTEXT_WINDOW
        if model is invalid, model not found, or limit not specified.
    """
    try:
        provider_id, model_id = parse_model_string(model_string)
    except ValueError:
        return DEFAULT_CONTEXT_WINDOW

    registry = _get_registry_for_read()
    provider = _get_provider_entry(registry, provider_id)
    model = _get_model_entry(provider, model_id)
    if model is None:
        return DEFAULT_CONTEXT_WINDOW

    limit = model.get("limit")
    if limit is None:
        return DEFAULT_CONTEXT_WINDOW

    context = limit.get("context")
    if context is None:
        return DEFAULT_CONTEXT_WINDOW

    return context
