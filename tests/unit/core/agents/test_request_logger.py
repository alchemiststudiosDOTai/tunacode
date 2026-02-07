"""Tests for tunacode.core.agents.request_logger."""

from types import SimpleNamespace

from tunacode.core.agents.request_logger import (
    DEBUG_HISTORY_PARTS_LIMIT,
    DEBUG_HISTORY_SAMPLE_SIZE,
    _format_parts_summary,
    log_history_state,
    log_node_details,
    log_run_handle_context_messages,
    log_sanitized_history_state,
    message_has_tool_calls,
)


class TestFormatPartsSummary:
    def test_empty_list_returns_empty(self):
        result = _format_parts_summary([])
        assert result == []

    def test_part_with_string_content_shows_char_count(self):
        part = SimpleNamespace(part_kind="text", content="hello world")
        result = _format_parts_summary([part])
        assert len(result) == 1
        assert result[0] == "text:11chars"

    def test_part_without_content(self):
        part = SimpleNamespace(part_kind="tool-call")
        result = _format_parts_summary([part])
        assert len(result) == 1
        assert result[0] == "tool-call"

    def test_part_with_non_string_content(self):
        part = SimpleNamespace(part_kind="tool-return", content=42)
        result = _format_parts_summary([part])
        assert len(result) == 1
        assert result[0] == "tool-return"

    def test_part_with_none_content(self):
        part = SimpleNamespace(part_kind="tool-call", content=None)
        result = _format_parts_summary([part])
        assert len(result) == 1
        assert result[0] == "tool-call"

    def test_multiple_parts(self):
        parts = [
            SimpleNamespace(part_kind="text", content="abc"),
            SimpleNamespace(part_kind="tool-call"),
            SimpleNamespace(part_kind="tool-return", content="result data"),
        ]
        result = _format_parts_summary(parts)
        assert len(result) == 3
        assert result[0] == "text:3chars"
        assert result[1] == "tool-call"
        assert result[2] == "tool-return:11chars"

    def test_respects_parts_limit(self):
        parts = [
            SimpleNamespace(part_kind=f"part-{i}", content=f"content-{i}")
            for i in range(DEBUG_HISTORY_PARTS_LIMIT + 3)
        ]
        result = _format_parts_summary(parts)
        assert len(result) == DEBUG_HISTORY_PARTS_LIMIT

    def test_part_with_missing_part_kind_uses_fallback(self):
        part = SimpleNamespace(content="some text")
        result = _format_parts_summary([part])
        assert len(result) == 1
        # getattr with default "?" when part_kind is missing
        assert result[0] == "?:9chars"

    def test_empty_string_content_shows_zero_chars(self):
        part = SimpleNamespace(part_kind="text", content="")
        result = _format_parts_summary([part])
        assert len(result) == 1
        assert result[0] == "text:0chars"


class TestMessageHasToolCalls:
    def test_object_with_tool_calls_list(self):
        message = SimpleNamespace(
            tool_calls=[SimpleNamespace(tool_name="bash")],
            parts=[],
        )
        assert message_has_tool_calls(message) is True

    def test_object_with_tool_call_part_kind(self):
        part = SimpleNamespace(part_kind="tool-call")
        message = SimpleNamespace(tool_calls=[], parts=[part])
        assert message_has_tool_calls(message) is True

    def test_dict_with_tool_calls(self):
        message = {
            "tool_calls": [{"tool_name": "bash"}],
            "parts": [],
        }
        assert message_has_tool_calls(message) is True

    def test_dict_with_tool_call_part_kind(self):
        message = {
            "tool_calls": [],
            "parts": [{"part_kind": "tool-call"}],
        }
        assert message_has_tool_calls(message) is True

    def test_message_with_no_tool_calls_returns_false(self):
        message = SimpleNamespace(
            tool_calls=[],
            parts=[SimpleNamespace(part_kind="text")],
        )
        assert message_has_tool_calls(message) is False

    def test_dict_with_no_tool_calls_returns_false(self):
        message = {
            "tool_calls": [],
            "parts": [{"part_kind": "text"}],
        }
        assert message_has_tool_calls(message) is False

    def test_object_with_no_parts_or_tool_calls_attrs(self):
        message = SimpleNamespace()
        assert message_has_tool_calls(message) is False

    def test_dict_with_empty_keys(self):
        message = {}
        assert message_has_tool_calls(message) is False

    def test_object_with_none_tool_calls(self):
        message = SimpleNamespace(tool_calls=None, parts=[])
        assert message_has_tool_calls(message) is False

    def test_dict_parts_with_non_dict_parts(self):
        """Dict message with object parts that have part_kind attribute."""
        part = SimpleNamespace(part_kind="tool-call")
        message = {
            "tool_calls": [],
            "parts": [part],
        }
        # The part is not a dict, so getattr is used
        assert message_has_tool_calls(message) is True

    def test_mixed_parts_first_is_text_second_is_tool_call(self):
        message = SimpleNamespace(
            tool_calls=[],
            parts=[
                SimpleNamespace(part_kind="text"),
                SimpleNamespace(part_kind="tool-call"),
            ],
        )
        assert message_has_tool_calls(message) is True


