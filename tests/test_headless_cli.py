"""Tests for headless CLI mode."""

import subprocess
import tempfile
from pathlib import Path

import pytest

TEST_TIMEOUT_SECONDS = 15


def test_run_command_exists_and_shows_help() -> None:
    """Verify the run command exists and shows help."""
    result = subprocess.run(
        ["tunacode", "run", "--help"],
        capture_output=True,
        text=True,
        timeout=TEST_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0
    assert "Run TunaCode in non-interactive headless mode" in result.stdout
    assert "--auto-approve" in result.stdout
    assert "--output-json" in result.stdout
    assert "--timeout" in result.stdout
    assert "--cwd" in result.stdout
    assert "--model" in result.stdout


def test_run_command_executes_without_tui() -> None:
    """Verify headless mode doesn't import Textual during execution."""
    result = subprocess.run(
        ["tunacode", "run", "echo test", "--auto-approve", "--timeout", "5"],
        capture_output=True,
        text=True,
        timeout=TEST_TIMEOUT_SECONDS,
    )
    # Should complete without TUI (exit code 0 or model error, not import error)
    # The command may fail due to no API key, but it shouldn't have Textual errors
    assert "Textual" not in result.stderr
    # Exit code 0=success, 1=model/network error is OK (not import failures)
    assert result.returncode in (0, 1)


@pytest.mark.integration
def test_needle_in_haystack() -> None:
    """Agent finds a hidden value in a file.

    CLAUDE_ANCHOR[real-llm-integration-tests]: 98d4d2cc-cd77-4432-bc57-eeaf930a608e
    This test intentionally calls the REAL LLM - no mocking.
    If it fails, check API key, network, and model availability.
    """
    needle = "SECRET_CODE_XJ7K9"

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create haystack file with needle buried in it
        haystack = Path(tmpdir) / "data.txt"
        haystack.write_text(
            "Line 1: Some random data\n"
            "Line 2: More irrelevant content\n"
            "Line 3: Nothing to see here\n"
            f"Line 4: The secret is {needle}\n"
            "Line 5: Even more filler text\n"
            "Line 6: Almost at the end\n"
            "Line 7: Final line of content\n"
        )

        result = subprocess.run(
            [
                "tunacode",
                "run",
                "What is the SECRET_CODE in data.txt? Reply with just the code.",
                "--auto-approve",
                "--timeout",
                "60",
                "--cwd",
                tmpdir,
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert needle in result.stdout, f"Needle not found in: {result.stdout}"
