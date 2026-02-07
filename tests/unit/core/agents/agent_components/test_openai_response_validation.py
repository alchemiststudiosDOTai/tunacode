"""Tests for tunacode.core.agents.agent_components.openai_response_validation."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from tunacode.exceptions import AgentError

from tunacode.core.agents.agent_components.openai_response_validation import (
    DEFAULT_ERROR_MESSAGE,
    UNKNOWN_MODEL_NAME,
    UNKNOWN_PROVIDER_NAME,
    _collect_missing_fields,
    _extract_error_payload,
    _extract_model_name,
    _extract_provider_name,
    _format_error_details,
    _format_error_message,
    _is_chat_completion_request,
    _is_streaming_response,
    _load_request_payload,
    _normalize_payload,
    _read_response_payload,
    validate_openai_chat_completion_response,
)


def _make_response(
    url_path: str = "/v1/chat/completions",
    content_type: str = "application/json",
    body: bytes = b"",
    host: str = "api.openai.com",
    request_body: bytes = b"",
) -> MagicMock:
    response = MagicMock()
    response.request.url.path = url_path
    response.request.url.host = host
    response.request.content = request_body
    response.headers = {"content-type": content_type}
    response.content = body
    response.aread = AsyncMock()
    return response


class TestIsChatCompletionRequest:
    def test_true_for_chat_completions(self):
        resp = _make_response(url_path="/v1/chat/completions")
        assert _is_chat_completion_request(resp) is True

    def test_false_for_other_paths(self):
        resp = _make_response(url_path="/v1/embeddings")
        assert _is_chat_completion_request(resp) is False

    def test_false_when_no_request(self):
        resp = MagicMock()
        resp.request = None
        assert _is_chat_completion_request(resp) is False


class TestIsStreamingResponse:
    def test_true_for_event_stream(self):
        resp = _make_response(content_type="text/event-stream")
        assert _is_streaming_response(resp) is True

    def test_false_for_json(self):
        resp = _make_response(content_type="application/json")
        assert _is_streaming_response(resp) is False

    def test_case_insensitive(self):
        resp = _make_response(content_type="Text/Event-Stream")
        assert _is_streaming_response(resp) is True


class TestReadResponsePayload:
    @pytest.mark.asyncio
    async def test_valid_json(self):
        body = json.dumps({"id": "123"}).encode()
        resp = _make_response(body=body)
        result = await _read_response_payload(resp)
        assert result == {"id": "123"}

    @pytest.mark.asyncio
    async def test_empty_body(self):
        resp = _make_response(body=b"")
        result = await _read_response_payload(resp)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        resp = _make_response(body=b"not json")
        result = await _read_response_payload(resp)
        assert result is None


class TestNormalizePayload:
    def test_dict_returned_as_is(self):
        assert _normalize_payload({"a": 1}) == {"a": 1}

    def test_non_dict_wrapped(self):
        result = _normalize_payload("string_payload")
        assert result == {"_payload": "string_payload"}

    def test_list_wrapped(self):
        result = _normalize_payload([1, 2])
        assert result == {"_payload": [1, 2]}


class TestExtractErrorPayload:
    def test_no_error_field(self):
        assert _extract_error_payload({"id": "123"}) is None

    def test_dict_error(self):
        payload = {"error": {"message": "bad request", "type": "invalid_request"}}
        result = _extract_error_payload(payload)
        assert result == {"message": "bad request", "type": "invalid_request"}

    def test_non_dict_error(self):
        payload = {"error": "something went wrong"}
        result = _extract_error_payload(payload)
        assert result == {"message": "something went wrong"}


class TestFormatErrorDetails:
    def test_empty_payload(self):
        assert _format_error_details({}) is None

    def test_with_type(self):
        result = _format_error_details({"type": "invalid_request"})
        assert "type=invalid_request" in result

    def test_with_code(self):
        result = _format_error_details({"code": "rate_limit"})
        assert "code=rate_limit" in result

    def test_with_param(self):
        result = _format_error_details({"param": "model"})
        assert "param=model" in result

    def test_all_details(self):
        result = _format_error_details({"type": "t", "code": "c", "param": "p"})
        assert "type=t" in result
        assert "code=c" in result
        assert "param=p" in result


class TestFormatErrorMessage:
    def test_with_message(self):
        result = _format_error_message({"message": "oops"})
        assert "oops" in result

    def test_default_message(self):
        result = _format_error_message({})
        assert DEFAULT_ERROR_MESSAGE in result

    def test_with_details(self):
        result = _format_error_message({"message": "oops", "type": "err"})
        assert "oops" in result
        assert "type=err" in result


class TestCollectMissingFields:
    def test_valid_response(self):
        payload = {
            "id": "chatcmpl-123",
            "choices": [{"message": {}}],
            "model": "gpt-4",
            "object": "chat.completion",
        }
        assert _collect_missing_fields(payload) == []

    def test_all_missing(self):
        missing = _collect_missing_fields({})
        assert "id" in missing
        assert "choices" in missing
        assert "model" in missing
        assert "object" in missing

    def test_empty_choices(self):
        payload = {"id": "x", "choices": [], "model": "gpt-4", "object": "chat.completion"}
        missing = _collect_missing_fields(payload)
        assert "choices" in missing

    def test_wrong_object(self):
        payload = {"id": "x", "choices": [{}], "model": "gpt-4", "object": "wrong"}
        missing = _collect_missing_fields(payload)
        assert "object" in missing


class TestExtractProviderName:
    def test_from_host(self):
        resp = _make_response(host="api.openai.com")
        assert _extract_provider_name(resp) == "api.openai.com"

    def test_no_request(self):
        resp = MagicMock()
        resp.request = None
        assert _extract_provider_name(resp) == UNKNOWN_PROVIDER_NAME

    def test_empty_host_uses_url(self):
        resp = _make_response(host="")
        result = _extract_provider_name(resp)
        assert result == str(resp.request.url)


class TestExtractModelName:
    def test_from_request_body(self):
        body = json.dumps({"model": "gpt-4"}).encode()
        resp = _make_response(request_body=body)
        assert _extract_model_name(resp) == "gpt-4"

    def test_no_request(self):
        resp = MagicMock()
        resp.request = None
        assert _extract_model_name(resp) == UNKNOWN_MODEL_NAME

    def test_invalid_request_body(self):
        resp = _make_response(request_body=b"not json")
        assert _extract_model_name(resp) == UNKNOWN_MODEL_NAME

    def test_no_model_in_body(self):
        body = json.dumps({"messages": []}).encode()
        resp = _make_response(request_body=body)
        assert _extract_model_name(resp) == UNKNOWN_MODEL_NAME


class TestLoadRequestPayload:
    def test_bytes(self):
        result = _load_request_payload(b'{"a": 1}')
        assert result == {"a": 1}

    def test_string(self):
        result = _load_request_payload('{"a": 1}')
        assert result == {"a": 1}

    def test_none(self):
        assert _load_request_payload(None) is None

    def test_empty_bytes(self):
        assert _load_request_payload(b"") is None

    def test_invalid_json(self):
        assert _load_request_payload(b"nope") is None

    def test_other_type(self):
        result = _load_request_payload(123)
        assert result == 123


class TestValidateOpenAIChatCompletionResponse:
    @pytest.mark.asyncio
    async def test_skips_non_chat_completion(self):
        resp = _make_response(url_path="/v1/embeddings")
        await validate_openai_chat_completion_response(resp)

    @pytest.mark.asyncio
    async def test_skips_streaming(self):
        resp = _make_response(content_type="text/event-stream")
        await validate_openai_chat_completion_response(resp)

    @pytest.mark.asyncio
    async def test_skips_empty_body(self):
        resp = _make_response(body=b"")
        await validate_openai_chat_completion_response(resp)

    @pytest.mark.asyncio
    async def test_raises_on_error_payload(self):
        body = json.dumps({"error": {"message": "bad request"}}).encode()
        resp = _make_response(body=body)
        with pytest.raises(AgentError, match="bad request"):
            await validate_openai_chat_completion_response(resp)

    @pytest.mark.asyncio
    async def test_raises_on_missing_fields(self):
        body = json.dumps({"not_a_valid": "response"}).encode()
        resp = _make_response(body=body)
        with pytest.raises(AgentError, match="missing fields"):
            await validate_openai_chat_completion_response(resp)

    @pytest.mark.asyncio
    async def test_passes_valid_response(self):
        body = json.dumps(
            {
                "id": "chatcmpl-123",
                "choices": [{"message": {"content": "hello"}}],
                "model": "gpt-4",
                "object": "chat.completion",
            }
        ).encode()
        resp = _make_response(body=body)
        await validate_openai_chat_completion_response(resp)
