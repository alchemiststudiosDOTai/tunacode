"""Agent configuration and creation utilities."""

import asyncio
import math
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from httpx import AsyncClient, HTTPStatusError, Request
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.retries import AsyncTenacityTransport, RetryConfig, wait_retry_after
from tenacity import retry_if_exception_type, stop_after_attempt

from tunacode.constants import ENV_OPENAI_BASE_URL, SETTINGS_BASE_URL, UI_THINKING_MESSAGE
from tunacode.core.agents.delegation_tools import create_research_codebase_tool
from tunacode.core.prompting import (
    MAIN_TEMPLATE,
    TEMPLATE_OVERRIDES,
    SectionLoader,
    SystemPromptSection,
    compose_prompt,
    resolve_prompt,
)
from tunacode.core.state import StateManager
from tunacode.tools.bash import bash
from tunacode.tools.glob import glob
from tunacode.tools.grep import grep
from tunacode.tools.list_dir import list_dir
from tunacode.tools.read_file import read_file
from tunacode.tools.todo import create_todoclear_tool, create_todoread_tool, create_todowrite_tool
from tunacode.tools.update_file import update_file
from tunacode.tools.web_fetch import web_fetch
from tunacode.tools.write_file import write_file
from tunacode.types import ModelName, PydanticAgent

# Module-level caches for system prompts
_PROMPT_CACHE: dict[str, tuple[str, float]] = {}
_TUNACODE_CACHE: dict[str, tuple[str, float]] = {}

# Module-level cache for agents to persist across requests
_AGENT_CACHE: dict[ModelName, PydanticAgent] = {}
_AGENT_CACHE_VERSION: dict[ModelName, int] = {}

REQUEST_DELAY_MESSAGE_PREFIX = "Respecting request delay"


def _format_request_delay_message(seconds_remaining: float) -> str:
    safe_remaining = max(0.0, seconds_remaining)
    return f"{REQUEST_DELAY_MESSAGE_PREFIX}: {safe_remaining:.1f}s remaining"


async def _publish_delay_message(message: str, state_manager: StateManager) -> None:
    """Best-effort spinner update; UI failures must not block requests."""
    streaming_panel = getattr(state_manager.session, "streaming_panel", None)
    try:
        if streaming_panel:
            if message == UI_THINKING_MESSAGE:
                await streaming_panel.clear_status_message()
            else:
                await streaming_panel.set_status_message(message)
    except Exception:
        pass


async def _sleep_with_countdown(
    total_delay: float, countdown_steps: int, state_manager: StateManager
) -> None:
    """Sleep while surfacing a countdown via the spinner."""
    delay_per_step = total_delay / countdown_steps
    remaining = total_delay
    await _publish_delay_message(_format_request_delay_message(remaining), state_manager)

    for _ in range(countdown_steps):
        await asyncio.sleep(delay_per_step)
        remaining = max(0.0, remaining - delay_per_step)
        await _publish_delay_message(_format_request_delay_message(remaining), state_manager)

    await _publish_delay_message(UI_THINKING_MESSAGE, state_manager)


def _coerce_request_delay(state_manager: StateManager) -> float:
    """Return validated request_delay from config."""
    settings = state_manager.session.user_config.get("settings", {})
    request_delay_raw = settings.get("request_delay", 0.0)
    request_delay = float(request_delay_raw)

    if request_delay < 0.0 or request_delay > 60.0:
        raise ValueError(f"request_delay must be between 0.0 and 60.0 seconds, got {request_delay}")

    return request_delay


def _coerce_global_request_timeout(state_manager: StateManager) -> float | None:
    """Return validated global_request_timeout from config, or None if disabled."""
    settings = state_manager.session.user_config.get("settings", {})
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


def _resolve_base_url_override(
    env_base_url: str | None,
    settings_base_url: str | None,
) -> str | None:
    if env_base_url:
        return env_base_url

    if settings_base_url:
        return settings_base_url

    return None


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
    request_delay: float, state_manager: StateManager
) -> dict[str, list[Callable[[Request], Awaitable[None]]]]:
    """Return httpx event hooks enforcing a fixed pre-request delay."""
    if request_delay <= 0:
        # Reason: avoid overhead when no throttling requested
        return {}

    countdown_steps = max(int(math.ceil(request_delay)), 1)

    async def _delay_before_request(_: Request) -> None:
        await _sleep_with_countdown(request_delay, countdown_steps, state_manager)

    return {"request": [_delay_before_request]}


