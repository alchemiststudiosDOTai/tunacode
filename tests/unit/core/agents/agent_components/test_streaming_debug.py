"""Tests for tunacode.core.agents.agent_components.streaming_debug."""

from types import SimpleNamespace

from tunacode.core.agents.agent_components.streaming_debug import (
    DEBUG_STREAM_EVENT_HISTORY_LIMIT,
    DEBUG_STREAM_NEWLINE_REPLACEMENT,
    DEBUG_STREAM_PREFIX_MAX_LEN,
    DEBUG_STREAM_PREVIEW_SUFFIX,
    DEBUG_STREAM_RAW_STREAM_MAX_CHARS,
    DEBUG_STREAM_TEXT_PREVIEW_LEN,
    _append_debug_event,
    _append_raw_stream,
    _build_stream_event_debug_info,
    _capture_pre_first_delta_text,
    _extract_first_part_text,
    _extract_result_preview,
    _extract_stream_result_text,
    _extract_text_from_parts,
    _format_debug_preview,
    _format_request_part_debug,
    _format_stream_preview,
    _get_delta_debug_data,
    _get_part_debug_data,
    _get_result_debug_data,
    _log_stream_request_parts,
    _truncate_prefix,
)


class TestFormatStreamPreview:
    def test_none_returns_empty(self):
        preview, length = _format_stream_preview(None)
        assert preview == ""
        assert length == 0

    def test_short_string_unchanged(self):
        text = "hello world"
        preview, length = _format_stream_preview(text)
        assert preview == "hello world"
        assert length == 11

    def test_long_string_truncated_with_suffix(self):
        text = "a" * 200
        preview, length = _format_stream_preview(text)
        expected = "a" * DEBUG_STREAM_TEXT_PREVIEW_LEN + DEBUG_STREAM_PREVIEW_SUFFIX
        assert preview == expected
        assert length == 200

    def test_newlines_replaced(self):
        text = "line1\nline2"
        preview, _length = _format_stream_preview(text)
        assert "\n" not in preview
        assert DEBUG_STREAM_NEWLINE_REPLACEMENT in preview

    def test_exact_boundary_no_suffix(self):
        text = "x" * DEBUG_STREAM_TEXT_PREVIEW_LEN
        preview, length = _format_stream_preview(text)
        assert preview == text
        assert DEBUG_STREAM_PREVIEW_SUFFIX not in preview
        assert length == DEBUG_STREAM_TEXT_PREVIEW_LEN

    def test_non_string_value_converted(self):
        preview, length = _format_stream_preview(42)
        assert preview == "42"
        assert length == 2


class TestFormatRequestPartDebug:
    def test_text_part_with_content(self):
        part = SimpleNamespace(part_kind="text", content="hello", args=None)
        result = _format_request_part_debug(part)
        assert "kind=text" in result
        assert "content=hello" in result

    def test_tool_call_part(self):
        part = SimpleNamespace(
            part_kind="tool-call",
            tool_name="grep",
            tool_call_id="call_123",
            content=None,
            args='{"pattern": "foo"}',
        )
        result = _format_request_part_debug(part)
        assert "kind=tool-call" in result
        assert "tool=grep" in result
        assert "id=call_123" in result
        assert "args=" in result

    def test_unknown_part_kind(self):
        part = SimpleNamespace(content="data", args=None)
        result = _format_request_part_debug(part)
        assert "kind=unknown" in result

    def test_no_content_no_args(self):
        part = SimpleNamespace(part_kind="system", content=None, args=None)
        result = _format_request_part_debug(part)
        assert result == "kind=system"


class TestExtractFirstPartText:
    def test_none_returns_none(self):
        assert _extract_first_part_text(None) is None

    def test_non_list_returns_none(self):
        assert _extract_first_part_text("not a list") is None

    def test_empty_list_returns_none(self):
        assert _extract_first_part_text([]) is None

    def test_list_with_content_returns_first(self):
        parts = [
            SimpleNamespace(content="first"),
            SimpleNamespace(content="second"),
        ]
        assert _extract_first_part_text(parts) == "first"

    def test_skips_none_content(self):
        parts = [
            SimpleNamespace(content=None),
            SimpleNamespace(content="found"),
        ]
        assert _extract_first_part_text(parts) == "found"

    def test_skips_empty_string(self):
        parts = [
            SimpleNamespace(content=""),
            SimpleNamespace(content="non-empty"),
        ]
        assert _extract_first_part_text(parts) == "non-empty"

    def test_tuple_works(self):
        parts = (SimpleNamespace(content="via tuple"),)
        assert _extract_first_part_text(parts) == "via tuple"


