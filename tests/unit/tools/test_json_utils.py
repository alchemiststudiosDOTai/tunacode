"""Tests for tunacode.tools.parsing.json_utils."""

import json

import pytest

from tunacode.tools.parsing.json_utils import (
    ConcatenatedJSONError,
    _advance_json_state,
    _try_collect_object,
    safe_json_parse,
    split_concatenated_json,
    validate_tool_args_safety,
)


class TestAdvanceJsonState:
    def test_escape_next_true(self):
        escape, in_str, skip = _advance_json_state("n", True, True)
        assert escape is False
        assert in_str is True
        assert skip is True

    def test_backslash_sets_escape(self):
        escape, _in_str, skip = _advance_json_state("\\", False, False)
        assert escape is True
        assert skip is True

    def test_quote_toggles_string(self):
        _escape, in_str, skip = _advance_json_state('"', False, False)
        assert in_str is True
        assert skip is True

        _escape, in_str, skip = _advance_json_state('"', False, True)
        assert in_str is False

    def test_in_string_skips(self):
        _escape, _in_str, skip = _advance_json_state("{", False, True)
        assert skip is True

    def test_brace_outside_string(self):
        _escape, _in_str, skip = _advance_json_state("{", False, False)
        assert skip is False


class TestTryCollectObject:
    def test_valid_dict(self):
        objects: list = []
        _try_collect_object('{"a": 1}', 0, 7, objects)
        assert len(objects) == 1
        assert objects[0] == {"a": 1}

    def test_invalid_json(self):
        objects: list = []
        _try_collect_object("{bad}", 0, 4, objects)
        assert len(objects) == 0

    def test_non_dict_json(self):
        objects: list = []
        _try_collect_object("[1, 2]", 0, 5, objects)
        assert len(objects) == 0


class TestSplitConcatenatedJson:
    def test_single_object(self):
        result = split_concatenated_json('{"a": 1}')
        assert len(result) == 1
        assert result[0] == {"a": 1}

    def test_two_concatenated(self):
        result = split_concatenated_json('{"a": 1}{"b": 2}')
        assert len(result) == 2
        assert result[0] == {"a": 1}
        assert result[1] == {"b": 2}

    def test_with_whitespace(self):
        result = split_concatenated_json('  {"a": 1}  {"b": 2}  ')
        assert len(result) == 2

    def test_nested_braces(self):
        result = split_concatenated_json('{"a": {"b": 1}}')
        assert len(result) == 1
        assert result[0] == {"a": {"b": 1}}

    def test_string_with_braces(self):
        result = split_concatenated_json('{"a": "x{y}z"}')
        assert len(result) == 1
        assert result[0] == {"a": "x{y}z"}

    def test_no_valid_objects_raises(self):
        with pytest.raises(json.JSONDecodeError, match="No valid"):
            split_concatenated_json("not json at all")

    def test_escaped_quotes(self):
        result = split_concatenated_json('{"a": "he said \\"hi\\""}')
        assert len(result) == 1


class TestValidateToolArgsSafety:
    def test_single_object_is_safe(self):
        assert validate_tool_args_safety([{"a": 1}]) is True

    def test_empty_list_is_safe(self):
        assert validate_tool_args_safety([]) is True

    def test_multiple_objects_raises(self):
        with pytest.raises(ConcatenatedJSONError):
            validate_tool_args_safety([{"a": 1}, {"b": 2}])

    def test_multiple_objects_includes_tool_name(self):
        with pytest.raises(ConcatenatedJSONError) as exc_info:
            validate_tool_args_safety([{"a": 1}, {"b": 2}], tool_name="bash")
        assert exc_info.value.tool_name == "bash"
        assert exc_info.value.objects_found == 2


class TestSafeJsonParse:
    def test_valid_json(self):
        result = safe_json_parse('{"a": 1}')
        assert result == {"a": 1}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            safe_json_parse("{invalid}")

    def test_non_dict_raises(self):
        with pytest.raises(json.JSONDecodeError, match="Expected dict"):
            safe_json_parse("[1, 2, 3]")

    def test_concatenated_not_allowed_by_default(self):
        with pytest.raises(json.JSONDecodeError):
            safe_json_parse('{"a": 1}{"b": 2}')

    def test_concatenated_raises_for_multiple(self):
        with pytest.raises(ConcatenatedJSONError):
            safe_json_parse('{"a": 1}{"b": 2}', allow_concatenated=True)

    def test_extra_data_recovery_single_object(self):
        result = safe_json_parse('{"a": 1}  not json', allow_concatenated=True)
        assert result == {"a": 1}


class TestConcatenatedJSONError:
    def test_attributes(self):
        err = ConcatenatedJSONError("msg", 3, "bash")
        assert err.message == "msg"
        assert err.objects_found == 3
        assert err.tool_name == "bash"