def clear_all_caches():
    """Clear all module-level caches. Useful for testing."""
    _PROMPT_CACHE.clear()
    _TUNACODE_CACHE.clear()
    _AGENT_CACHE.clear()
    _AGENT_CACHE_VERSION.clear()


def get_agent_tool():
    """Lazy import for Agent and Tool to avoid circular imports."""
    from pydantic_ai import Tool

    return Agent, Tool


def _read_prompt_from_path(prompt_path: Path) -> str:
    """Return prompt content from disk, leveraging the cache when possible."""
    cache_key = str(prompt_path)

    try:
        current_mtime = prompt_path.stat().st_mtime
    except FileNotFoundError as error:
        raise FileNotFoundError from error

    if cache_key in _PROMPT_CACHE:
        cached_content, cached_mtime = _PROMPT_CACHE[cache_key]
        if current_mtime == cached_mtime:
            return cached_content

    try:
        content = prompt_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise FileNotFoundError from error

    _PROMPT_CACHE[cache_key] = (content, current_mtime)
    return content


def load_system_prompt(base_path: Path, model: str | None = None) -> str:
    """Load the system prompt with section-based composition.

    Loads individual section files from prompts/sections/ and composes them
    using the template system.

    Args:
        base_path: Base path to the tunacode package
        model: Optional model name for template overrides

    Raises:
        FileNotFoundError: If prompts/sections/ does not exist.
    """
    prompts_dir = base_path / "prompts"
    sections_dir = prompts_dir / "sections"

    if not sections_dir.exists():
        raise FileNotFoundError(
            f"Required sections directory not found: {sections_dir}. "
            "The prompts/sections/ directory must exist."
        )

    loader = SectionLoader(sections_dir)
    sections = {s.value: loader.load_section(s) for s in SystemPromptSection}

    # Get template (model-specific override or default)
    template = TEMPLATE_OVERRIDES.get(model, MAIN_TEMPLATE) if model else MAIN_TEMPLATE

    # Compose sections into template, then resolve dynamic placeholders
    prompt = compose_prompt(template, sections)
    return resolve_prompt(prompt)


def load_tunacode_context() -> str:
    """Load AGENTS.md context if it exists with caching."""
    try:
        tunacode_path = Path.cwd() / "AGENTS.md"
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
            result = "\n\n# Project Context from AGENTS.md\n" + tunacode_content
            _TUNACODE_CACHE[cache_key] = (result, tunacode_path.stat().st_mtime)
            return result
        else:
            _TUNACODE_CACHE[cache_key] = ("", tunacode_path.stat().st_mtime)
            return ""

    except Exception:
        return ""


def _create_model_with_retry(
    model_string: str, http_client: AsyncClient, state_manager: StateManager
):
    """Create a model instance with retry-enabled HTTP client.

    Parses model string in format 'provider:model_name' and creates
    appropriate provider and model instances with the retry-enabled HTTP client.
    """
    # Extract environment config
    env = state_manager.session.user_config.get("env", {})

    settings = state_manager.session.user_config.get("settings", {})
    env_base_url_raw = env.get(ENV_OPENAI_BASE_URL)
    settings_base_url_raw = settings.get(SETTINGS_BASE_URL)
    env_base_url = _coerce_optional_str(env_base_url_raw, ENV_OPENAI_BASE_URL)
    settings_base_url = _coerce_optional_str(settings_base_url_raw, SETTINGS_BASE_URL)
    base_url_override = _resolve_base_url_override(env_base_url, settings_base_url)

    # Provider configuration: API key names and base URLs
    PROVIDER_CONFIG = {
        "anthropic": {"api_key_name": "ANTHROPIC_API_KEY", "base_url": None},
        "openai": {"api_key_name": "OPENAI_API_KEY", "base_url": None},
        "openrouter": {
            "api_key_name": "OPENROUTER_API_KEY",
            "base_url": "https://openrouter.ai/api/v1",
        },
        "azure": {
            "api_key_name": "AZURE_OPENAI_API_KEY",
            "base_url": env.get("AZURE_OPENAI_ENDPOINT"),
        },
        "deepseek": {"api_key_name": "DEEPSEEK_API_KEY", "base_url": None},
        "cerebras": {
            "api_key_name": "CEREBRAS_API_KEY",
            "base_url": "https://api.cerebras.ai/v1",
        },
    }

    # Parse model string
    if ":" in model_string:
        provider_name, model_name = model_string.split(":", 1)
    else:
        # Auto-detect provider from model name
        model_name = model_string
        if model_name.startswith("claude"):
            provider_name = "anthropic"
        elif model_name.startswith(("gpt", "o1", "o3")):
            provider_name = "openai"
        else:
            # Default to treating as model string (pydantic-ai will auto-detect)
            return model_string

    # Create provider with api_key + base_url + http_client
    if provider_name == "anthropic":
        api_key = env.get("ANTHROPIC_API_KEY")
        provider = AnthropicProvider(api_key=api_key, http_client=http_client)
        return AnthropicModel(model_name, provider=provider)
    elif provider_name in ("openai", "openrouter", "azure", "deepseek", "cerebras"):
        # OpenAI-compatible providers all use OpenAIChatModel
        config = PROVIDER_CONFIG.get(provider_name, {})
        api_key_name = config.get("api_key_name")
        api_key = env.get(api_key_name) if api_key_name else None
        base_url = config.get("base_url")
        if base_url is None and provider_name != "azure":
            base_url = base_url_override
        provider = OpenAIProvider(api_key=api_key, base_url=base_url, http_client=http_client)
        return OpenAIChatModel(model_name, provider=provider)
    else:
        # Unsupported provider, return string and let pydantic-ai handle it
        # (won't have retry support but won't break)
        return model_string