class TestLogHistoryState:
    def test_empty_messages_returns_early(self):
        logger = SimpleNamespace(debug=lambda msg: None)
        log_history_state([], 0, logger)

    def test_single_message_logs_state(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        msg = SimpleNamespace(kind="request", parts=[], tool_calls=[])
        log_history_state([msg], 1, logger)
        assert len(calls) >= 1
        assert "History state" in calls[0]
        assert "has_tool_calls" in calls[0]

    def test_multiple_messages_logs_sample(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        msgs = [SimpleNamespace(kind=f"msg-{i}", parts=[], tool_calls=[]) for i in range(5)]
        log_history_state(msgs, 5, logger)
        # Should log state line + sample lines
        assert len(calls) >= 1 + min(DEBUG_HISTORY_SAMPLE_SIZE, 5)

    def test_message_with_tool_calls_detected(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        msg = SimpleNamespace(
            kind="request",
            parts=[SimpleNamespace(part_kind="tool-call")],
            tool_calls=[],
        )
        log_history_state([msg], 1, logger)
        assert "has_tool_calls=True" in calls[0]


class TestLogSanitizedHistoryState:
    def test_debug_mode_false_returns_early(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        log_sanitized_history_state([SimpleNamespace()], debug_mode=False, logger=logger)
        assert len(calls) == 0

    def test_empty_history_logs_count(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        log_sanitized_history_state([], debug_mode=True, logger=logger)
        assert len(calls) >= 1
        assert "count=0" in calls[0]

    def test_single_message_logs_first(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        msg = SimpleNamespace(kind="request")
        log_sanitized_history_state([msg], debug_mode=True, logger=logger)
        assert any("message_history[0]" in c for c in calls)

    def test_two_messages_logs_first_and_last(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        msgs = [SimpleNamespace(kind="request"), SimpleNamespace(kind="response")]
        log_sanitized_history_state(msgs, debug_mode=True, logger=logger)
        assert any("message_history[0]" in c for c in calls)
        assert any("message_history[-1]" in c for c in calls)


class TestLogRunHandleContextMessages:
    def test_no_ctx_attr_returns_early(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        run_handle = SimpleNamespace()
        log_run_handle_context_messages(run_handle, logger)
        assert len(calls) == 0

    def test_ctx_with_messages(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        ctx = SimpleNamespace(messages=[SimpleNamespace()])
        run_handle = SimpleNamespace(ctx=ctx)
        log_run_handle_context_messages(run_handle, logger)
        assert any("ctx.messages count=1" in c for c in calls)

    def test_ctx_with_empty_messages(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        ctx = SimpleNamespace(messages=[])
        run_handle = SimpleNamespace(ctx=ctx)
        log_run_handle_context_messages(run_handle, logger)
        assert any("count=0" in c for c in calls)

    def test_ctx_messages_none_falls_back_to_state(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        state = SimpleNamespace(message_history=[SimpleNamespace(), SimpleNamespace()])
        ctx = SimpleNamespace(messages=None, state=state)
        run_handle = SimpleNamespace(ctx=ctx)
        log_run_handle_context_messages(run_handle, logger)
        assert any("count=2" in c for c in calls)

    def test_ctx_no_messages_no_state_logs_not_found(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        ctx = SimpleNamespace(messages=None, state=None)
        run_handle = SimpleNamespace(ctx=ctx)
        log_run_handle_context_messages(run_handle, logger)
        assert any("not found" in c for c in calls)


class TestLogNodeDetails:
    def test_basic_node(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        node = SimpleNamespace(request=None, model_response=None, thought=None)
        log_node_details(node, logger)
        assert len(calls) == 1
        assert "has_request=False" in calls[0]
        assert "has_response=False" in calls[0]

    def test_node_with_all_attrs(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        node = SimpleNamespace(
            request=SimpleNamespace(),
            model_response=SimpleNamespace(),
            thought="thinking...",
        )
        log_node_details(node, logger)
        assert "has_request=True" in calls[0]
        assert "has_response=True" in calls[0]
        assert "has_thought=True" in calls[0]

    def test_node_type_name_logged(self):
        calls = []
        logger = SimpleNamespace(debug=lambda msg: calls.append(msg))
        node = SimpleNamespace(request=None, model_response=None, thought=None)
        log_node_details(node, logger)
        assert "SimpleNamespace" in calls[0]
