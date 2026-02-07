"""Tests for tunacode.utils.messaging.adapter."""

from tunacode.types.canonical import (
    CanonicalMessage,
    MessageRole,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThoughtPart,
    ToolCallPart,
    ToolReturnPart,
)
from tunacode.utils.messaging.adapter import (
    PYDANTIC_MESSAGE_KIND_REQUEST,
    PYDANTIC_MESSAGE_KIND_RESPONSE,
    PYDANTIC_PART_KIND_RETRY_PROMPT,
    PYDANTIC_PART_KIND_SYSTEM_PROMPT,
    PYDANTIC_PART_KIND_TEXT,
    PYDANTIC_PART_KIND_TOOL_CALL,
    PYDANTIC_PART_KIND_TOOL_RETURN,
    PYDANTIC_PART_KIND_USER_PROMPT,
    _convert_part_to_canonical,
    _determine_role,
    _fallback_content_parts,
    _get_attr,
    _get_parts,
    _try_legacy_dict,
    find_dangling_tool_calls,
    from_canonical,
    from_canonical_list,
    get_content,
    get_tool_call_ids,
    get_tool_return_ids,
    to_canonical,
    to_canonical_list,
)


class TestGetAttr:
    def test_dict_access(self) -> None:
        assert _get_attr({"key": "val"}, "key") == "val"

    def test_dict_missing_key(self) -> None:
        assert _get_attr({"key": "val"}, "missing") is None

    def test_dict_default(self) -> None:
        assert _get_attr({}, "key", "default") == "default"

    def test_object_access(self) -> None:
        class Obj:
            key = "val"

        assert _get_attr(Obj(), "key") == "val"

    def test_object_missing_attr(self) -> None:
        assert _get_attr(object(), "key") is None


class TestGetParts:
    def test_dict_with_parts_list(self):
        msg = {"parts": [1, 2, 3]}
        assert _get_parts(msg) == [1, 2, 3]

    def test_dict_with_no_parts(self):
        assert _get_parts({}) == []

    def test_dict_with_tuple_parts(self):
        msg = {"parts": (1, 2)}
        assert _get_parts(msg) == [1, 2]

    def test_none_parts(self):
        assert _get_parts({"parts": None}) == []

    def test_object_with_parts_list(self):
        from types import SimpleNamespace

        msg = SimpleNamespace(parts=["a", "b"])
        assert _get_parts(msg) == ["a", "b"]

    def test_object_with_no_parts_attr(self):
        assert _get_parts(object()) == []


class TestConvertPartToCanonical:
    def test_text_part(self):
        part = {"part_kind": PYDANTIC_PART_KIND_TEXT, "content": "hello"}
        result = _convert_part_to_canonical(part)
        assert isinstance(result, TextPart)
        assert result.content == "hello"

    def test_user_prompt_part(self):
        part = {"part_kind": PYDANTIC_PART_KIND_USER_PROMPT, "content": "user says"}
        result = _convert_part_to_canonical(part)
        assert isinstance(result, TextPart)
        assert result.content == "user says"

    def test_tool_call_part(self):
        part = {
            "part_kind": PYDANTIC_PART_KIND_TOOL_CALL,
            "tool_call_id": "tc1",
            "tool_name": "bash",
            "args": {"cmd": "ls"},
        }
        result = _convert_part_to_canonical(part)
        assert isinstance(result, ToolCallPart)
        assert result.tool_call_id == "tc1"
        assert result.tool_name == "bash"
        assert result.args == {"cmd": "ls"}

    def test_tool_return_part(self):
        part = {
            "part_kind": PYDANTIC_PART_KIND_TOOL_RETURN,
            "tool_call_id": "tc1",
            "content": "output",
        }
        result = _convert_part_to_canonical(part)
        assert isinstance(result, ToolReturnPart)
        assert result.tool_call_id == "tc1"
        assert result.content == "output"

    def test_retry_prompt_part(self):
        part = {
            "part_kind": PYDANTIC_PART_KIND_RETRY_PROMPT,
            "tool_call_id": "tc1",
            "tool_name": "bash",
            "content": "retry reason",
        }
        result = _convert_part_to_canonical(part)
        assert isinstance(result, RetryPromptPart)
        assert result.content == "retry reason"
        assert result.tool_call_id == "tc1"
        assert result.tool_name == "bash"

    def test_system_prompt_part(self):
        part = {"part_kind": PYDANTIC_PART_KIND_SYSTEM_PROMPT, "content": "sys prompt"}
        result = _convert_part_to_canonical(part)
        assert isinstance(result, SystemPromptPart)
        assert result.content == "sys prompt"

    def test_unknown_part_returns_none(self):
        part = {"part_kind": "unknown-kind", "content": "x"}
        assert _convert_part_to_canonical(part) is None