class TestExtractTextFromParts:
    def test_none_returns_none(self):
        assert _extract_text_from_parts(None) is None

    def test_empty_list_returns_none(self):
        assert _extract_text_from_parts([]) is None

    def test_joins_all_text(self):
        parts = [
            SimpleNamespace(content="hello "),
            SimpleNamespace(content="world"),
        ]
        assert _extract_text_from_parts(parts) == "hello world"

    def test_skips_non_string_content(self):
        parts = [
            SimpleNamespace(content=42),
            SimpleNamespace(content="only this"),
        ]
        assert _extract_text_from_parts(parts) == "only this"

    def test_all_none_content_returns_none(self):
        parts = [SimpleNamespace(content=None)]
        assert _extract_text_from_parts(parts) is None

    def test_non_list_returns_none(self):
        assert _extract_text_from_parts("not a list") is None


class TestExtractStreamResultText:
    def test_none_returns_none(self):
        assert _extract_stream_result_text(None) is None

    def test_string_returns_itself(self):
        assert _extract_stream_result_text("hello") == "hello"

    def test_obj_with_output_attr(self):
        obj = SimpleNamespace(output="output text")
        assert _extract_stream_result_text(obj) == "output text"

    def test_obj_with_text_attr(self):
        obj = SimpleNamespace(text="text content")
        assert _extract_stream_result_text(obj) == "text content"

    def test_obj_with_content_attr(self):
        obj = SimpleNamespace(content="content value")
        assert _extract_stream_result_text(obj) == "content value"

    def test_obj_with_parts(self):
        part = SimpleNamespace(content="from parts")
        obj = SimpleNamespace(parts=[part])
        assert _extract_stream_result_text(obj) == "from parts"

    def test_nested_result(self):
        inner = SimpleNamespace(output="nested output")
        obj = SimpleNamespace(result=inner)
        assert _extract_stream_result_text(obj) == "nested output"

    def test_empty_string_attr_skipped(self):
        obj = SimpleNamespace(output="", text="fallback")
        assert _extract_stream_result_text(obj) == "fallback"


class TestExtractResultPreview:
    def test_string_result(self):
        preview, length = _extract_result_preview("hello world")
        assert length == 11
        assert "hello" in preview

    def test_obj_with_output(self):
        obj = SimpleNamespace(output="output text here")
        preview, length = _extract_result_preview(obj)
        assert length == 16
        assert preview is not None

    def test_obj_with_text(self):
        obj = SimpleNamespace(text="some text")
        preview, length = _extract_result_preview(obj)
        assert length == 9
        assert preview is not None

    def test_obj_with_parts(self):
        part = SimpleNamespace(content="part content")
        obj = SimpleNamespace(parts=[part])
        preview, length = _extract_result_preview(obj)
        assert length == 12
        assert preview is not None

    def test_no_extractable_content(self):
        obj = SimpleNamespace(other="irrelevant")
        preview, length = _extract_result_preview(obj)
        assert preview is None
        assert length is None

    def test_none_result(self):
        preview, length = _extract_result_preview(None)
        assert preview is None
        assert length is None


class TestTruncatePrefix:
    def test_short_text_unchanged(self):
        assert _truncate_prefix("short") == "short"

    def test_exact_boundary_unchanged(self):
        text = "x" * DEBUG_STREAM_PREFIX_MAX_LEN
        assert _truncate_prefix(text) == text

    def test_long_text_truncated(self):
        text = "x" * (DEBUG_STREAM_PREFIX_MAX_LEN + 50)
        result = _truncate_prefix(text)
        assert len(result) == DEBUG_STREAM_PREFIX_MAX_LEN


