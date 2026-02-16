"""Agent configuration and creation utilities.

Phase 3/4 migration note:

This module now constructs a ``tinyagent.Agent`` configured for TunaCode.
We intentionally do **not** preserve the pydantic-ai agent construction logic.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

from tinyagent import Agent, AgentOptions
from tinyagent.agent_types import AgentMessage, AgentTool
from tinyagent.alchemy_provider import OpenAICompatModel, stream_alchemy_openai_completions

from tunacode.configuration.limits import get_max_tokens
from tunacode.configuration.models import (
    get_provider_base_url,
    get_provider_env_var,
    load_models_registry,
    parse_model_string,
)
from tunacode.configuration.user_config import load_config
from tunacode.constants import ENV_OPENAI_BASE_URL
from tunacode.types import ModelName

from tunacode.tools.bash import bash
from tunacode.tools.decorators import to_tinyagent_tool
from tunacode.tools.glob import glob
from tunacode.tools.grep import grep
from tunacode.tools.list_dir import list_dir
from tunacode.tools.read_file import read_file
from tunacode.tools.update_file import update_file
from tunacode.tools.web_fetch import web_fetch
from tunacode.tools.write_file import write_file

from tunacode.infrastructure.cache.caches import agents as agents_cache
from tunacode.infrastructure.cache.caches import tunacode_context as context_cache

from tunacode.core.compaction.controller import get_or_create_compaction_controller
from tunacode.core.logging import get_logger
from tunacode.core.types import SessionStateProtocol, StateManagerProtocol

ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
OPENAI_CHAT_COMPLETIONS_PATH = "/chat/completions"
OPENROUTER_PROVIDER_ID = "openrouter"


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


def _compute_agent_version(
    settings: dict[str, Any],
    request_delay: float,
    *,
    max_tokens: int | None,
) -> int:
    """Compute a hash representing agent-defining configuration."""

    return hash(
        (
            str(settings.get("max_retries", 3)),
            str(settings.get("tool_strict_validation", False)),
            str(request_delay),
            str(settings.get("global_request_timeout", 90.0)),
            str(max_tokens),
        )
    )


def invalidate_agent_cache(model: str, state_manager: StateManagerProtocol) -> bool:
    """Invalidate cached agent for a specific model.

    Call this after timeout, model switches, or explicit recovery after failed requests.
    the Agent (and any underlying provider client cache).

    Clears both module-level and session-level caches.

    Args:
        model: The model name to invalidate.
        state_manager: StateManagerProtocol to clear session-level cache.

    Returns:
        True if an agent was invalidated, False if not cached.
    """

    logger = get_logger()
    cleared_module = agents_cache.invalidate_agent(model)
    cleared_session = False

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


def load_system_prompt(base_path: Path, model: str | None = None) -> str:
    """Load the system prompt from a single MD file."""

    _ = model

    prompt_file = base_path / "prompts" / "system_prompt.md"

    if not prompt_file.exists():
        raise FileNotFoundError(f"Required prompt file not found: {prompt_file}")

    return prompt_file.read_text(encoding="utf-8")


def load_tunacode_context() -> str:
    """Load guide file context with caching."""

    logger = get_logger()

    try:
        config = load_config()
        guide_file = "AGENTS.md"
        if config and "settings" in config:
            guide_file = config["settings"].get("guide_file", "AGENTS.md")
        tunacode_path = Path.cwd() / guide_file

        return context_cache.get_context(tunacode_path)

    except Exception as e:
        logger.error(f"Unexpected error loading guide file: {e}")
        raise


def _build_tools() -> list[AgentTool]:
    """Return the full TunaCode tool set as tinyagent AgentTools."""

    return [
        to_tinyagent_tool(bash),
        to_tinyagent_tool(glob),
        to_tinyagent_tool(grep),
        to_tinyagent_tool(list_dir),
        to_tinyagent_tool(read_file),
        to_tinyagent_tool(update_file),
        to_tinyagent_tool(web_fetch),
        to_tinyagent_tool(write_file),
    ]


def _normalize_chat_completions_url(base_url: str | None) -> str | None:
    if not isinstance(base_url, str):
        return None

    stripped = base_url.strip()
    if not stripped:
        return None

    if stripped.endswith(OPENAI_CHAT_COMPLETIONS_PATH):
        return stripped

    return f"{stripped.rstrip('/')}{OPENAI_CHAT_COMPLETIONS_PATH}"


def _resolve_base_url(session: SessionStateProtocol, provider_id: str) -> str | None:
    """Resolve model base URL with explicit override-first precedence.

    Precedence order:
    1) ``OPENAI_BASE_URL`` from session config
    2) provider API URL from models registry
    3) tinyagent OpenAICompatModel default (returned as None here)
    """

    env_config = session.user_config.get("env", {})
    if not isinstance(env_config, dict):
        raise TypeError("session.user_config['env'] must be a dict")

    configured_base_url = _normalize_chat_completions_url(env_config.get(ENV_OPENAI_BASE_URL))
    if configured_base_url is not None:
        return configured_base_url

    load_models_registry()
    provider_base_url = get_provider_base_url(provider_id)
    return _normalize_chat_completions_url(provider_base_url)


def _require_provider_base_url(provider_id: str, base_url: str | None) -> str | None:
    if base_url is not None:
        return base_url

    if provider_id == OPENROUTER_PROVIDER_ID:
        return None

    raise ValueError(
        "Provider has no configured API base URL. "
        f"Set {ENV_OPENAI_BASE_URL} or add provider.api to models_registry for '{provider_id}'."
    )


def _build_api_key_resolver(session: SessionStateProtocol) -> Callable[[str], str | None]:
    env_config = session.user_config.get("env", {})
    if not isinstance(env_config, dict):
        raise TypeError("session.user_config['env'] must be a dict")

    def _read_env_api_key(env_var: str) -> str | None:
        value = env_config.get(env_var)
        if not isinstance(value, str):
            return None

        stripped = value.strip()
        if not stripped:
            return None

        return stripped

    def _resolve(provider_id: str) -> str | None:
        provider_env_var = get_provider_env_var(provider_id)
        provider_api_key = _read_env_api_key(provider_env_var)
        if provider_api_key is not None:
            return provider_api_key

        if provider_env_var == ENV_OPENAI_API_KEY:
            return None

        return _read_env_api_key(ENV_OPENAI_API_KEY)

    return _resolve


def _build_stream_fn(
    *,
    request_delay: float,
    max_tokens: int | None,
) -> Callable[..., Awaitable[Any]]:
    async def _stream(model: Any, context: Any, options: dict[str, Any]) -> Any:
        if request_delay > 0:
            await _sleep_with_delay(request_delay)

        # tinyagent's agent loop passes max_tokens=None by default; we inject
        # TunaCode's configured limit if one exists.
        if max_tokens is not None:
            options = {**options, "max_tokens": max_tokens}

        return await stream_alchemy_openai_completions(model, context, options)

    return _stream


def _build_transform_context(
    state_manager: StateManagerProtocol,
) -> Callable[[list[AgentMessage], asyncio.Event | None], Awaitable[list[AgentMessage]]]:
    async def _transform_context(
        messages: list[AgentMessage],
        signal: asyncio.Event | None,
    ) -> list[AgentMessage]:
        controller = get_or_create_compaction_controller(state_manager)
        session = state_manager.session
        compaction_outcome = await controller.check_and_compact(
            messages,
            max_tokens=session.conversation.max_tokens,
            signal=signal,
            allow_threshold=False,
        )
        return controller.inject_summary_message(compaction_outcome.messages)

    return _transform_context


def _build_tinyagent_model(
    model: ModelName,
    session: SessionStateProtocol,
) -> OpenAICompatModel:
    """Convert a TunaCode ModelName into a tinyagent OpenAICompatModel.

    Resolves base URL with the following order:
    1) ``OPENAI_BASE_URL`` from session config
    2) provider API URL from models registry (normalized to `/chat/completions`)
    3) tinyagent OpenAICompatModel default when neither is available
    """

    provider_id, model_id = parse_model_string(model)
    resolved_base_url = _resolve_base_url(session, provider_id)
    base_url = _require_provider_base_url(provider_id, resolved_base_url)

    return OpenAICompatModel(
        provider=provider_id,
        id=model_id,
        **({"base_url": base_url} if base_url else {}),
    )


def get_or_create_agent(model: ModelName, state_manager: StateManagerProtocol) -> Agent:
    """Get existing agent or create a new tinyagent Agent for the specified model."""

    logger = get_logger()
    session = state_manager.session

    request_delay = _coerce_request_delay(session)
    settings = session.user_config.get("settings", {})

    # Ensure models_registry is cached so get_provider_env_var() works.
    load_models_registry()

    max_tokens = get_max_tokens()
    agent_version = _compute_agent_version(settings, request_delay, max_tokens=max_tokens)

    session_agent = session.agents.get(model)
    session_version = session.agent_versions.get(model)
    if session_agent and session_version == agent_version:
        logger.debug(f"Agent cache hit (session): {model}")
        return cast(Agent, session_agent)

    if session_agent and session_version != agent_version:
        logger.debug(f"Agent cache invalidated (session version mismatch): {model}")
        del session.agents[model]
        session.agent_versions.pop(model, None)

    cached_agent = agents_cache.get_agent(model, expected_version=agent_version)
    if cached_agent is not None:
        logger.debug(f"Agent cache hit (module): {model}")
        session.agents[model] = cached_agent
        session.agent_versions[model] = agent_version
        return cached_agent

    base_path = Path(__file__).parent.parent.parent.parent
    system_prompt = load_system_prompt(base_path, model=model)
    system_prompt += load_tunacode_context()

    tools_list = _build_tools()

    stream_fn = _build_stream_fn(request_delay=request_delay, max_tokens=max_tokens)
    opts = AgentOptions(
        stream_fn=stream_fn,
        session_id=getattr(session, "session_id", None),
        get_api_key=_build_api_key_resolver(session),
        transform_context=_build_transform_context(state_manager),
    )

    agent = Agent(opts)
    agent.set_system_prompt(system_prompt)
    agent.set_model(_build_tinyagent_model(model, session))
    agent.set_tools(tools_list)

    agents_cache.set_agent(model, agent=agent, version=agent_version)
    session.agent_versions[model] = agent_version
    session.agents[model] = agent

    logger.info(f"Agent created: {model}")

    return cast(Agent, agent)
