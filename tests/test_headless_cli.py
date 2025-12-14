"""Tests for headless CLI mode."""

import subprocess


def test_run_command_exists_and_shows_help():
    """Verify the run command exists and shows help."""
    result = subprocess.run(
        ["tunacode", "run", "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert "Run TunaCode in non-interactive headless mode" in result.stdout
    assert "--auto-approve" in result.stdout
    assert "--output-json" in result.stdout
    assert "--timeout" in result.stdout
    assert "--cwd" in result.stdout
    assert "--model" in result.stdout


def test_run_command_executes_without_tui():
    """Verify headless mode doesn't import Textual during execution."""
    result = subprocess.run(
        ["tunacode", "run", "echo test", "--auto-approve", "--timeout", "5"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    # Should complete without TUI (exit code 0 or model error, not import error)
    # The command may fail due to no API key, but it shouldn't have Textual errors
    assert "Textual" not in result.stderr
    # Exit code 0=success, 1=model/network error is OK (not import failures)
    assert result.returncode in (0, 1)
