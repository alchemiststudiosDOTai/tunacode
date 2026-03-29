"""System tests for the long-lived `tunacode rpc` command."""

from __future__ import annotations

import json
import os
import select
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

RPC_TIMEOUT_SECONDS = 5.0
STARTUP_QUIET_TIMEOUT_SECONDS = 0.25


@contextmanager
def _rpc_process(tmp_path: Path) -> Iterator[tuple[subprocess.Popen[str], Path]]:
    env = os.environ.copy()
    home_dir = tmp_path / "home"
    data_dir = tmp_path / "xdg-data"
    home_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(home_dir)
    env["XDG_DATA_HOME"] = str(data_dir)
    env["TUNACODE_RPC_TEST_MODE"] = "1"
    env["NO_COLOR"] = "1"

    process = subprocess.Popen(
        ["tunacode", "rpc"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    try:
        yield process, data_dir
    finally:
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        try:
            process.wait(timeout=RPC_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=RPC_TIMEOUT_SECONDS)


def _send_payload(process: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    process.stdin.flush()


def _send_raw(process: subprocess.Popen[str], line: str) -> None:
    assert process.stdin is not None
    process.stdin.write(line)
    process.stdin.flush()


def _read_line(process: subprocess.Popen[str], timeout: float = RPC_TIMEOUT_SECONDS) -> str | None:
    assert process.stdout is not None
    ready, _, _ = select.select([process.stdout], [], [], timeout)
    if not ready:
        return None
    return process.stdout.readline()


def _read_json_record(
    process: subprocess.Popen[str],
    *,
    timeout: float = RPC_TIMEOUT_SECONDS,
) -> tuple[str, dict[str, Any]]:
    line = _read_line(process, timeout=timeout)
    assert line is not None, "Timed out waiting for RPC output"
    assert line.endswith("\n")
    assert "\n" not in line[:-1]
    return line, json.loads(line)


def _read_until(
    process: subprocess.Popen[str],
    predicate: Callable[[dict[str, Any]], bool],
    *,
    timeout: float = RPC_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    while True:
        _line, record = _read_json_record(process, timeout=timeout)
        records.append(record)
        if predicate(record):
            return records


def test_rpc_starts_without_stdout_noise(tmp_path: Path) -> None:
    with _rpc_process(tmp_path) as (process, _data_dir):
        assert _read_line(process, timeout=STARTUP_QUIET_TIMEOUT_SECONDS) is None


def test_prompt_returns_response_then_streamed_events(tmp_path: Path) -> None:
    with _rpc_process(tmp_path) as (process, _data_dir):
        _send_payload(process, {"id": "1", "command": "prompt", "prompt": "hello"})

        first_line, response = _read_json_record(process)
        assert json.loads(first_line) == response
        assert response == {
            "id": "1",
            "type": "response",
            "command": "prompt",
            "success": True,
        }

        records = _read_until(process, lambda record: record.get("type") == "agent_end")
        event_types = [record["type"] for record in records]
        assert event_types == [
            "agent_start",
            "turn_start",
            "message_start",
            "message_end",
            "message_start",
            "message_update",
            "message_update",
            "message_end",
            "turn_end",
            "agent_end",
        ]
        assert records[5]["assistantMessageEvent"]["delta"] == "echo:"
        assert records[6]["assistantMessageEvent"]["delta"] == "hello"


def test_streaming_state_busy_errors_and_abort_keep_process_alive(tmp_path: Path) -> None:
    with _rpc_process(tmp_path) as (process, _data_dir):
        _send_payload(process, {"id": "1", "command": "prompt", "prompt": "slow"})
        prompt_records = _read_until(
            process,
            lambda record: record.get("type") == "response" and record.get("id") == "1",
        )
        assert prompt_records[-1]["success"] is True

        _send_payload(process, {"id": "2", "command": "get_state"})
        state_records = _read_until(
            process,
            lambda record: record.get("type") == "response" and record.get("id") == "2",
        )
        state_response = state_records[-1]
        assert state_response["success"] is True
        assert state_response["isStreaming"] is True

        _send_payload(process, {"id": "3", "command": "prompt", "prompt": "again"})
        busy_records = _read_until(
            process,
            lambda record: record.get("type") == "response" and record.get("id") == "3",
        )
        busy_response = busy_records[-1]
        assert busy_response["success"] is False
        assert busy_response["error"]["code"] == "busy"

        _send_payload(process, {"id": "4", "command": "abort"})
        abort_records = _read_until(
            process,
            lambda record: record.get("type") == "response" and record.get("id") == "4",
        )
        assert abort_records[-1]["success"] is True

        _send_payload(process, {"id": "5", "command": "get_state"})
        idle_records = _read_until(
            process,
            lambda record: record.get("type") == "response" and record.get("id") == "5",
            timeout=RPC_TIMEOUT_SECONDS,
        )
        assert idle_records[-1]["isStreaming"] is False


def test_tool_events_get_messages_invalid_input_and_session_save(tmp_path: Path) -> None:
    with _rpc_process(tmp_path) as (process, data_dir):
        _send_payload(process, {"id": "1", "command": "prompt", "prompt": "tool"})
        _read_until(
            process, lambda record: record.get("type") == "response" and record.get("id") == "1"
        )
        prompt_events = _read_until(process, lambda record: record.get("type") == "agent_end")

        tool_start = next(
            record for record in prompt_events if record["type"] == "tool_execution_start"
        )
        tool_update = next(
            record for record in prompt_events if record["type"] == "tool_execution_update"
        )
        tool_end = next(
            record for record in prompt_events if record["type"] == "tool_execution_end"
        )
        assert {
            tool_start["toolCallId"],
            tool_update["toolCallId"],
            tool_end["toolCallId"],
        } == {"call_1"}

        _send_payload(process, {"id": "2", "command": "get_messages"})
        message_records = _read_until(
            process,
            lambda record: record.get("type") == "response" and record.get("id") == "2",
        )
        messages_response = message_records[-1]
        assert messages_response["success"] is True
        assert [message["role"] for message in messages_response["messages"]] == [
            "user",
            "tool_result",
            "assistant",
        ]

        session_files = list((data_dir / "tunacode" / "sessions").glob("*.json"))
        assert len(session_files) == 1
        persisted = json.loads(session_files[0].read_text())
        assert [message["role"] for message in persisted["messages"]] == [
            "user",
            "tool_result",
            "assistant",
        ]

        _send_raw(process, "not json\n")
        invalid_json_records = _read_until(
            process,
            lambda record: record.get("type") == "response"
            and record.get("command") == "invalid"
            and record.get("error", {}).get("code") == "invalid_json",
        )
        assert invalid_json_records[-1]["success"] is False

        _send_payload(process, {"id": "3", "command": "unknown"})
        unknown_records = _read_until(
            process,
            lambda record: record.get("type") == "response" and record.get("id") == "3",
        )
        assert unknown_records[-1]["error"]["code"] == "invalid_command"

        _send_payload(process, {"id": "4", "command": "get_state"})
        alive_records = _read_until(
            process,
            lambda record: record.get("type") == "response" and record.get("id") == "4",
        )
        assert alive_records[-1]["success"] is True
