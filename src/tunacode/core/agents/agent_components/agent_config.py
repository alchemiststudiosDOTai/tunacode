"""Agent configuration and creation utilities."""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from httpx import AsyncClient, HTTPStatusError, Request
from pydantic_ai import Agent

if TYPE_CHECKING:
    from pydantic_ai import Tool
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.retries import AsyncTenacityTransport, RetryConfig, wait_retry_after
from pydantic_ai.settings import ModelSettings
from tenacity import retry_if_exception_type, stop_after_attempt

from tunacode.configuration.limits import get_max_tokens
from tunacode.configuration.models import load_models_registry
from tunacode.configuration.user_config import load_config
from tunacode.constants import ENV_OPENAI_BASE_URL
from tunacode.types import ModelName

from tunacode.tools.bash import bash
from tunacode.tools.glob import glob
from tunacode.tools.grep import grep
from tunacode.tools.list_dir import list_dir
from tunacode.tools.read_file import read_file
from tunacode.tools.submit import submit
from tunacode.tools.update_file import update_file
from tunacode.tools.web_fetch import web_fetch
from tunacode.tools.write_file import write_file

from tunacode.infrastructure.llm_types import PydanticAgent

from tunacode.core.logging import get_logger
from tunacode.core.prompting import resolve_prompt
from tunacode.core.types import SessionStateProtocol, StateManagerProtocol

# Module-level cache for AGENTS.md context
_TUNACODE_CACHE: dict[str, tuple[str, float]] = {}

# Module-level cache for agents to persist across requests
_AGENT_CACHE: dict[ModelName, PydanticAgent] = {}
_AGENT_CACHE_VERSION: dict[ModelName, int] = {}


async def _sleep_with_delay(total_delay: float) -> None:
    """Sleep for a fixed pre-request delay."""
    await asyncio.sleep(total_delay)


def _coerce_request_delay(session: SessionStateProtocol) -> float:
    """Return validated request_delay from session config."""
    settings = session.user_config.get("settings", {})
    request_delay_raw = settings.get("request_delay", 0.0)
    request_delay = float(request_delay_raw)

    if request_delay < 0.0 or request_delay > 60.0:
        raise ValueError(f"request_delay must be between 0.0 and 60.0 seconds, got {request_delay}")

    return request_delay


def _coerce_global_request_timeout(session: SessionStateProtocol) -> float | None:
    """Return validated global_request_timeout from session config, or None if disabled."""
    settings = session.user_config.get("settings", {})
    timeout_raw = settings.get("global_request_timeout", 90.0)
    timeout = float(timeout_raw)

    if timeout < 0.0:
        raise ValueError(f"global_request_timeout must be >= 0.0 seconds, got {timeout}")

    if timeout == 0.0:
        return None

    return timeout


def _coerce_optional_str(value: Any, label: str) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string, got {type(value).__name__}")

    normalized = value.strip()
    if not normalized:
        return None

    return normalized


def _compute_agent_version(settings: dict[str, Any], request_delay: float) -> int:
    """Compute a hash representing agent-defining configuration."""
    return hash(
        (
            str(settings.get("max_retries", 3)),
            str(settings.get("tool_strict_validation", False)),
            str(request_delay),
            str(settings.get("global_request_timeout", 90.0)),
        )
    )


def _build_request_hooks(
    request_delay: float,
) -> dict[str, list[Callable[[Request], Awaitable[None]]]]:
    """Return httpx event hooks enforcing a fixed pre-request delay."""
    if request_delay <= 0:
        # Reason: avoid overhead when no throttling requested
        return {}

    async def _delay_before_request(_: Request) -> None:
        await _sleep_with_delay(request_delay)

    return {"request": [_delay_before_request]}


def clear_all_caches() -> None:
    """Clear all module-level caches. Useful for testing."""
    _TUNACODE_CACHE.clear()
    _AGENT_CACHE.clear()
    _AGENT_CACHE_VERSION.clear()


def invalidate_agent_cache(model: str, state_manager: StateManagerProtocol) -> bool:
    """Invalidate cached agent for a specific model.

    Call this after an abort or timeout to ensure the HTTP client is recreated.
    Clears both module-level and session-level caches.

    Args:
        model: The model name to invalidate
        state_manager: StateManagerProtocol to clear session-level cache

    Returns:
        True if an agent was invalidated, False if not cached.
    """
    logger = get_logger()
    cleared_module = False
    cleared_session = False

    # Clear module-level cache
    if model in _AGENT_CACHE:
        del _AGENT_CACHE[model]
        cleared_module = True
    _AGENT_CACHE_VERSION.pop(model, None)

    # Clear session-level cache
    if model in state_manager.session.agents:
        del state_manager.session.agents[model]
        cleared_session = True
    state_manager.session.agent_versions.pop(model, None)

    invalidated = cleared_module or cleared_session
    if invalidated:
        logger.debug(
            f"Agent cache cleared: model={model}, "
            f"module={cleared_module}, session={cleared_session}"
        )

    return invalidated


