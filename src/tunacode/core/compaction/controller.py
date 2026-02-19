"""Compaction orchestration for request-time context management."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from tinyagent.agent_types import AgentMessage, Context, SimpleStreamOptions
from tinyagent.alchemy_provider import OpenAICompatModel, stream_alchemy_openai_completions

from tunacode.configuration.limits import get_max_tokens
from tunacode.configuration.models import (
    get_provider_alchemy_api,
    get_provider_base_url,
    get_provider_env_var,
    load_models_registry,
    parse_model_string,
)
from tunacode.constants import ENV_OPENAI_BASE_URL
from tunacode.utils.messaging import estimate_messages_tokens, estimate_tokens, get_content

from tunacode.core.compaction.summarizer import ContextSummarizer
from tunacode.core.compaction.types import (
    COMPACTION_REASON_ALREADY_COMPACTED,
    COMPACTION_REASON_AUTO_DISABLED,
    COMPACTION_REASON_BELOW_THRESHOLD,
    COMPACTION_REASON_COMPACTED,
    COMPACTION_REASON_MISSING_API_KEY,
    COMPACTION_REASON_NO_COMPACTABLE_MESSAGES,
    COMPACTION_REASON_NO_VALID_BOUNDARY,
    COMPACTION_REASON_SUMMARIZATION_FAILED,
    COMPACTION_REASON_THRESHOLD_NOT_ALLOWED,
    COMPACTION_REASON_UNSUPPORTED_PROVIDER,
    COMPACTION_STATUS_COMPACTED,
    COMPACTION_STATUS_FAILED,
    COMPACTION_STATUS_SKIPPED,
    CompactionOutcome,
    CompactionRecord,
)
from tunacode.core.logging import get_logger
from tunacode.core.types import StateManagerProtocol

DEFAULT_KEEP_RECENT_TOKENS = 20_000
DEFAULT_RESERVE_TOKENS = 16_384

COMPACTION_SUMMARY_HEADER = "[Compaction summary]"
COMPACTION_SUMMARY_KEY = "compaction_summary"

ROLE_USER = "user"
CONTENT_TYPE_TEXT = "text"
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
OPENAI_CHAT_COMPLETIONS_PATH = "/chat/completions"
OPENROUTER_PROVIDER_ID = "openrouter"

DEFAULT_MISSING_API_KEY_ENV_VAR = ENV_OPENAI_API_KEY


class _CompactionCapabilityError(RuntimeError):
    """Base class for expected non-fatal compaction capability skips."""

    def __init__(self, *, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


class UnsupportedCompactionProviderError(_CompactionCapabilityError):
    """Raised when compaction provider lacks a usable OpenAI-compatible endpoint."""

    def __init__(self, provider_id: str) -> None:
        super().__init__(
            reason=COMPACTION_REASON_UNSUPPORTED_PROVIDER,
            detail=provider_id,
        )


class MissingCompactionApiKeyError(_CompactionCapabilityError):
    """Raised when compaction summarization has no configured provider API key."""

    def __init__(self, env_var: str) -> None:
        super().__init__(
            reason=COMPACTION_REASON_MISSING_API_KEY,
            detail=env_var,
        )


class CompactionController:
    """Single entry point for threshold checks and forced compaction."""

    def __init__(
        self,
        *,
        state_manager: StateManagerProtocol,
        summarizer: ContextSummarizer | None = None,
        keep_recent_tokens: int = DEFAULT_KEEP_RECENT_TOKENS,
        reserve_tokens: int = DEFAULT_RESERVE_TOKENS,
        auto_compact: bool = True,
    ) -> None:
        if keep_recent_tokens < 0:
            raise ValueError("keep_recent_tokens must be >= 0")

        if reserve_tokens < 0:
            raise ValueError("reserve_tokens must be >= 0")

        self._state_manager = state_manager
        self.keep_recent_tokens = keep_recent_tokens
        self.reserve_tokens = reserve_tokens
        self.auto_compact = auto_compact

        self._compacted_this_request = False
        self._status_callback: CompactionStatusCallback | None = None

        if summarizer is None:
            self._summarizer = ContextSummarizer(self._generate_summary)
        else:
            self._summarizer = summarizer

    def set_status_callback(self, status_callback: CompactionStatusCallback | None) -> None:
        """Set callback used to signal compaction in-progress status."""

        self._status_callback = status_callback

    def reset_request_state(self) -> None:
        """Reset per-request idempotency guard."""

        self._compacted_this_request = False

    def should_compact(
        self,
        messages: list[AgentMessage],
        *,
        max_tokens: int,
        reserve_tokens: int | None = None,
    ) -> bool:
        """Return True when the estimated context exceeds the compaction threshold."""

        if max_tokens <= 0:
            return False

        reserve = self.reserve_tokens if reserve_tokens is None else reserve_tokens
        threshold_tokens = max_tokens - reserve - self.keep_recent_tokens
        effective_threshold = max(0, threshold_tokens)

        estimated_tokens = estimate_messages_tokens(messages)
        return estimated_tokens > effective_threshold

    async def check_and_compact(
        self,
        messages: list[AgentMessage],
        *,
        max_tokens: int,
        signal: asyncio.Event | None,
        force: bool = False,
        allow_threshold: bool = True,
    ) -> CompactionOutcome:
        """Compact messages if policy allows it, otherwise return structured skip outcome."""

        if not force:
            if self._compacted_this_request:
                return self._build_skip_outcome(messages, COMPACTION_REASON_ALREADY_COMPACTED)

            if not allow_threshold:
                return self._build_skip_outcome(messages, COMPACTION_REASON_THRESHOLD_NOT_ALLOWED)

            if not self.auto_compact:
                return self._build_skip_outcome(messages, COMPACTION_REASON_AUTO_DISABLED)

            if not self.should_compact(messages, max_tokens=max_tokens):
                return self._build_skip_outcome(messages, COMPACTION_REASON_BELOW_THRESHOLD)

        self._compacted_this_request = True
        return await self._compact(messages, signal=signal, force=force)

    async def force_compact(
        self,
        messages: list[AgentMessage],
        *,
        max_tokens: int,
        signal: asyncio.Event | None,
    ) -> CompactionOutcome:
        """Bypass threshold checks and compact immediately."""

        return await self.check_and_compact(
            messages,
            max_tokens=max_tokens,
            signal=signal,
            force=True,
            allow_threshold=True,
        )

    def inject_summary_message(self, messages: list[AgentMessage]) -> list[AgentMessage]:
        """Inject a synthetic summary user message for model-facing context only."""

        record = self._state_manager.session.compaction
        if record is None:
            return list(messages)

        summary_text = record.summary.strip()
        if not summary_text:
            return list(messages)

        if messages and _is_compaction_summary_message(messages[0]):
            return list(messages)

        summary_message = _build_summary_user_message(summary_text)
        return [summary_message, *messages]

    async def _compact(
        self,
        messages: list[AgentMessage],
        *,
        signal: asyncio.Event | None,
        force: bool,
    ) -> CompactionOutcome:
        logger = get_logger()
        if force:
            boundary = self._summarizer.calculate_force_retention_boundary(messages)
        else:
            boundary = self._summarizer.calculate_retention_boundary(
                messages, self.keep_recent_tokens
            )

        if boundary <= 0:
            logger.debug("Compaction skipped", reason=COMPACTION_REASON_NO_VALID_BOUNDARY)
            return self._build_skip_outcome(messages, COMPACTION_REASON_NO_VALID_BOUNDARY)

        compactable_messages = messages[:boundary]
        retained_messages = list(messages[boundary:])

        if not compactable_messages:
            logger.debug("Compaction skipped", reason=COMPACTION_REASON_NO_COMPACTABLE_MESSAGES)
            return self._build_skip_outcome(messages, COMPACTION_REASON_NO_COMPACTABLE_MESSAGES)

        self._announce_compaction_start()
        try:
            summary = await self._summarizer.summarize(
                compactable_messages,
                previous_summary=self._current_summary(),
                signal=signal,
            )
        except _CompactionCapabilityError as exc:
            logger.warning(
                "Compaction skipped: summarization capability unavailable",
                reason=exc.reason,
                detail=exc.detail,
            )
            return self._build_skip_outcome(messages, exc.reason, detail=exc.detail)
        except Exception as exc:  # noqa: BLE001 - fail-safe path
            failure_detail = str(exc)
            logger.error(
                "Compaction summarization failed",
                reason=COMPACTION_REASON_SUMMARIZATION_FAILED,
                detail=failure_detail,
            )
            return CompactionOutcome(
                status=COMPACTION_STATUS_FAILED,
                reason=COMPACTION_REASON_SUMMARIZATION_FAILED,
                detail=failure_detail,
                messages=list(messages),
            )
        finally:
            self._announce_compaction_end()

        self._update_compaction_record(
            all_messages=messages,
            retained_messages=retained_messages,
            compacted_message_count=len(compactable_messages),
            summary=summary,
        )

        return CompactionOutcome(
            status=COMPACTION_STATUS_COMPACTED,
            reason=COMPACTION_REASON_COMPACTED,
            detail=None,
            messages=retained_messages,
        )

    def _build_skip_outcome(
        self,
        messages: list[AgentMessage],
        reason: str,
        *,
        detail: str | None = None,
    ) -> CompactionOutcome:
        return CompactionOutcome(
            status=COMPACTION_STATUS_SKIPPED,
            reason=reason,
            detail=detail,
            messages=list(messages),
        )

    def _current_summary(self) -> str | None:
        record = self._state_manager.session.compaction
        if record is None:
            return None
        return record.summary

    def _announce_compaction_start(self) -> None:
        if self._status_callback is None:
            return
        self._status_callback(True)

    def _announce_compaction_end(self) -> None:
        if self._status_callback is None:
            return
        self._status_callback(False)

    def _update_compaction_record(
        self,
        *,
        all_messages: list[AgentMessage],
        retained_messages: list[AgentMessage],
        compacted_message_count: int,
        summary: str,
    ) -> None:
        previous_record = self._state_manager.session.compaction
        previous_summary = None if previous_record is None else previous_record.summary
        previous_count = 0 if previous_record is None else previous_record.compaction_count

        tokens_before = estimate_messages_tokens(all_messages)
        retained_tokens = estimate_messages_tokens(retained_messages)
        summary_tokens = estimate_tokens(summary)
        tokens_after = retained_tokens + summary_tokens

        self._state_manager.session.compaction = CompactionRecord(
            summary=summary,
            compacted_message_count=compacted_message_count,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            compaction_count=previous_count + 1,
            previous_summary=previous_summary,
            last_compacted_at=datetime.now(UTC).isoformat(),
        )

    async def _generate_summary(self, prompt: str, signal: asyncio.Event | None) -> str:
        model = self._build_model()
        api_key = self._resolve_api_key(model.provider)

        message: dict[str, Any] = {
            "role": ROLE_USER,
            "content": [{"type": CONTENT_TYPE_TEXT, "text": prompt}],
            "timestamp": None,
        }
        context = Context(system_prompt="", messages=[message], tools=None)

        options: SimpleStreamOptions = {
            "api_key": api_key,
            "signal": signal,
            "temperature": None,
            "max_tokens": get_max_tokens(),
        }

        response = await stream_alchemy_openai_completions(model, context, options)
        final_message = await response.result()

        summary = get_content(final_message).strip()
        if not summary:
            raise RuntimeError("Summary model returned empty content")

        return summary

    def _build_model(self) -> OpenAICompatModel:
        model_name = self._state_manager.session.current_model
        provider_id, model_id = parse_model_string(model_name)
        resolved_base_url = self._resolve_base_url(provider_id)
        base_url = self._require_provider_base_url(provider_id, resolved_base_url)

        resolved_alchemy_api = get_provider_alchemy_api(provider_id)

        model_kwargs: dict[str, str] = {}
        if base_url:
            model_kwargs["base_url"] = base_url
        if resolved_alchemy_api:
            model_kwargs["api"] = resolved_alchemy_api
        return OpenAICompatModel(
            provider=provider_id,
            id=model_id,
            **model_kwargs,
        )

    def _resolve_base_url(self, provider_id: str) -> str | None:
        """Resolve model base URL with explicit override-first precedence."""

        env_config = self._state_manager.session.user_config.get("env", {})
        if not isinstance(env_config, dict):
            raise TypeError("session.user_config['env'] must be a dict")

        configured_base_url = self._normalize_chat_completions_url(
            env_config.get(ENV_OPENAI_BASE_URL)
        )
        if configured_base_url is not None:
            return configured_base_url

        load_models_registry()
        provider_base_url = get_provider_base_url(provider_id)
        return self._normalize_chat_completions_url(provider_base_url)

    def _normalize_chat_completions_url(self, base_url: str | None) -> str | None:
        if not isinstance(base_url, str):
            return None

        stripped = base_url.strip()
        if not stripped:
            return None

        if stripped.endswith(OPENAI_CHAT_COMPLETIONS_PATH):
            return stripped

        return f"{stripped.rstrip('/')}{OPENAI_CHAT_COMPLETIONS_PATH}"

    def _require_provider_base_url(self, provider_id: str, base_url: str | None) -> str | None:
        if base_url is not None:
            return base_url

        if provider_id == OPENROUTER_PROVIDER_ID:
            return None

        raise UnsupportedCompactionProviderError(provider_id)

    def _resolve_api_key(self, provider_id: str) -> str:
        load_models_registry()
        provider_env_var = get_provider_env_var(provider_id)

        env_config = self._state_manager.session.user_config.get("env", {})
        if not isinstance(env_config, dict):
            raise TypeError("session.user_config['env'] must be a dict")

        provider_api_key = self._extract_api_key(env_config, provider_env_var)
        if provider_api_key is not None:
            return provider_api_key

        if provider_env_var != ENV_OPENAI_API_KEY:
            openai_api_key = self._extract_api_key(env_config, ENV_OPENAI_API_KEY)
            if openai_api_key is not None:
                return openai_api_key

        raise MissingCompactionApiKeyError(provider_env_var)

    def _extract_api_key(self, env_config: dict[str, Any], env_var: str) -> str | None:
        raw_value = env_config.get(env_var)
        if not isinstance(raw_value, str):
            return None

        api_key = raw_value.strip()
        if not api_key:
            return None

        return api_key


CompactionStatusCallback = Callable[[bool], None]


def get_or_create_compaction_controller(
    state_manager: StateManagerProtocol,
) -> CompactionController:
    """Return the session-scoped CompactionController instance."""

    session = state_manager.session
    existing = session._compaction_controller
    if isinstance(existing, CompactionController):
        return existing

    controller = CompactionController(state_manager=state_manager)
    session._compaction_controller = controller
    return controller


def apply_compaction_messages(
    state_manager: StateManagerProtocol,
    messages: list[AgentMessage],
) -> list[AgentMessage]:
    """Apply compaction output to session conversation with one shared write path."""

    applied_messages = list(messages)
    state_manager.session.conversation.messages = applied_messages
    return applied_messages


def build_compaction_notice(outcome: CompactionOutcome) -> str | None:
    """Return a user-facing notice for explicit compaction skip/failure outcomes."""

    reason = outcome.reason

    if reason == COMPACTION_REASON_UNSUPPORTED_PROVIDER:
        current_model = outcome.detail or "<unknown-model>"
        return f"Compaction skipped: unsupported summarization provider ({current_model})."

    if reason == COMPACTION_REASON_MISSING_API_KEY:
        missing_env_var = outcome.detail or DEFAULT_MISSING_API_KEY_ENV_VAR
        return f"Compaction skipped: missing API key ({missing_env_var})."

    if reason == COMPACTION_REASON_SUMMARIZATION_FAILED:
        return "Compaction failed during summarization; keeping existing history."

    return None


def _is_compaction_summary_message(message: AgentMessage) -> bool:
    if not isinstance(message, dict):
        return False

    if message.get(COMPACTION_SUMMARY_KEY) is True:
        return True

    content = message.get("content")
    if not isinstance(content, list) or not content:
        return False

    first_item = content[0]
    if not isinstance(first_item, dict):
        return False

    text = first_item.get("text")
    if not isinstance(text, str):
        return False

    return text.startswith(COMPACTION_SUMMARY_HEADER)


def _build_summary_user_message(summary_text: str) -> AgentMessage:
    payload_text = f"{COMPACTION_SUMMARY_HEADER}\n\n{summary_text}"
    return {
        "role": ROLE_USER,
        "content": [{"type": CONTENT_TYPE_TEXT, "text": payload_text}],
        "timestamp": None,
        COMPACTION_SUMMARY_KEY: True,
    }
