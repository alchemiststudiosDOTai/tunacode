"""Tests for tunacode.tools.parsing.command_parser."""

import pytest

from tunacode.exceptions import ValidationError

from tunacode.tools.parsing.command_parser import (
    ARG_ERROR_PREVIEW_LIMIT,
    _parse_json_args,
    _preview_json,
    parse_args,
)


class TestPreviewJson:
    def test_short_string_returned_as_is(self):
        result = _preview_json("short")
        assert result == "short"

    def test_exact_limit_no_truncation(self):
        value = "x" * ARG_ERROR_PREVIEW_LIMIT
        result = _preview_json(value)
        assert result == value
        assert "..." not in result

    def test_long_string_truncated_with_ellipsis(self):
        value = "y" * (ARG_ERROR_PREVIEW_LIMIT + 50)
        result = _preview_json(value)
        assert result.endswith("...")
        expected_prefix = "y" * ARG_ERROR_PREVIEW_LIMIT
        assert result == f"{expected_prefix}..."

    def test_empty_string(self):
        result = _preview_json("")
        assert result == ""


class TestParseJsonArgs:
    def test_valid_json_dict(self):
        result = _parse_json_args('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_empty_dict(self):
        result = _parse_json_args("{}")
        assert result == {}

    def test_invalid_json_raises_validation_error(self):
        with pytest.raises(ValidationError):
            _parse_json_args("{not valid json}")

    def test_non_dict_json_raises_validation_error(self):
        with pytest.raises(ValidationError, match="expected object"):
            _parse_json_args("[1, 2, 3]")

    def test_non_dict_string_raises_validation_error(self):
        with pytest.raises(ValidationError, match="expected object"):
            _parse_json_args('"just a string"')

    def test_non_dict_number_raises_validation_error(self):
        with pytest.raises(ValidationError, match="expected object"):
            _parse_json_args("42")

    def test_invalid_json_error_includes_preview(self):
        bad_json = "x" * 300
        with pytest.raises(ValidationError, match="Invalid JSON"):
            _parse_json_args(bad_json)

    def test_concatenated_invalid_with_long_preview(self):
        raw = '{"a": 1}{"b": "' + "x" * 300 + '"}'
        with pytest.raises(ValidationError):
            _parse_json_args(raw)

    def test_nested_dict(self):
        result = _parse_json_args('{"a": {"b": {"c": 1}}}')
        assert result == {"a": {"b": {"c": 1}}}

    def test_concatenated_json_single_valid_recovered(self):
        # Second object is invalid JSON, so only the first is recovered
        result = _parse_json_args('{"a": 1}{not json}')
        assert result == {"a": 1}

    def test_concatenated_json_multiple_valid_raises(self):
        # Two valid objects triggers ConcatenatedJSONError -> ValidationError
        with pytest.raises(ValidationError):
            _parse_json_args('{"a": 1}{"b": 2}')


class TestParseArgs:
    @pytest.mark.asyncio
    async def test_dict_passed_through(self):
        input_dict = {"key": "value"}
        result = await parse_args(input_dict)
        assert result is input_dict

    @pytest.mark.asyncio
    async def test_valid_json_string_parsed(self):
        result = await parse_args('{"key": "value"}')
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_invalid_json_string_raises(self):
        with pytest.raises(ValidationError):
            await parse_args("{bad json}")

    @pytest.mark.asyncio
    async def test_invalid_type_int_raises(self):
        with pytest.raises(ValidationError, match="Invalid args type"):
            await parse_args(42)

    @pytest.mark.asyncio
    async def test_invalid_type_list_raises(self):
        with pytest.raises(ValidationError, match="Invalid args type"):
            await parse_args([1, 2, 3])

    @pytest.mark.asyncio
    async def test_invalid_type_none_raises(self):
        with pytest.raises(ValidationError, match="Invalid args type"):
            await parse_args(None)

    @pytest.mark.asyncio
    async def test_empty_dict_passed_through(self):
        result = await parse_args({})
        assert result == {}

    @pytest.mark.asyncio
    async def test_empty_json_string_parsed(self):
        result = await parse_args("{}")
        assert result == {}