class TestCapturePreFirstDeltaText:
    def test_first_delta_seen_returns_existing(self):
        event = SimpleNamespace(part=SimpleNamespace(content="new"))
        result = _capture_pre_first_delta_text(
            event, first_delta_seen=True, existing_text="existing"
        )
        assert result == "existing"

    def test_event_with_text_part_content(self):
        event = SimpleNamespace(part=SimpleNamespace(content="captured"))
        result = _capture_pre_first_delta_text(event, first_delta_seen=False, existing_text=None)
        assert result == "captured"

    def test_no_part_returns_existing(self):
        event = SimpleNamespace(part=None)
        result = _capture_pre_first_delta_text(event, first_delta_seen=False, existing_text="keep")
        assert result == "keep"

    def test_empty_content_returns_existing(self):
        event = SimpleNamespace(part=SimpleNamespace(content=""))
        result = _capture_pre_first_delta_text(event, first_delta_seen=False, existing_text="old")
        assert result == "old"

    def test_content_with_leading_newline_captured(self):
        # "\nstuff".lstrip() == "stuff", which does not startswith("\n"),
        # so the function returns the truncated content (not existing_text).
        event = SimpleNamespace(part=SimpleNamespace(content="\nstuff"))
        result = _capture_pre_first_delta_text(event, first_delta_seen=False, existing_text="old")
        assert result == "\nstuff"

    def test_long_content_truncated(self):
        long_text = "a" * (DEBUG_STREAM_PREFIX_MAX_LEN + 50)
        event = SimpleNamespace(part=SimpleNamespace(content=long_text))
        result = _capture_pre_first_delta_text(event, first_delta_seen=False, existing_text=None)
        assert result is not None
        assert len(result) == DEBUG_STREAM_PREFIX_MAX_LEN


class TestBuildStreamEventDebugInfo:
    def test_returns_formatted_string(self):
        event = SimpleNamespace(
            delta=SimpleNamespace(content_delta="hello"),
            result=None,
            part=None,
        )
        result = _build_stream_event_debug_info(event, 0)
        assert "[src] event[0]" in result
        assert "etype=SimpleNamespace" in result

    def test_with_result(self):
        event = SimpleNamespace(
            delta=None,
            result=SimpleNamespace(output="done"),
            part=None,
        )
        result = _build_stream_event_debug_info(event, 3)
        assert "event[3]" in result
        assert "rtype=SimpleNamespace" in result

    def test_with_part(self):
        event = SimpleNamespace(
            delta=None,
            result=None,
            part=SimpleNamespace(part_kind="text", content="hi"),
        )
        result = _build_stream_event_debug_info(event, 1)
        assert "pkind=text" in result
        assert "ptype=SimpleNamespace" in result


class TestFormatDebugPreview:
    def test_short_string(self):
        preview, length = _format_debug_preview("hello", 10)
        assert preview == repr("hello")
        assert length == 5

    def test_truncated_at_preview_len(self):
        preview, length = _format_debug_preview("abcdefghij", 5)
        assert preview == repr("abcde")
        assert length == 10

    def test_full_length_returned(self):
        text = "x" * 200
        preview, length = _format_debug_preview(text, 10)
        assert length == 200
        assert preview == repr("x" * 10)


class TestGetDeltaDebugData:
    def test_no_delta(self):
        event = SimpleNamespace(delta=None)
        delta_type, content_len, content_preview = _get_delta_debug_data(event)
        assert delta_type is None
        assert content_len is None
        assert content_preview is None

    def test_delta_without_content_delta(self):
        event = SimpleNamespace(delta=SimpleNamespace())
        delta_type, content_len, content_preview = _get_delta_debug_data(event)
        assert delta_type == "SimpleNamespace"
        assert content_len is None
        assert content_preview is None

    def test_delta_with_non_string_content(self):
        event = SimpleNamespace(delta=SimpleNamespace(content_delta=42))
        delta_type, content_len, _content_preview = _get_delta_debug_data(event)
        assert delta_type == "SimpleNamespace"
        assert content_len is None

    def test_delta_with_string_content(self):
        event = SimpleNamespace(delta=SimpleNamespace(content_delta="hello world"))
        delta_type, content_len, content_preview = _get_delta_debug_data(event)
        assert delta_type == "SimpleNamespace"
        assert content_len == 11
        assert content_preview is not None


