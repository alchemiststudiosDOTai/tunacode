"""Shared test fixtures for tools tests."""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# =============================================================================
# Test Performance Tracking
# =============================================================================

REPORTS_DIR = Path(__file__).parent.parent / ".test_reports"


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Archive test report with timestamp after each run."""
    latest_report = REPORTS_DIR / "latest.json"
    if not latest_report.exists():
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archived = REPORTS_DIR / f"report_{timestamp}.json"
    shutil.copy(latest_report, archived)

    # Keep only the last 30 reports to avoid unbounded growth
    reports = sorted(REPORTS_DIR.glob("report_*.json"))
    for old_report in reports[:-30]:
        old_report.unlink()


def pytest_terminal_summary(
    terminalreporter: "pytest.TerminalReporter", exitstatus: int, config: pytest.Config
) -> None:
    """Print summary of slow test trends if historical data exists."""
    latest_report = REPORTS_DIR / "latest.json"
    if not latest_report.exists():
        return

    try:
        with open(latest_report) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    # Extract test durations
    tests = data.get("tests", [])
    slow_tests = [
        (t["nodeid"], t.get("call", {}).get("duration", 0))
        for t in tests
        if t.get("call", {}).get("duration", 0) > 0.5
    ]

    if slow_tests:
        terminalreporter.write_sep("=", "Slow Test Summary (>0.5s)")
        for nodeid, duration in sorted(slow_tests, key=lambda x: -x[1])[:10]:
            terminalreporter.write_line(f"  {duration:.2f}s {nodeid}")


@pytest.fixture
def mock_no_xml_prompt():
    """Patch XML loading to return None."""
    with patch("tunacode.tools.decorators.load_prompt_from_xml", return_value=None):
        yield


@pytest.fixture
def mock_xml_prompt():
    """Patch XML loading to return a test prompt."""
    with patch("tunacode.tools.decorators.load_prompt_from_xml", return_value="Test XML prompt"):
        yield


# =============================================================================
# Test Isolation Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate tests from environment pollution.

    Removes env vars that could affect test behavior.
    """
    sensitive_vars = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "MINIMAX_API_KEY",
        "MINIMAX_CN_API_KEY",
        "OPENROUTER_API_KEY",
        "TUNACODE_CONFIG",
    ]
    for var in sensitive_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def isolated_tmp_dir() -> Path:
    """Provide a fresh temp directory for each test."""
    with tempfile.TemporaryDirectory(prefix="tunacode_test_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def isolated_cwd(isolated_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run test with isolated current working directory."""
    monkeypatch.chdir(isolated_tmp_dir)
    return isolated_tmp_dir
