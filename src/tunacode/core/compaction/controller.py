"""Compaction orchestration for request-time context management."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from tinyagent.agent_types import AgentMessage, Context, Model, SimpleStreamOptions, ThinkingLevel

from tunacode.configuration.limits import get_max_tokens
from tunacode.configuration.models import (
    get_provider_env_var,
    load_models_registry,
    parse_model_string,
)
from tunacode.types import NoticeCallback
from tunacode.utils.messaging import estimate_messages_tokens, estimate_tokens, get_content

from tunacode.core.compaction.summarizer import ContextSummarizer
from tunacode.core.compaction.types import CompactionRecord
from tunacode.core.logging import get_logger
from tunacode.core.tinyagent.openrouter_usage import stream_openrouter_with_usage
from tunacode.core.types import StateManagerProtocol

DEFAULT_KEEP_RECENT_TOKENS = 20_000
DEFAULT_RESERVE_TOKENS = 16_384

COMPACTION_NOTICE_TEXT = "Compacting context..."
COMPACTION_SUMMARY_HEADER = "[Compaction summary]"
COMPACTION_SUMMARY_KEY = "compaction_summary"

OPENROUTER_PROVIDER_ID = "openrouter"
OPENROUTER_API_NAME = "openrouter"

ROLE_USER = "user"
CONTENT_TYPE_TEXT = "text"


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
        self._notice_callback: NoticeCallback | None = None
        self._status_callback: CompactionStatusCallback | None = None

        if summarizer is None:
            self._summarizer = ContextSummarizer(self._generate_summary)
        else:
            self._summarizer = summarizer

    def set_callbacks(
        self,
        *,
        notice_callback: NoticeCallback | None,
        status_callback: CompactionStatusCallback | None,
    ) -> None:
        """Set callbacks used during compaction operations."""

        self._notice_callback = notice_callback
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
    ) -> list[AgentMessage]:
        """Compact messages if policy allows it, otherwise return unchanged messages."""

        if not force:
            if self._compacted_this_request:
                return list(messages)

            if not allow_threshold:
                return list(messages)

            if not self.auto_compact:
                return list(messages)

            if not self.should_compact(messages, max_tokens=max_tokens):
                return list(messages)

        self._compacted_this_request = True
        return await self._compact(messages, signal=signal)

    async def force_compact(
        self,
        messages: list[AgentMessage],
        *,
        max_tokens: int,
        signal: asyncio.Event | None,
    ) -> list[AgentMessage]:
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
    ) -> list[AgentMessage]:
        logger = get_logger()
        boundary = self._summarizer.calculate_retention_boundary(messages, self.keep_recent_tokens)

        if boundary <= 0:
            logger.debug("Compaction skipped: no valid retention boundary")
            return list(messages)

        compactable_messages = messages[:boundary]
        retained_messages = list(messages[boundary:])

        if not compactable_messages:
            logger.debug("Compaction skipped: no messages before retention boundary")
            return list(messages)

        self._announce_compaction_start()
        try:
            summary = await self._summarizer.summarize(
                compactable_messages,
                previous_summary=self._current_summary(),
                signal=signal,
            )
        except Exception as exc:  # noqa: BLE001 - fail-safe path
            logger.error("Compaction summarization failed", error=str(exc))
            return list(messages)
        finally:
            self._announce_compaction_end()

        self._update_compaction_record(
            all_messages=messages,
            retained_messages=retained_messages,
            compacted_message_count=len(compactable_messages),
            summary=summary,
        )

        self._state_manager.session.conversation.messages = retained_messages
        return retained_messages

    def _current_summary(self) -> str | None:
        record = self._state_manager.session.compaction
        if record is None:
            return None
        return record.summary

    def _announce_compaction_start(self) -> None:
        if self._status_callback is not None:
            self._status_callback(True)

        if self._notice_callback is not None:
            self._notice_callback(COMPACTION_NOTICE_TEXT)

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

        response = await stream_openrouter_with_usage(model, context, options)
        final_message = await response.result()

        summary = get_content(final_message).strip()
        if not summary:
            raise RuntimeError("Summary model returned empty content")

        return summary

    def _build_model(self) -> Model:
        model_name = self._state_manager.session.current_model
        provider_id, model_id = parse_model_string(model_name)

        if provider_id != OPENROUTER_PROVIDER_ID:
            raise ValueError(
                "Compaction summarization currently supports only openrouter models; "
                f"got {model_name!r}"
            )

        return Model(
            provider=provider_id,
            id=model_id,
            api=OPENROUTER_API_NAME,
            thinking_level=ThinkingLevel.OFF,
        )

    def _resolve_api_key(self, provider_id: str) -> str:
        load_models_registry()
        env_var = get_provider_env_var(provider_id)

        env_config = self._state_manager.session.user_config.get("env", {})
        if not isinstance(env_config, dict):
            raise TypeError("session.user_config['env'] must be a dict")

        raw_value = env_config.get(env_var)
        if not isinstance(raw_value, str):
            raise ValueError(f"Missing API key: {env_var}")

        api_key = raw_value.strip()
        if not api_key:
            raise ValueError(f"Missing API key: {env_var}")

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
