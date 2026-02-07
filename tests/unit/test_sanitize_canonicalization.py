from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tunacode.types.canonical import CanonicalMessage
from tunacode.utils.messaging import adapter

from tunacode.core.agents.resume import sanitize
from tunacode.core.types import ToolCallRegistry

USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
USER_CONTENT = "hello"
ASSISTANT_CONTENT = "world"
EXPECTED_MESSAGE_COUNT = 2


def _build_text_message(role: str, content: str) -> dict[str, Any]:
    return {
        "role": role,
        "content": [
            {
                "type": "text",
                "text": content,
                "text_signature": None,
            }
        ],
    }


class CanonicalCallCounter:
    def __init__(self) -> None:
        self.count = 0

    def wrap(
        self, original: Callable[[Any], CanonicalMessage]
    ) -> Callable[[Any], CanonicalMessage]:
        def wrapped(message: Any) -> CanonicalMessage:
            self.count += 1
            return original(message)

        return wrapped


def test_canonicalization_count_reduction(monkeypatch) -> None:
    messages = [
        _build_text_message(USER_ROLE, USER_CONTENT),
        _build_text_message(ASSISTANT_ROLE, ASSISTANT_CONTENT),
    ]
    message_count = len(messages)
    assert message_count == EXPECTED_MESSAGE_COUNT

    counter = CanonicalCallCounter()
    original_to_canonical = adapter.to_canonical
    monkeypatch.setattr(adapter, "to_canonical", counter.wrap(original_to_canonical))

    tool_registry = ToolCallRegistry()
    sanitize.run_cleanup_loop(messages, tool_registry)

    assert counter.count == message_count
