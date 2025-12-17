"""Tests for CLI default command behavior."""

import subprocess

TEST_TIMEOUT_SECONDS = 30


def test_cli_help_lists_run_command() -> None:
    result = subprocess.run(
        ["tunacode", "--help"],
        capture_output=True,
        text=True,
        timeout=TEST_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0
    assert "TunaCode - OS AI-powered development assistant" in result.stdout
    assert "run" in result.stdout
    assert "--setup" in result.stdout


def test_cli_help_hides_main_alias() -> None:
    result = subprocess.run(
        ["tunacode", "--help"],
        capture_output=True,
        text=True,
        timeout=TEST_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0
    assert "\n│ main" not in result.stdout
