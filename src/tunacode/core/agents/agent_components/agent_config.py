"""Agent configuration and creation utilities."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol, cast

import httpx
from tinyagent.agent import Agent, AgentOptions
from tinyagent.agent_types import (
    AgentMessage,
    AgentTool,
    AgentToolResult,
    AgentToolUpdateCallback,
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    JsonObject,
    Model,
    SimpleStreamOptions,
    StreamFn,
    StreamResponse,
)
from tinyagent.alchemy_provider import OpenAICompatModel, stream_alchemy_openai_completions

from tunacode.configuration.limits import get_max_tokens
from tunacode.configuration.models import (
    get_cached_models_registry,
    get_provider_alchemy_api,
    get_provider_base_url,
    get_provider_env_var,
    load_models_registry,
    parse_model_string,
)
from tunacode.constants import AGENTS_MD, ENV_OPENAI_BASE_URL
from tunacode.skills.prompting import (
    compute_skills_prompt_fingerprint,
    render_available_skills_block,
    render_selected_skills_block,
)
from tunacode.skills.registry import list_skill_summaries
from tunacode.skills.selection import resolve_selected_skills
from tunacode.types import ModelName

from tunacode.tools.bash import bash
from tunacode.tools.discover import discover
from tunacode.tools.hashline_edit import hashline_edit
from tunacode.tools.read_file import read_file
from tunacode.tools.web_fetch import web_fetch
from tunacode.tools.write_file import write_file

from tunacode.infrastructure.cache.caches import agents as agents_cache
from tunacode.infrastructure.cache.caches import tunacode_context as context_cache

from tunacode.core.compaction.controller import get_or_create_compaction_controller
from tunacode.core.logging.manager import get_logger
from tunacode.core.types.state import SessionStateProtocol, StateManagerProtocol

from .agent_session_config import (
    SessionConfig,
    SkillsPromptState,
    _coerce_global_request_timeout,
    _coerce_max_iterations,
    _coerce_session_config,
    _compute_agent_version,
    _normalize_session_config,
)

__all__ = [
    "get_or_create_agent",
    "invalidate_agent_cache",
    "load_system_prompt",
    "load_tunacode_context",
    "_apply_tool_concurrency_limit",
    "_build_api_key_resolver",
    "_build_stream_fn",
    "_build_tinyagent_model",
    "_coerce_global_request_timeout",
    "_coerce_max_iterations",
]

ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
OPENAI_CHAT_COMPLETIONS_PATH = "/chat/completions"
OPENROUTER_PROVIDER_ID = "openrouter"
MAX_PARALLEL_TOOL_CALLS, MIN_PARALLEL_TOOL_CALLS = 3, 1
MAX_STREAM_RETRY_DELAY_SECONDS = 8.0
STREAM_RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429})
STREAM_RAW_EVENT_GAP_WARN_MS = 250.0

ToolExecute = Callable[
    [str, JsonObject, asyncio.Event | None, AgentToolUpdateCallback],
    Awaitable[AgentToolResult],
]


class _LifecycleTraceLogger(Protocol):
    debug_mode: bool

    def lifecycle(self, message: str) -> None: ...
    def warning(self, message: str, **kwargs: object) -> None: ...


class _TracedStreamResponse:
    """Wrap provider StreamResponse with timing logs for /debug sessions."""

    def __init__(
        self,
        response: StreamResponse,
        *,
        logger: _LifecycleTraceLogger,
        opened_at: float,
        response_ready_at: float,
    ) -> None:
        self._response = response
        self._logger = logger
        self._opened_at = opened_at
        self._response_ready_at = response_ready_at
        self._event_count = 0
        self._last_event_at = response_ready_at

    def __aiter__(self) -> _TracedStreamResponse:
        return self

    async def __anext__(self) -> AssistantMessageEvent:
        event = await self._response.__anext__()
        now = time.perf_counter()
        self._event_count += 1
        event_type = event.type or "unknown"

        if self._event_count == 1:
            self._logger.lifecycle(
                "Stream: "
                f"provider_first_raw type={event_type} "
                f"since_open={(now - self._opened_at) * 1000.0:.1f}ms "
                f"since_response={(now - self._response_ready_at) * 1000.0:.1f}ms"
            )
        else:
            gap_ms = (now - self._last_event_at) * 1000.0
            if gap_ms >= STREAM_RAW_EVENT_GAP_WARN_MS:
                self._logger.lifecycle(
                    "Stream: "
                    f"provider_raw_gap type={event_type} "
                    f"gap={gap_ms:.1f}ms "
                    f"count={self._event_count}"
                )

        self._last_event_at = now
        return event

    async def result(self) -> AssistantMessage:
        started_at = time.perf_counter()
        result = await self._response.result()
        duration_ms = (time.perf_counter() - started_at) * 1000.0
        self._logger.lifecycle(f"Stream: provider_result dur={duration_ms:.1f}ms")
        return result


async def _sleep_with_delay(total_delay: float) -> None:
    await asyncio.sleep(total_delay)


def invalidate_agent_cache(model: str, state_manager: StateManagerProtocol) -> bool:
    """Invalidate cached agent for a specific model."""
    logger = get_logger()
    cleared_module = agents_cache.invalidate_agent(model)
    cleared_session = False

    session_agents = _session_agents_dict(state_manager.session)
    if model in session_agents:
        del session_agents[model]
        cleared_session = True
    state_manager.session.agent_versions.pop(model, None)

    invalidated = cleared_module or cleared_session
    if invalidated:
        logger.debug(
            f"Agent cache cleared: model={model}, "
            f"module={cleared_module}, session={cleared_session}"
        )
    return invalidated


def load_system_prompt(
    base_path: Path,
    model: str | None = None,
) -> str:
    _ = model
    prompt_file = base_path / "prompts" / "system_prompt.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Required prompt file not found: {prompt_file}")
    return prompt_file.read_text(encoding="utf-8")


def load_tunacode_context() -> str:
    logger = get_logger()
    try:
        tunacode_path = Path.cwd() / AGENTS_MD
        return context_cache.get_context(tunacode_path)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Unexpected error loading guide file: {exc}")
        raise


def _wrap_tool_with_concurrency_limit(tool: AgentTool, *, limiter: asyncio.Semaphore) -> AgentTool:
    raw_execute_fn = cast(object, tool.execute)
    if raw_execute_fn is None:
        raise ValueError(f"Tool '{tool.name}' must define an execute handler")
    typed_execute_fn = cast(ToolExecute, raw_execute_fn)

    async def _execute_with_limit(
        tool_call_id: str,
        args: JsonObject,
        signal: asyncio.Event | None,
        on_update: AgentToolUpdateCallback,
    ) -> AgentToolResult:
        await limiter.acquire()
        try:
            return await typed_execute_fn(tool_call_id, args, signal, on_update)
        finally:
            limiter.release()

    tool.execute = _execute_with_limit
    return tool


def _apply_tool_concurrency_limit(
    tools: Sequence[AgentTool],
    *,
    max_parallel_tool_calls: int = MAX_PARALLEL_TOOL_CALLS,
) -> list[AgentTool]:
    if max_parallel_tool_calls < MIN_PARALLEL_TOOL_CALLS:
        raise ValueError(
            f"max_parallel_tool_calls must be >= {MIN_PARALLEL_TOOL_CALLS}, "
            f"got {max_parallel_tool_calls}"
        )
    limiter = asyncio.Semaphore(max_parallel_tool_calls)
    return [_wrap_tool_with_concurrency_limit(tool, limiter=limiter) for tool in tools]


def _build_tools(*, strict_validation: bool = False) -> list[AgentTool]:
    _ = strict_validation
    tools: list[AgentTool] = [
        bash,
        discover,
        read_file,
        hashline_edit,
        web_fetch,
        write_file,
    ]
    return _apply_tool_concurrency_limit(tools)


def _normalize_chat_completions_url(base_url: str | None) -> str | None:
    if not isinstance(base_url, str):
        return None
    stripped = base_url.strip()
    if not stripped:
        return None
    if stripped.endswith(OPENAI_CHAT_COMPLETIONS_PATH):
        return stripped
    return f"{stripped.rstrip('/')}{OPENAI_CHAT_COMPLETIONS_PATH}"


def _resolve_base_url(config: SessionConfig | SessionStateProtocol, provider_id: str) -> str | None:
    """Resolve base URL with env override first, then lazy registry lookup."""
    session_config = _coerce_session_config(config)
    configured_base_url = _normalize_chat_completions_url(
        session_config.env.get(ENV_OPENAI_BASE_URL)
    )
    if configured_base_url is not None:
        return configured_base_url
    return _normalize_chat_completions_url(get_provider_base_url(provider_id))


def _require_provider_base_url(provider_id: str, base_url: str | None) -> str | None:
    if base_url is not None or provider_id == OPENROUTER_PROVIDER_ID:
        return base_url
    raise ValueError(
        "Provider has no configured API base URL. "
        f"Set {ENV_OPENAI_BASE_URL} or add provider.api to models_registry for '{provider_id}'."
    )


def _build_api_key_resolver(
    env_config: Mapping[str, str] | SessionStateProtocol,
) -> Callable[[str], str | None]:
    if isinstance(env_config, Mapping):

        def env_getter() -> Mapping[str, str]:
            return env_config
    else:
        session = env_config

        def env_getter() -> Mapping[str, str]:
            return {
                key: value.strip()
                for key, value in session.user_config["env"].items()
                if value.strip()
            }

    def _read_api_key(env_var: str) -> str | None:
        configured = env_getter().get(env_var)
        if isinstance(configured, str) and configured.strip():
            return configured.strip()
        os_value = os.environ.get(env_var, "")
        return os_value.strip() or None

    def _resolve(provider_id: str) -> str | None:
        provider_env_var = get_provider_env_var(provider_id)
        provider_api_key = _read_api_key(provider_env_var)
        if provider_api_key is not None:
            return provider_api_key
        if provider_env_var == ENV_OPENAI_API_KEY:
            return None
        return _read_api_key(ENV_OPENAI_API_KEY)

    return _resolve


def _merge_stream_options(
    *,
    options: SimpleStreamOptions,
    max_tokens: int | None,
) -> SimpleStreamOptions:
    if max_tokens is None:
        return options
    update_values: dict[str, object] = {"max_tokens": max_tokens}
    return options.model_copy(update=update_values)


def _is_retryable_stream_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        if response is None:
            return False
        return response.status_code in STREAM_RETRYABLE_STATUS_CODES or response.status_code >= 500
    return isinstance(exc, httpx.RequestError | TimeoutError)


def _compute_stream_retry_delay(attempt_number: int) -> float:
    exponent = attempt_number - 1
    if exponent < 0:
        exponent = 0
    backoff_multiplier = 1 << exponent
    exponential_delay = 0.5 * float(backoff_multiplier)
    if exponential_delay > MAX_STREAM_RETRY_DELAY_SECONDS:
        return MAX_STREAM_RETRY_DELAY_SECONDS
    return exponential_delay


def _build_stream_fn(
    *,
    request_delay: float,
    max_tokens: int | None,
    max_retries: int = 1,
) -> StreamFn:
    async def _stream(
        model: Model,
        context: Context,
        options: SimpleStreamOptions,
    ) -> StreamResponse:
        stream_options = _merge_stream_options(options=options, max_tokens=max_tokens)
        logger = get_logger()

        for attempt in range(1, max_retries + 1):
            if request_delay > 0:
                await _sleep_with_delay(request_delay)
            try:
                opened_at = time.perf_counter()
                response = await stream_alchemy_openai_completions(model, context, stream_options)
                response_ready_at = time.perf_counter()
                logger.lifecycle(
                    "Stream: "
                    f"provider_open attempt={attempt}/{max_retries} "
                    f"dur={(response_ready_at - opened_at) * 1000.0:.1f}ms"
                )
                if logger.debug_mode:
                    return _TracedStreamResponse(
                        response,
                        logger=cast(_LifecycleTraceLogger, logger),
                        opened_at=opened_at,
                        response_ready_at=response_ready_at,
                    )
                return response
            except Exception as exc:  # noqa: BLE001
                if attempt >= max_retries or not _is_retryable_stream_error(exc):
                    raise
                logger.warning(
                    "Retrying provider stream request after transient error: "
                    f"attempt={attempt}/{max_retries}, error={type(exc).__name__}"
                )
                await _sleep_with_delay(_compute_stream_retry_delay(attempt))

        raise RuntimeError("Unreachable stream retry exhaustion")

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
    config: SessionConfig | SessionStateProtocol,
) -> OpenAICompatModel:
    session_config = _coerce_session_config(config)
    provider_id, model_id = parse_model_string(model)
    base_url = _require_provider_base_url(
        provider_id,
        _resolve_base_url(session_config, provider_id),
    )
    alchemy_api = get_provider_alchemy_api(provider_id)
    if base_url is not None and alchemy_api is not None:
        return OpenAICompatModel(
            provider=provider_id,
            id=model_id,
            api=alchemy_api,
            base_url=base_url,
        )
    if base_url is not None:
        return OpenAICompatModel(provider=provider_id, id=model_id, base_url=base_url)
    if alchemy_api is not None:
        return OpenAICompatModel(provider=provider_id, id=model_id, api=alchemy_api)
    return OpenAICompatModel(provider=provider_id, id=model_id)


def _build_skills_prompt_state(session: SessionStateProtocol) -> SkillsPromptState:
    logger = get_logger()
    available_skills_started_at = time.perf_counter()
    available_skill_summaries = list_skill_summaries()
    available_skills_duration_ms = (time.perf_counter() - available_skills_started_at) * 1000.0
    logger.lifecycle(
        "Init: "
        f"available_skills count={len(available_skill_summaries)} "
        f"dur={available_skills_duration_ms:.1f}ms"
    )

    selected_skills_started_at = time.perf_counter()
    selected_skills = resolve_selected_skills(session.selected_skill_names)
    selected_skills_duration_ms = (time.perf_counter() - selected_skills_started_at) * 1000.0
    logger.lifecycle(
        "Init: "
        f"selected_skills count={len(selected_skills)} "
        f"dur={selected_skills_duration_ms:.1f}ms"
    )

    return SkillsPromptState(
        available_block=render_available_skills_block(available_skill_summaries),
        selected_block=render_selected_skills_block(selected_skills),
        fingerprint=compute_skills_prompt_fingerprint(available_skill_summaries, selected_skills),
        selected_skills=selected_skills,
    )


def _get_session_cached_agent(session: SessionStateProtocol, model: ModelName) -> Agent | None:
    cached_agent = _session_agents_dict(session).get(model)
    if isinstance(cached_agent, Agent):
        return cached_agent
    if cached_agent is None:
        return None
    raise TypeError(f"session.agents[{model!r}] must be Agent, got {type(cached_agent).__name__}")


def _session_agents_dict(session: SessionStateProtocol) -> dict[str, object]:
    agents = cast(object, session.agents)
    if not isinstance(agents, dict):
        raise TypeError(f"session.agents must be a dict, got {type(agents).__name__}")
    if not all(isinstance(key, str) for key in agents):
        raise TypeError("session.agents keys must be strings")
    return cast(dict[str, object], agents)


def _build_agent_options(
    *,
    session: SessionStateProtocol,
    state_manager: StateManagerProtocol,
    config: SessionConfig,
    max_tokens: int | None,
) -> AgentOptions:
    return AgentOptions(
        stream_fn=_build_stream_fn(
            request_delay=config.settings.request_delay,
            max_tokens=max_tokens,
            max_retries=config.settings.max_retries,
        ),
        session_id=session.session_id,
        get_api_key=_build_api_key_resolver(config.env),
        transform_context=_build_transform_context(state_manager),
    )


def get_or_create_agent(model: ModelName, state_manager: StateManagerProtocol) -> Agent:
    """Get existing agent or create a new tinyagent Agent for the specified model."""
    logger = get_logger()
    session = state_manager.session
    session_agents = _session_agents_dict(session)
    config = _normalize_session_config(session)

    init_started_at = time.perf_counter()
    registry_cached = get_cached_models_registry() is not None  # type: ignore[misc]
    registry_started_at = time.perf_counter()
    load_models_registry()
    registry_duration_ms = (time.perf_counter() - registry_started_at) * 1000.0
    logger.lifecycle(
        "Init: "
        f"models_registry cached={str(registry_cached).lower()} "
        f"dur={registry_duration_ms:.1f}ms"
    )

    skills_started_at = time.perf_counter()
    skills_state = _build_skills_prompt_state(session)
    skills_duration_ms = (time.perf_counter() - skills_started_at) * 1000.0
    logger.lifecycle(
        "Init: "
        f"skills_prompt total={skills_duration_ms:.1f}ms "
        f"selected={len(skills_state.selected_skills)}"
    )

    max_tokens = get_max_tokens()
    agent_version = _compute_agent_version(
        config.settings,
        max_tokens=max_tokens,
        skills_prompt_fingerprint=skills_state.fingerprint,
    )

    session_agent = _get_session_cached_agent(session, model)
    session_version = session.agent_versions.get(model)
    if session_agent is not None and session_version == agent_version:
        logger.debug(f"Agent cache hit (session): {model}")
        return session_agent
    if session_agent is not None and session_version != agent_version:
        logger.debug(f"Agent cache invalidated (session version mismatch): {model}")
        del session_agents[model]
        session.agent_versions.pop(model, None)

    base_path = Path(__file__).parent.parent.parent.parent
    system_prompt_content = load_system_prompt(base_path, model=model)
    tunacode_context_content = load_tunacode_context()
    system_prompt = (
        system_prompt_content
        + tunacode_context_content
        + skills_state.selected_block
        + skills_state.available_block
    )

    tools = _build_tools(strict_validation=config.settings.tool_strict_validation)

    agent_build_started_at = time.perf_counter()
    agent = Agent(
        _build_agent_options(
            session=session,
            state_manager=state_manager,
            config=config,
            max_tokens=max_tokens,
        )
    )
    agent.set_system_prompt(system_prompt)
    agent.set_model(_build_tinyagent_model(model, config))
    agent.set_tools(tools)

    session.agent_versions[model] = agent_version
    session_agents[model] = agent

    agent_build_duration_ms = (time.perf_counter() - agent_build_started_at) * 1000.0
    total_init_duration_ms = (time.perf_counter() - init_started_at) * 1000.0
    logger.lifecycle(
        "Init: "
        f"agent_build model={model} "
        f"dur={agent_build_duration_ms:.1f}ms "
        f"total={total_init_duration_ms:.1f}ms"
    )
    logger.info(f"Agent created: {model}")
    return agent