class TestDetermineRole:
    def test_request_kind(self):
        msg = {"kind": PYDANTIC_MESSAGE_KIND_REQUEST}
        assert _determine_role(msg) == MessageRole.USER

    def test_response_kind(self):
        msg = {"kind": PYDANTIC_MESSAGE_KIND_RESPONSE}
        assert _determine_role(msg) == MessageRole.ASSISTANT

    def test_role_user(self):
        msg = {"role": "user"}
        assert _determine_role(msg) == MessageRole.USER

    def test_role_assistant(self):
        msg = {"role": "assistant"}
        assert _determine_role(msg) == MessageRole.ASSISTANT

    def test_role_tool(self):
        msg = {"role": "tool"}
        assert _determine_role(msg) == MessageRole.TOOL

    def test_role_system(self):
        msg = {"role": "system"}
        assert _determine_role(msg) == MessageRole.SYSTEM

    def test_default_is_user(self):
        assert _determine_role({}) == MessageRole.USER


class TestTryLegacyDict:
    def test_thought_dict(self):
        msg = {"thought": "I think..."}
        result = _try_legacy_dict(msg)
        assert result is not None
        assert result.role == MessageRole.ASSISTANT
        assert isinstance(result.parts[0], ThoughtPart)
        assert result.parts[0].content == "I think..."

    def test_bare_content_dict(self):
        msg = {"content": "hello"}
        result = _try_legacy_dict(msg)
        assert result is not None
        assert result.role == MessageRole.USER
        assert result.parts[0].content == "hello"

    def test_dict_with_parts_returns_none(self):
        msg = {"content": "hello", "parts": []}
        assert _try_legacy_dict(msg) is None

    def test_dict_with_kind_returns_none(self):
        msg = {"content": "hello", "kind": "request"}
        assert _try_legacy_dict(msg) is None

    def test_non_string_content_returns_none(self):
        msg = {"content": ["list", "content"]}
        assert _try_legacy_dict(msg) is None


class TestFallbackContentParts:
    def test_string_content(self):
        result = _fallback_content_parts({"content": "hello"})
        assert len(result) == 1
        assert result[0].content == "hello"

    def test_list_of_strings(self):
        result = _fallback_content_parts({"content": ["a", "b"]})
        assert len(result) == 2
        assert result[0].content == "a"
        assert result[1].content == "b"

    def test_list_of_dicts_with_text(self):
        result = _fallback_content_parts({"content": [{"text": "hi"}]})
        assert len(result) == 1
        assert result[0].content == "hi"

    def test_empty_content(self):
        assert _fallback_content_parts({"content": ""}) == []

    def test_none_content(self):
        assert _fallback_content_parts({"content": None}) == []

    def test_no_content_key(self):
        assert _fallback_content_parts({}) == []


