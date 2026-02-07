"""Tests for tunacode.core.agents.resume.filter."""

from tunacode.core.agents.resume.filter import filter_compacted
from tunacode.core.agents.resume.summary import SUMMARY_MARKER


def _make_plain_message(text: str) -> dict:
    """Create a plain dict message without summary marker."""
    return {"content": text}


def _make_summary_message(text: str = "Summary of conversation") -> dict:
    """Create a dict message containing the summary marker."""
    return {"content": f"{SUMMARY_MARKER}\n{text}"}


class TestFilterCompacted:
    def test_empty_messages_returns_empty(self):
        result = filter_compacted([])
        assert result == []

    def test_no_summary_returns_all_messages(self):
        messages = [
            _make_plain_message("hello"),
            _make_plain_message("world"),
            _make_plain_message("foo"),
        ]
        result = filter_compacted(messages)
        assert result == messages

    def test_summary_at_index_returns_from_that_point(self):
        messages = [
            _make_plain_message("old message 1"),
            _make_plain_message("old message 2"),
            _make_summary_message("summary of prior conversation"),
            _make_plain_message("new message 1"),
            _make_plain_message("new message 2"),
        ]
        result = filter_compacted(messages)
        assert len(result) == 3
        assert result[0] is messages[2]
        assert result[1] is messages[3]
        assert result[2] is messages[4]

    def test_summary_at_start_returns_all_messages(self):
        messages = [
            _make_summary_message("summary"),
            _make_plain_message("message 1"),
            _make_plain_message("message 2"),
        ]
        result = filter_compacted(messages)
        assert len(result) == 3
        assert result == messages

    def test_summary_at_end_returns_only_last_message(self):
        messages = [
            _make_plain_message("old 1"),
            _make_plain_message("old 2"),
            _make_summary_message("final summary"),
        ]
        result = filter_compacted(messages)
        assert len(result) == 1
        assert result[0] is messages[2]

    def test_multiple_summaries_returns_from_last_one(self):
        messages = [
            _make_plain_message("very old"),
            _make_summary_message("first summary"),
            _make_plain_message("old"),
            _make_summary_message("second summary"),
            _make_plain_message("recent"),
        ]
        result = filter_compacted(messages)
        assert len(result) == 2
        assert result[0] is messages[3]
        assert result[1] is messages[4]

    def test_summary_detected_in_content_field(self):
        """Verify detection works via the content field of a dict message."""
        marker_message = {"content": f"prefix {SUMMARY_MARKER} suffix"}
        messages = [
            _make_plain_message("before"),
            marker_message,
            _make_plain_message("after"),
        ]
        result = filter_compacted(messages)
        assert len(result) == 2
        assert result[0] is marker_message

    def test_summary_detected_in_parts_content(self):
        """Verify detection works via parts[].content for dict messages."""
        parts_message = {
            "parts": [
                {"content": f"{SUMMARY_MARKER}\nSome summary text"},
            ],
        }
        messages = [
            _make_plain_message("before"),
            parts_message,
            _make_plain_message("after"),
        ]
        result = filter_compacted(messages)
        assert len(result) == 2
        assert result[0] is parts_message

    def test_single_summary_message_returns_it(self):
        messages = [_make_summary_message("only message")]
        result = filter_compacted(messages)
        assert len(result) == 1
        assert result[0] is messages[0]

    def test_single_plain_message_returns_it(self):
        messages = [_make_plain_message("only message")]
        result = filter_compacted(messages)
        assert len(result) == 1
        assert result[0] is messages[0]