def get_agent_tool() -> tuple[type[Agent], type["Tool"]]:
    """Lazy import for Agent and Tool to avoid circular imports."""
    from pydantic_ai import Tool

    return Agent, Tool


def load_system_prompt(base_path: Path, model: str | None = None) -> str:
    """Load the system prompt from a single MD file.

    Local mode is being deleted - only one prompt file needed.

    Args:
        base_path: Base path to the tunacode package
        model: Optional model name (reserved for future use)

    Returns:
        System prompt with dynamic placeholders resolved

    Raises:
        FileNotFoundError: If system_prompt.md does not exist.
    """
    prompt_file = base_path / "prompts" / "system_prompt.md"

    if not prompt_file.exists():
        raise FileNotFoundError(f"Required prompt file not found: {prompt_file}")

    content = prompt_file.read_text(encoding="utf-8")
    return resolve_prompt(content)


def load_tunacode_context() -> str:
    """Load guide file context if it exists with caching.

    Uses guide_file from settings (defaults to AGENTS.md).
    Local mode support removed - no longer loads local_prompt.md.
    """
    logger = get_logger()

    try:
        # Load guide_file from cwd (defaults to AGENTS.md)
        config = load_config()
        guide_file = "AGENTS.md"
        if config and "settings" in config:
            guide_file = config["settings"].get("guide_file", "AGENTS.md")
        tunacode_path = Path.cwd() / guide_file

        cache_key = str(tunacode_path)

        if not tunacode_path.exists():
            return ""

        # Check cache with file modification time
        if cache_key in _TUNACODE_CACHE:
            cached_content, cached_mtime = _TUNACODE_CACHE[cache_key]
            current_mtime = tunacode_path.stat().st_mtime
            if current_mtime == cached_mtime:
                return cached_content

        # Load from file and cache
        tunacode_content = tunacode_path.read_text(encoding="utf-8")
        if tunacode_content.strip():
            result = f"\n\n# Project Context from {guide_file}\n" + tunacode_content
            _TUNACODE_CACHE[cache_key] = (result, tunacode_path.stat().st_mtime)
            return result
        else:
            _TUNACODE_CACHE[cache_key] = ("", tunacode_path.stat().st_mtime)
            return ""

    except FileNotFoundError:
        return ""
    except Exception as e:
        logger.error(f"Unexpected error loading guide file: {e}")
        raise


class _ProviderConfig:
    """Provider configuration from registry."""

    __slots__ = ("api", "env")

    def __init__(self, api: str | None, env: list[str]) -> None:
        self.api = api
        self.env = env


def _get_provider_config_from_registry(provider_name: str) -> _ProviderConfig:
    """Get provider config from models registry.

    Returns config with 'api' (base_url) and 'env' (list of env var names).
    Returns empty config if provider not found.
    """
    registry = load_models_registry()
    provider_data = registry.get(provider_name, {})
    return _ProviderConfig(
        api=provider_data.get("api"),
        env=provider_data.get("env", []),
    )


def _create_model_with_retry(
    model_string: str, http_client: AsyncClient, session: SessionStateProtocol
) -> AnthropicModel | OpenAIChatModel | str:
    """Create a model instance with retry-enabled HTTP client.

    Parses model string in format 'provider:model_name' and creates
    appropriate provider and model instances with the retry-enabled HTTP client.

    Uses models_registry.json for provider configuration (api URL, env vars).
    Only 'anthropic' provider uses AnthropicModel, all others use OpenAI.
    """
    env = session.user_config.get("env", {})
    settings = session.user_config.get("settings", {})

    # Parse model string
    if ":" in model_string:
        provider_name, model_name = model_string.split(":", 1)
    else:
        model_name = model_string
        if model_name.startswith("claude"):
            provider_name = "anthropic"
        elif model_name.startswith(("gpt", "o1", "o3")):
            provider_name = "openai"
        else:
            return model_string

    # Get config from registry
    registry_config = _get_provider_config_from_registry(provider_name)
    env_vars = registry_config.env
    api_key_name = env_vars[0] if env_vars else f"{provider_name.upper()}_API_KEY"
    api_key = env.get(api_key_name)

    # Resolve base_url: user override > registry default
    provider_settings = settings.get("providers", {}).get(provider_name, {})
    base_url = provider_settings.get("base_url") or registry_config.api

    if provider_name == "anthropic":
        anthropic_provider = AnthropicProvider(
            api_key=api_key, base_url=base_url, http_client=http_client
        )
        return AnthropicModel(model_name, provider=anthropic_provider)

    # OpenAI-compatible: also check OPENAI_BASE_URL env var as escape hatch
    env_base_url = _coerce_optional_str(env.get(ENV_OPENAI_BASE_URL), ENV_OPENAI_BASE_URL)
    if env_base_url:
        base_url = env_base_url

    openai_provider = OpenAIProvider(api_key=api_key, base_url=base_url, http_client=http_client)
    return OpenAIChatModel(model_name, provider=openai_provider)


