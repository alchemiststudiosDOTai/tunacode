"""
Module: tunacode.configuration.models

Configuration for loading model data from models_registry.json.
"""

from tunacode.constants import DEFAULT_CONTEXT_WINDOW

# --- Models.dev Registry Functions ---

MODELS_REGISTRY_FILE_NAME = "models_registry.json"

_models_registry_cache: dict | None = None


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


def load_models_registry() -> dict:
    """Load bundled models.dev registry from JSON file.

    Returns cached data on subsequent calls for performance.
    """
    global _models_registry_cache
    if _models_registry_cache is not None:
        return _models_registry_cache

    import json
    from pathlib import Path

    registry_path = Path(__file__).parent / MODELS_REGISTRY_FILE_NAME
    with open(registry_path) as f:
        _models_registry_cache = json.load(f)
    return _models_registry_cache


def get_cached_models_registry() -> dict | None:
    """Return cached registry data if already loaded."""
    return _models_registry_cache


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
    provider = registry.get(provider_id, {})
    models = provider.get("models", {})
    result = [(m["name"], mid) for mid, m in models.items()]
    return sorted(result, key=lambda x: x[0].lower())


def get_provider_env_var(provider_id: str) -> str:
    """Return the environment variable name for a provider's API key.

    Args:
        provider_id: The provider identifier

    Returns:
        Environment variable name (e.g., "OPENAI_API_KEY")
    """
    registry = get_cached_models_registry()
    if registry is None:
        return f"{provider_id.upper()}_API_KEY"

    provider = registry.get(provider_id, {})
    env_vars = provider.get("env", [])
    if env_vars:
        return env_vars[0]
    return f"{provider_id.upper()}_API_KEY"


def validate_provider_api_key(provider_id: str, user_config: dict) -> tuple[bool, str]:
    """Check if API key exists for provider.

    Args:
        provider_id: The provider identifier (e.g., "openai", "anthropic")
        user_config: User configuration dict containing env keys

    Returns:
        Tuple of (is_valid, env_var_name) - True if key exists and is non-empty
    """
    env_var = get_provider_env_var(provider_id)
    env = user_config.get("env", {})
    api_key = env.get(env_var, "")
    return (bool(api_key and api_key.strip()), env_var)


def get_provider_base_url(provider_id: str) -> str | None:
    """Return the API base URL for a provider.

    Args:
        provider_id: The provider identifier

    Returns:
        Base URL string or None if not specified
    """
    registry = get_cached_models_registry()
    if registry is None:
        return None

    provider = registry.get(provider_id, {})
    return provider.get("api")


def get_model_context_window(model_string: str) -> int:
    """Get context window limit for a model from cached models_registry data.

    Args:
        model_string: Full model identifier (e.g., "openrouter:openai/gpt-4.1")

    Returns:
        Context window size in tokens. Falls back to DEFAULT_CONTEXT_WINDOW
        if registry is not loaded, model not found, or limit not specified.
    """
    registry = get_cached_models_registry()
    if registry is None:
        return DEFAULT_CONTEXT_WINDOW

    try:
        provider_id, model_id = parse_model_string(model_string)
    except ValueError:
        return DEFAULT_CONTEXT_WINDOW

    provider = registry.get(provider_id, {})
    model = provider.get("models", {}).get(model_id, {})
    limit = model.get("limit", {})

    context = limit.get("context")
    if context is None:
        return DEFAULT_CONTEXT_WINDOW

    return context
