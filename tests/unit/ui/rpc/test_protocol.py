"""Unit tests for RPC protocol parsing and response helpers."""

from __future__ import annotations

import pytest

from tunacode.ui.rpc.protocol import (
    RPC_CODE_INVALID_COMMAND,
    RPC_CODE_INVALID_PARAMS,
    PromptCommand,
    RpcProtocolError,
    error_response,
    parse_command,
)


def test_parse_prompt_command() -> None:
    command = parse_command({"id": "1", "command": "prompt", "prompt": "hello"})

    assert isinstance(command, PromptCommand)
    assert command.request_id == "1"
    assert command.command == "prompt"
    assert command.prompt == "hello"


def test_parse_command_rejects_unknown_command() -> None:
    with pytest.raises(RpcProtocolError) as excinfo:
        parse_command({"id": "1", "command": "unknown"})

    assert excinfo.value.code == RPC_CODE_INVALID_COMMAND
    assert excinfo.value.command == "unknown"


def test_parse_command_requires_string_fields() -> None:
    with pytest.raises(RpcProtocolError) as excinfo:
        parse_command({"id": "1", "command": "set_model", "model": ""})

    assert excinfo.value.code == RPC_CODE_INVALID_PARAMS


def test_error_response_preserves_structure() -> None:
    response = error_response(
        RpcProtocolError(
            code=RPC_CODE_INVALID_PARAMS,
            message="bad input",
            command="prompt",
            request_id="123",
        )
    )

    assert response == {
        "id": "123",
        "type": "response",
        "command": "prompt",
        "success": False,
        "error": {
            "code": RPC_CODE_INVALID_PARAMS,
            "message": "bad input",
        },
    }