def get_or_create_agent(model: ModelName, state_manager: StateManagerProtocol) -> PydanticAgent:
    """Get existing agent or create new one for the specified model."""
    logger = get_logger()
    request_delay = _coerce_request_delay(state_manager.session)
    settings = state_manager.session.user_config.get("settings", {})
    agent_version = _compute_agent_version(settings, request_delay)

    # Check session-level cache first (for backward compatibility with tests)
    session_agent = state_manager.session.agents.get(model)
    session_version = state_manager.session.agent_versions.get(model)
    if session_agent and session_version == agent_version:
        logger.debug(f"Agent cache hit (session): {model}")
        return cast(PydanticAgent, session_agent)
    if session_agent and session_version != agent_version:
        logger.debug(f"Agent cache invalidated (session version mismatch): {model}")
        del state_manager.session.agents[model]
        state_manager.session.agent_versions.pop(model, None)

    # Check module-level cache
    if model in _AGENT_CACHE:
        # Verify cache is still valid (check for config changes)
        cached_version = _AGENT_CACHE_VERSION.get(model)
        if cached_version == agent_version:
            logger.debug(f"Agent cache hit (module): {model}")
            state_manager.session.agents[model] = _AGENT_CACHE[model]
            state_manager.session.agent_versions[model] = agent_version
            return _AGENT_CACHE[model]
        else:
            logger.debug(f"Agent cache invalidated (config changed): {model}")
            del _AGENT_CACHE[model]
            del _AGENT_CACHE_VERSION[model]

    if model not in _AGENT_CACHE:
        max_retries = settings.get("max_retries", 3)

        # Lazy import Agent and Tool
        Agent, Tool = get_agent_tool()

        # Load system prompt (with optional model-specific template override)
        base_path = Path(__file__).parent.parent.parent.parent
        system_prompt = load_system_prompt(base_path, model=model)

        # Load AGENTS.md context
        system_prompt += load_tunacode_context()

        # Get tool strict validation setting from config (default to False for backward
        # compatibility)
        tool_strict_validation = settings.get("tool_strict_validation", False)

        # Full tool set with detailed descriptions
        tools_list = [
            Tool(bash, max_retries=max_retries, strict=tool_strict_validation),
            Tool(glob, max_retries=max_retries, strict=tool_strict_validation),
            Tool(grep, max_retries=max_retries, strict=tool_strict_validation),
            Tool(list_dir, max_retries=max_retries, strict=tool_strict_validation),
            Tool(read_file, max_retries=max_retries, strict=tool_strict_validation),
            Tool(update_file, max_retries=max_retries, strict=tool_strict_validation),
            Tool(web_fetch, max_retries=max_retries, strict=tool_strict_validation),
            Tool(write_file, max_retries=max_retries, strict=tool_strict_validation),
            # Add submit tool for completion signaling
            Tool(submit, max_retries=max_retries, strict=tool_strict_validation),
        ]

        # Configure HTTP client with retry logic at transport layer
        # This handles retries BEFORE node creation, avoiding pydantic-ai's
        # single-stream-per-node constraint violations
        # https://ai.pydantic.dev/api/retries/#pydantic_ai.retries.wait_retry_after
        transport = AsyncTenacityTransport(
            config=RetryConfig(
                retry=retry_if_exception_type(HTTPStatusError),
                wait=wait_retry_after(max_wait=60),
                stop=stop_after_attempt(max_retries),
                reraise=True,
            ),
            validate_response=lambda r: r.raise_for_status(),
        )

        event_hooks = _build_request_hooks(request_delay)

        # Set HTTP timeout: connect=10s, read=60s, write=30s, pool=5s
        # This prevents hanging forever if provider doesn't respond
        from httpx import Timeout

        http_timeout = Timeout(10.0, read=60.0, write=30.0, pool=5.0)
        http_client = AsyncClient(
            transport=transport, event_hooks=event_hooks, timeout=http_timeout
        )

        # Create model instance with retry-enabled HTTP client
        model_instance = _create_model_with_retry(model, http_client, state_manager.session)

        # Apply max_tokens if configured
        max_tokens = get_max_tokens()
        if max_tokens is not None:
            agent = Agent(
                model=model_instance,
                system_prompt=system_prompt,
                tools=tools_list,
                model_settings=ModelSettings(max_tokens=max_tokens),
            )
        else:
            agent = Agent(
                model=model_instance,
                system_prompt=system_prompt,
                tools=tools_list,
            )

        # Store in both caches
        _AGENT_CACHE[model] = agent
        _AGENT_CACHE_VERSION[model] = agent_version
        state_manager.session.agent_versions[model] = agent_version
        state_manager.session.agents[model] = agent
        logger.info(f"Agent created: {model}")

    return _AGENT_CACHE[model]