class TestGetResultDebugData:
    def test_no_result(self):
        event = SimpleNamespace(result=None)
        result_type, preview, length = _get_result_debug_data(event)
        assert result_type is None
        assert preview is None
        assert length is None

    def test_result_with_output(self):
        event = SimpleNamespace(result=SimpleNamespace(output="done"))
        result_type, preview, length = _get_result_debug_data(event)
        assert result_type == "SimpleNamespace"
        assert length == 4
        assert preview is not None


class TestGetPartDebugData:
    def test_no_part(self):
        event = SimpleNamespace(part=None)
        part_type, part_kind, preview, length = _get_part_debug_data(event)
        assert part_type is None
        assert part_kind is None
        assert preview is None
        assert length is None

    def test_part_with_string_content(self):
        event = SimpleNamespace(part=SimpleNamespace(part_kind="text", content="hi"))
        part_type, part_kind, preview, length = _get_part_debug_data(event)
        assert part_type == "SimpleNamespace"
        assert part_kind == "text"
        assert length == 2
        assert preview is not None

    def test_part_with_non_string_content(self):
        event = SimpleNamespace(part=SimpleNamespace(part_kind="tool-call", content=42))
        part_type, part_kind, preview, length = _get_part_debug_data(event)
        assert part_type == "SimpleNamespace"
        assert part_kind == "tool-call"
        assert preview is None
        assert length is None


def _make_state_manager() -> SimpleNamespace:
    """Create a mock state manager with session._debug_events and _debug_raw_stream_accum."""
    session = SimpleNamespace(
        _debug_events=[],
        _debug_raw_stream_accum="",
    )
    return SimpleNamespace(session=session)


class TestAppendDebugEvent:
    def test_appends_entry(self):
        sm = _make_state_manager()
        _append_debug_event(sm, "event1")
        assert sm.session._debug_events == ["event1"]

    def test_trims_when_over_limit(self):
        sm = _make_state_manager()
        for i in range(DEBUG_STREAM_EVENT_HISTORY_LIMIT + 10):
            _append_debug_event(sm, f"event-{i}")
        assert len(sm.session._debug_events) == DEBUG_STREAM_EVENT_HISTORY_LIMIT


class TestAppendRawStream:
    def test_appends_text(self):
        sm = _make_state_manager()
        _append_raw_stream(sm, "hello")
        assert sm.session._debug_raw_stream_accum == "hello"

    def test_empty_text_noop(self):
        sm = _make_state_manager()
        sm.session._debug_raw_stream_accum = "existing"
        _append_raw_stream(sm, "")
        assert sm.session._debug_raw_stream_accum == "existing"

    def test_truncates_when_over_limit(self):
        sm = _make_state_manager()
        sm.session._debug_raw_stream_accum = "x" * DEBUG_STREAM_RAW_STREAM_MAX_CHARS
        _append_raw_stream(sm, "new")
        assert len(sm.session._debug_raw_stream_accum) == DEBUG_STREAM_RAW_STREAM_MAX_CHARS


class TestLogStreamRequestParts:
    def test_debug_mode_false_returns_early(self):
        # Should not raise even with None node
        _log_stream_request_parts(SimpleNamespace(), False)

    def test_no_request_attr(self):
        _log_stream_request_parts(SimpleNamespace(), True)

    def test_request_with_parts_list(self):
        part = SimpleNamespace(part_kind="text", content="hi", args=None)
        request = SimpleNamespace(parts=[part])
        node = SimpleNamespace(request=request)
        _log_stream_request_parts(node, True)

    def test_request_with_empty_parts(self):
        request = SimpleNamespace(parts=[])
        node = SimpleNamespace(request=request)
        _log_stream_request_parts(node, True)

    def test_request_with_none_parts(self):
        request = SimpleNamespace(parts=None)
        node = SimpleNamespace(request=request)
        _log_stream_request_parts(node, True)

    def test_request_with_non_list_parts(self):
        request = SimpleNamespace(parts="not a list")
        node = SimpleNamespace(request=request)
        _log_stream_request_parts(node, True)
