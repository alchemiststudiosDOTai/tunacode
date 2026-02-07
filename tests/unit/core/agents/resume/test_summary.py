"""Tests for tunacode.core.agents.resume.summary."""

from datetime import UTC, datetime
from types import SimpleNamespace

from tunacode.utils.messaging.token_counter import CHARS_PER_TOKEN

from tunacode.core.agents.resume.summary import (
    SUMMARY_MARKER,
    SUMMARY_THRESHOLD,
    SummaryMessage,
    is_summary_message,
    should_compact,
)


class TestSummaryMessageToMarkerText:
    def test_returns_marker_with_content(self):
        msg = SummaryMessage(
            content="This is a summary.",
            timestamp=datetime.now(UTC),
            source_range=(0, 5),
            token_count=10,
        )
        result = msg.to_marker_text()
        assert result == f"{SUMMARY_MARKER}\nThis is a summary."

    def test_marker_is_first_line(self):
        msg = SummaryMessage(
            content="content here",
            timestamp=datetime.now(UTC),
            source_range=(0, 1),
            token_count=5,
        )
        lines = msg.to_marker_text().split("\n")
        assert lines[0] == SUMMARY_MARKER


class TestIsSummaryMessage:
    def test_dict_with_content_containing_marker(self):
        message = {"content": f"{SUMMARY_MARKER}\nSome summary text"}
        assert is_summary_message(message) is True

    def test_dict_without_marker(self):
        message = {"content": "Just a regular message"}
        assert is_summary_message(message) is False

    def test_dict_with_parts_containing_marker(self):
        message = {
            "content": "",
            "parts": [{"content": f"{SUMMARY_MARKER}\nSummary here"}],
        }
        assert is_summary_message(message) is True

    def test_dict_with_parts_no_marker(self):
        message = {
            "content": "",
            "parts": [{"content": "no marker here"}],
        }
        assert is_summary_message(message) is False

    def test_object_with_parts_containing_marker(self):
        part = SimpleNamespace(content=f"{SUMMARY_MARKER}\nSummary")
        message = SimpleNamespace(parts=[part])
        assert is_summary_message(message) is True

    def test_object_with_parts_no_marker(self):
        part = SimpleNamespace(content="regular content")
        message = SimpleNamespace(parts=[part])
        assert is_summary_message(message) is False

    def test_plain_string_returns_false(self):
        assert is_summary_message("just a string") is False

    def test_empty_dict_returns_false(self):
        assert is_summary_message({}) is False

    def test_dict_with_non_string_content(self):
        message = {"content": 42}
        assert is_summary_message(message) is False

    def test_object_with_non_string_part_content(self):
        """Object part with non-string content returns False."""
        part = SimpleNamespace(content=42)
        message = SimpleNamespace(parts=[part])
        assert is_summary_message(message) is False


class TestShouldCompact:
    def test_empty_list_returns_false(self):
        assert should_compact([]) is False

    def test_few_small_messages_returns_false(self):
        messages = [
            {"content": "Hello"},
            {"content": "How are you?"},
        ]
        assert should_compact(messages) is False

    def test_many_large_messages_returns_true(self):
        chars_needed = (SUMMARY_THRESHOLD * CHARS_PER_TOKEN) + 100
        large_content = "x" * chars_needed
        messages = [{"content": large_content}]
        assert should_compact(messages) is True

    def test_object_messages_with_parts(self):
        chars_needed = (SUMMARY_THRESHOLD * CHARS_PER_TOKEN) + 100
        part = SimpleNamespace(content="y" * chars_needed)
        message = SimpleNamespace(parts=[part])
        assert should_compact([message]) is True

    def test_object_messages_below_threshold(self):
        part = SimpleNamespace(content="short")
        message = SimpleNamespace(parts=[part])
        assert should_compact([message]) is False

    def test_mixed_messages_accumulate(self):
        # Split across multiple messages to still exceed threshold
        per_message_chars = (SUMMARY_THRESHOLD * CHARS_PER_TOKEN) // 3 + 100
        messages = [
            {"content": "a" * per_message_chars},
            {"content": "b" * per_message_chars},
            {"content": "c" * per_message_chars},
        ]
        assert should_compact(messages) is True