def get_or_create_agent(model: ModelName, state_manager: StateManager) -> PydanticAgent:
    """Get existing agent or create new one for the specified model."""
    request_delay = _coerce_request_delay(state_manager)
    settings = state_manager.session.user_config.get("settings", {})
    agent_version = _compute_agent_version(settings, request_delay)

    # Check session-level cache first (for backward compatibility with tests)
    session_agent = state_manager.session.agents.get(model)
    session_version = state_manager.session.agent_versions.get(model)
    if session_agent and session_version == agent_version:
        return session_agent
    if session_agent and session_version != agent_version:
        del state_manager.session.agents[model]
        state_manager.session.agent_versions.pop(model, None)

    # Check module-level cache
    if model in _AGENT_CACHE:
        # Verify cache is still valid (check for config changes)
        cached_version = _AGENT_CACHE_VERSION.get(model)
        if cached_version == agent_version:
            state_manager.session.agents[model] = _AGENT_CACHE[model]
            state_manager.session.agent_versions[model] = agent_version
            return _AGENT_CACHE[model]
        else:
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

        # Create tool list
        tools_list = [
            Tool(bash, max_retries=max_retries, strict=tool_strict_validation),
            Tool(glob, max_retries=max_retries, strict=tool_strict_validation),
            Tool(grep, max_retries=max_retries, strict=tool_strict_validation),
            Tool(list_dir, max_retries=max_retries, strict=tool_strict_validation),
            Tool(read_file, max_retries=max_retries, strict=tool_strict_validation),
            Tool(update_file, max_retries=max_retries, strict=tool_strict_validation),
            Tool(web_fetch, max_retries=max_retries, strict=tool_strict_validation),
            Tool(write_file, max_retries=max_retries, strict=tool_strict_validation),
        ]

        # Add delegation tool (multi-agent pattern)
        research_codebase = create_research_codebase_tool(state_manager)
        tools_list.append(
            Tool(research_codebase, max_retries=max_retries, strict=tool_strict_validation)
        )

        # Add todo tools (task tracking)
        todowrite = create_todowrite_tool(state_manager)
        todoread = create_todoread_tool(state_manager)
        todoclear = create_todoclear_tool(state_manager)
        tools_list.append(Tool(todowrite, max_retries=max_retries, strict=tool_strict_validation))
        tools_list.append(Tool(todoread, max_retries=max_retries, strict=tool_strict_validation))
        tools_list.append(Tool(todoclear, max_retries=max_retries, strict=tool_strict_validation))

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
        event_hooks = _build_request_hooks(request_delay, state_manager)
        http_client = AsyncClient(transport=transport, event_hooks=event_hooks)

        # Create model instance with retry-enabled HTTP client
        model_instance = _create_model_with_retry(model, http_client, state_manager)

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

    return _AGENT_CACHE[model]
