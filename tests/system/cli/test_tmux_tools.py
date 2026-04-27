"""Minimal tmux-backed system test for TunaCode TUI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG

READY_TIMEOUT_SECONDS = 20.0
RESPONSE_TIMEOUT_SECONDS = 60.0
POLL_INTERVAL_SECONDS = 0.5
TMUX_TARGET_PANE = "0.0"
TEST_MODEL = "minimax:MiniMax-M2.1"
TEST_PROMPT = "hey this is a test, respond hello"
EXPECTED_RESPONSE = "hello"
TEST_API_KEY_ENV_VAR = "TUNACODE_TEST_API_KEY"
RUN_TMUX_TESTS_ENV_VAR = "TUNACODE_RUN_TMUX_TESTS"
PROVIDER_API_KEY_ENV_VAR = "MINIMAX_API_KEY"


def _tmux_tests_explicitly_enabled() -> bool:
    return os.environ.get(RUN_TMUX_TESTS_ENV_VAR, "").lower() in {"1", "true", "yes"}


def _run_tmux(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["tmux", *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _wait_for_file(path: Path, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError(f"Timed out waiting for file: {path}")


def _capture_pane(session_name: str) -> str:
    result = _run_tmux("capture-pane", "-pt", f"{session_name}:{TMUX_TARGET_PANE}", "-S", "-200")
    return result.stdout


def _wait_for_pane_text(session_name: str, expected_text: str, timeout_seconds: float) -> str:
    deadline = time.monotonic() + timeout_seconds
    last_output = ""
    while time.monotonic() < deadline:
        last_output = _capture_pane(session_name)
        if expected_text.lower() in last_output.lower():
            return last_output
        time.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError(
        f"Timed out waiting for {expected_text!r} in tmux pane.\nLast output:\n{last_output}"
    )


def _write_test_config(config_path: Path, api_key: str) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(json.dumps(DEFAULT_USER_CONFIG))
    config["default_model"] = TEST_MODEL
    config["recent_models"] = [TEST_MODEL]
    config["env"][PROVIDER_API_KEY_ENV_VAR] = api_key
    config_path.write_text(
        json.dumps(config, indent=2),
        encoding="utf-8",
    )


@pytest.mark.integration
@pytest.mark.tmux
@pytest.mark.skipif(shutil.which("tmux") is None, reason="Requires tmux")
@pytest.mark.skipif(
    not _tmux_tests_explicitly_enabled(),
    reason=f"Requires explicit opt-in via {RUN_TMUX_TESTS_ENV_VAR}=1",
)
@pytest.mark.skipif(
    not os.environ.get(TEST_API_KEY_ENV_VAR),
    reason=f"Requires {TEST_API_KEY_ENV_VAR} for real API integration tests",
)
def test_tmux_prompt_responds_hello(tmp_path: Path) -> None:
    """Launch the TUI inside tmux, send a prompt, and assert the pane shows hello."""
    session_name = f"tunatest_{uuid.uuid4().hex[:8]}"
    home_dir = tmp_path / "home"
    data_dir = tmp_path / "data"
    ready_file = tmp_path / "ready.txt"
    config_path = home_dir / ".config" / "tunacode.json"
    api_key = os.environ[TEST_API_KEY_ENV_VAR]

    _write_test_config(config_path, api_key)

    command = f"cd {Path.cwd().as_posix()} && source .venv/bin/activate && tunacode"

    try:
        _run_tmux(
            "new-session",
            "-d",
            "-s",
            session_name,
            "-e",
            f"HOME={home_dir}",
            "-e",
            f"XDG_DATA_HOME={data_dir}",
            "-e",
            f"TUNACODE_TEST_READY_FILE={ready_file}",
            "bash",
            "-lc",
            command,
        )
        _wait_for_file(ready_file, READY_TIMEOUT_SECONDS)

        _run_tmux("send-keys", "-t", f"{session_name}:{TMUX_TARGET_PANE}", "-l", TEST_PROMPT)
        _run_tmux("send-keys", "-t", f"{session_name}:{TMUX_TARGET_PANE}", "Enter")

        pane_output = _wait_for_pane_text(session_name, EXPECTED_RESPONSE, RESPONSE_TIMEOUT_SECONDS)
        assert EXPECTED_RESPONSE in pane_output.lower()
    finally:
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            check=False,
            capture_output=True,
            text=True,
        )
