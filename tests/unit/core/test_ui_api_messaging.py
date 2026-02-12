from __future__ import annotations

from tunacode.core.ui_api.messaging import estimate_messages_tokens, estimate_tokens


def test_estimate_tokens_matches_plain_text_heuristic() -> None:
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcdefgh") == 2


def test_estimate_messages_tokens_accepts_tinyagent_messages() -> None:
    messages = [
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "abcdefgh"}],
        }
    ]

    assert estimate_messages_tokens(messages) >= 2