class TestToCanonical:
    def test_request_with_text_parts(self):
        msg = {
            "kind": "request",
            "parts": [{"part_kind": "text", "content": "hello"}],
        }
        result = to_canonical(msg)
        assert result.role == MessageRole.USER
        assert len(result.parts) == 1
        assert result.parts[0].content == "hello"

    def test_response_with_text_parts(self):
        msg = {
            "kind": "response",
            "parts": [{"part_kind": "text", "content": "answer"}],
        }
        result = to_canonical(msg)
        assert result.role == MessageRole.ASSISTANT

    def test_legacy_thought_dict(self):
        msg = {"thought": "reasoning"}
        result = to_canonical(msg)
        assert isinstance(result.parts[0], ThoughtPart)

    def test_fallback_to_content(self):
        msg = {"kind": "request", "content": "fallback text"}
        result = to_canonical(msg)
        assert result.parts[0].content == "fallback text"

    def test_empty_message(self):
        result = to_canonical({})
        assert result.role == MessageRole.USER
        assert len(result.parts) == 0

    def test_filters_unknown_parts(self):
        msg = {
            "kind": "request",
            "parts": [
                {"part_kind": "text", "content": "ok"},
                {"part_kind": "unknown", "content": "skip"},
            ],
        }
        result = to_canonical(msg)
        assert len(result.parts) == 1


class TestToCanonicalList:
    def test_converts_list(self):
        msgs = [
            {"kind": "request", "parts": [{"part_kind": "text", "content": "a"}]},
            {"kind": "response", "parts": [{"part_kind": "text", "content": "b"}]},
        ]
        result = to_canonical_list(msgs)
        assert len(result) == 2
        assert result[0].role == MessageRole.USER
        assert result[1].role == MessageRole.ASSISTANT

    def test_empty_list(self):
        assert to_canonical_list([]) == []


class TestFromCanonical:
    def test_text_part_roundtrip(self):
        msg = CanonicalMessage(
            role=MessageRole.USER,
            parts=(TextPart(content="hello"),),
        )
        result = from_canonical(msg)
        assert result["kind"] == PYDANTIC_MESSAGE_KIND_REQUEST
        assert len(result["parts"]) == 1
        assert result["parts"][0]["part_kind"] == PYDANTIC_PART_KIND_TEXT

    def test_assistant_response(self):
        msg = CanonicalMessage(
            role=MessageRole.ASSISTANT,
            parts=(TextPart(content="answer"),),
        )
        result = from_canonical(msg)
        assert result["kind"] == PYDANTIC_MESSAGE_KIND_RESPONSE

    def test_system_message_is_request(self):
        msg = CanonicalMessage(
            role=MessageRole.SYSTEM,
            parts=(SystemPromptPart(content="sys"),),
        )
        result = from_canonical(msg)
        assert result["kind"] == PYDANTIC_MESSAGE_KIND_REQUEST
        assert result["parts"][0]["part_kind"] == PYDANTIC_PART_KIND_SYSTEM_PROMPT

    def test_tool_call_part(self):
        msg = CanonicalMessage(
            role=MessageRole.ASSISTANT,
            parts=(ToolCallPart(tool_call_id="tc1", tool_name="bash", args={"cmd": "ls"}),),
        )
        result = from_canonical(msg)
        part = result["parts"][0]
        assert part["part_kind"] == PYDANTIC_PART_KIND_TOOL_CALL
        assert part["tool_name"] == "bash"

    def test_tool_return_part(self):
        msg = CanonicalMessage(
            role=MessageRole.USER,
            parts=(ToolReturnPart(tool_call_id="tc1", content="output"),),
        )
        result = from_canonical(msg)
        part = result["parts"][0]
        assert part["part_kind"] == PYDANTIC_PART_KIND_TOOL_RETURN

    def test_retry_prompt_part(self):
        msg = CanonicalMessage(
            role=MessageRole.USER,
            parts=(RetryPromptPart(tool_call_id="tc1", tool_name="bash", content="retry"),),
        )
        result = from_canonical(msg)
        part = result["parts"][0]
        assert part["part_kind"] == PYDANTIC_PART_KIND_RETRY_PROMPT

    def test_thought_part_becomes_text(self):
        msg = CanonicalMessage(
            role=MessageRole.ASSISTANT,
            parts=(ThoughtPart(content="thinking"),),
        )
        result = from_canonical(msg)
        part = result["parts"][0]
        assert part["part_kind"] == PYDANTIC_PART_KIND_TEXT
        assert part["content"] == "thinking"


