"""Wire protocol definitions and validation for TunaCode RPC mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RPC_TYPE_RESPONSE = "response"
RPC_COMMAND_INVALID = "invalid"

RPC_CODE_BUSY = "busy"
RPC_CODE_INVALID_COMMAND = "invalid_command"
RPC_CODE_INVALID_JSON = "invalid_json"
RPC_CODE_INVALID_PARAMS = "invalid_params"
RPC_CODE_NOT_STREAMING = "not_streaming"


@dataclass(slots=True)
class RpcProtocolError(Exception):
    """Structured protocol error returned to the client."""

    code: str
    message: str
    command: str = RPC_COMMAND_INVALID
    request_id: str | None = None


@dataclass(slots=True)
class RpcCommand:
    request_id: str | None
    command: str


@dataclass(slots=True)
class PromptCommand(RpcCommand):
    prompt: str


@dataclass(slots=True)
class AbortCommand(RpcCommand):
    pass


@dataclass(slots=True)
class GetStateCommand(RpcCommand):
    pass


@dataclass(slots=True)
class GetMessagesCommand(RpcCommand):
    pass


@dataclass(slots=True)
class SetModelCommand(RpcCommand):
    model: str


@dataclass(slots=True)
class CompactCommand(RpcCommand):
    pass


def parse_command(payload: Any) -> RpcCommand:
    """Parse and validate one RPC command payload."""
    if not isinstance(payload, dict):
        raise RpcProtocolError(
            code=RPC_CODE_INVALID_JSON,
            message="Command must be a JSON object.",
        )

    request_id = _optional_string(payload.get("id"), field_name="id")
    command = _required_string(payload.get("command"), field_name="command", request_id=request_id)

    if command == "prompt":
        prompt = _required_string(payload.get("prompt"), field_name="prompt", request_id=request_id)
        return PromptCommand(request_id=request_id, command=command, prompt=prompt)
    if command == "abort":
        return AbortCommand(request_id=request_id, command=command)
    if command == "get_state":
        return GetStateCommand(request_id=request_id, command=command)
    if command == "get_messages":
        return GetMessagesCommand(request_id=request_id, command=command)
    if command == "set_model":
        model = _required_string(payload.get("model"), field_name="model", request_id=request_id)
        return SetModelCommand(request_id=request_id, command=command, model=model)
    if command == "compact":
        return CompactCommand(request_id=request_id, command=command)

    raise RpcProtocolError(
        code=RPC_CODE_INVALID_COMMAND,
        message=f"Unknown command: {command}",
        command=command,
        request_id=request_id,
    )


def success_response(command: RpcCommand, **payload: Any) -> dict[str, Any]:
    """Build a success response."""
    response: dict[str, Any] = {
        "id": command.request_id,
        "type": RPC_TYPE_RESPONSE,
        "command": command.command,
        "success": True,
    }
    response.update(payload)
    return response


def error_response(error: RpcProtocolError) -> dict[str, Any]:
    """Build a structured error response."""
    return {
        "id": error.request_id,
        "type": RPC_TYPE_RESPONSE,
        "command": error.command,
        "success": False,
        "error": {
            "code": error.code,
            "message": error.message,
        },
    }


def _required_string(
    value: Any,
    *,
    field_name: str,
    request_id: str | None,
) -> str:
    if isinstance(value, str) and value:
        return value
    raise RpcProtocolError(
        code=RPC_CODE_INVALID_PARAMS,
        message=f"Field '{field_name}' must be a non-empty string.",
        request_id=request_id,
    )


def _optional_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value:
        return value
    raise RpcProtocolError(
        code=RPC_CODE_INVALID_PARAMS,
        message=f"Field '{field_name}' must be a non-empty string when provided.",
    )
