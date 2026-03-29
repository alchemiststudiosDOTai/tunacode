"""Core facade for configuration access."""

from __future__ import annotations

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG  # noqa: F401 (re-export)
from tunacode.configuration.models import (
    ModelPickerEntry as ModelPickerEntry,
)
from tunacode.configuration.models import (
    get_model_context_window as _get_model_context_window,
)
from tunacode.configuration.models import (
    get_model_picker_entries as _get_model_picker_entries,
)
from tunacode.configuration.models import (
    get_models_for_provider as _get_models_for_provider,
)
from tunacode.configuration.models import (
    get_provider_env_var as _get_provider_env_var,
)
from tunacode.configuration.models import (
    get_providers as _get_providers,
)
from tunacode.configuration.models import (
    load_models_registry as _load_models_registry,
)
from tunacode.configuration.models import (
    rank_model_picker_entries as _rank_model_picker_entries,
)
from tunacode.configuration.models import (
    validate_provider_api_key as _validate_provider_api_key,
)
from tunacode.configuration.pricing import (
    format_pricing_display as _format_pricing_display,
)
from tunacode.configuration.pricing import (
    get_model_pricing as _get_model_pricing,
)
from tunacode.configuration.settings import ApplicationSettings  # noqa: F401 (re-export)
from tunacode.types import ModelPricing, ModelsRegistryDocument, UserConfig


def get_models_for_provider(provider_id: str) -> list[tuple[str, str]]:
    """Return (display_name, id) tuples for provider models."""
    return _get_models_for_provider(provider_id)


def get_model_picker_entries() -> list[ModelPickerEntry]:
    """Return flattened provider/model entries for the model picker."""
    return _get_model_picker_entries()


def get_providers() -> list[tuple[str, str]]:
    """Return (display_name, id) tuples for all providers."""
    return _get_providers()


def get_provider_env_var(provider_id: str) -> str:
    """Return the provider API key environment variable name."""
    return _get_provider_env_var(provider_id)


def validate_provider_api_key(provider_id: str, user_config: UserConfig) -> tuple[bool, str]:
    """Check whether a provider API key is configured."""
    return _validate_provider_api_key(provider_id, user_config)


def load_models_registry() -> ModelsRegistryDocument:
    """Load the model registry data (cached after first load)."""
    return _load_models_registry()


def get_model_context_window(model_string: str) -> int:
    """Return the context window size for a model."""
    return _get_model_context_window(model_string)


def rank_model_picker_entries(
    entries: list[ModelPickerEntry],
    *,
    current_model: str,
    recent_models: list[str],
    filter_query: str,
) -> tuple[list[ModelPickerEntry], bool]:
    """Rank picker entries for current/recent-first display."""
    return _rank_model_picker_entries(
        entries,
        current_model=current_model,
        recent_models=recent_models,
        filter_query=filter_query,
    )


def get_model_pricing(model_string: str) -> ModelPricing | None:
    """Return pricing metadata for a model if available."""
    return _get_model_pricing(model_string)


def format_pricing_display(pricing: ModelPricing) -> str:
    """Format pricing for display as input/output cost string."""
    return _format_pricing_display(pricing)