class TestFromCanonicalList:
    def test_converts_list(self):
        msgs = [
            CanonicalMessage(role=MessageRole.USER, parts=(TextPart(content="a"),)),
            CanonicalMessage(role=MessageRole.ASSISTANT, parts=(TextPart(content="b"),)),
        ]
        result = from_canonical_list(msgs)
        assert len(result) == 2

    def test_empty_list(self):
        assert from_canonical_list([]) == []


class TestGetContent:
    def test_from_canonical_message(self):
        msg = CanonicalMessage(
            role=MessageRole.USER,
            parts=(TextPart(content="hello"), TextPart(content="world")),
        )
        assert get_content(msg) == "hello world"

    def test_from_dict(self):
        msg = {
            "kind": "request",
            "parts": [{"part_kind": "text", "content": "hello"}],
        }
        assert get_content(msg) == "hello"


class TestGetToolCallIds:
    def test_extracts_ids_from_canonical(self):
        msg = CanonicalMessage(
            role=MessageRole.ASSISTANT,
            parts=(
                ToolCallPart(tool_call_id="tc1", tool_name="bash", args={}),
                ToolCallPart(tool_call_id="tc2", tool_name="grep", args={}),
            ),
        )
        assert get_tool_call_ids(msg) == {"tc1", "tc2"}

    def test_extracts_ids_from_dict(self):
        msg = {
            "kind": "response",
            "parts": [
                {"part_kind": "tool-call", "tool_call_id": "tc1", "tool_name": "x", "args": {}},
            ],
        }
        assert get_tool_call_ids(msg) == {"tc1"}


class TestGetToolReturnIds:
    def test_extracts_return_ids(self):
        msg = CanonicalMessage(
            role=MessageRole.USER,
            parts=(ToolReturnPart(tool_call_id="tc1", content="output"),),
        )
        assert get_tool_return_ids(msg) == {"tc1"}

    def test_extracts_return_ids_from_dict(self):
        msg = {
            "kind": "request",
            "parts": [
                {"part_kind": "tool-return", "tool_call_id": "tc1", "content": "ok"},
                {"part_kind": "tool-return", "tool_call_id": "tc2", "content": "ok"},
            ],
        }
        assert get_tool_return_ids(msg) == {"tc1", "tc2"}


class TestFindDanglingToolCalls:
    def test_no_dangling(self):
        msgs = [
            CanonicalMessage(
                role=MessageRole.ASSISTANT,
                parts=(ToolCallPart(tool_call_id="tc1", tool_name="x", args={}),),
            ),
            CanonicalMessage(
                role=MessageRole.USER,
                parts=(ToolReturnPart(tool_call_id="tc1", content="ok"),),
            ),
        ]
        assert find_dangling_tool_calls(msgs) == set()

    def test_has_dangling(self):
        msgs = [
            CanonicalMessage(
                role=MessageRole.ASSISTANT,
                parts=(
                    ToolCallPart(tool_call_id="tc1", tool_name="x", args={}),
                    ToolCallPart(tool_call_id="tc2", tool_name="y", args={}),
                ),
            ),
            CanonicalMessage(
                role=MessageRole.USER,
                parts=(ToolReturnPart(tool_call_id="tc1", content="ok"),),
            ),
        ]
        assert find_dangling_tool_calls(msgs) == {"tc2"}

    def test_empty_list(self):
        assert find_dangling_tool_calls([]) == set()

    def test_works_with_dicts(self):
        msgs = [
            {
                "kind": "response",
                "parts": [
                    {"part_kind": "tool-call", "tool_call_id": "tc1", "tool_name": "x", "args": {}},
                ],
            },
        ]
        assert find_dangling_tool_calls(msgs) == {"tc1"}
