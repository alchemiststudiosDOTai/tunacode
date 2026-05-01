#!/usr/bin/env python3
"""Detect flaky tests by analyzing historical JSON test reports.

A test is considered flaky if it has both passed and failed outcomes across
different test runs. The script also flags tests with high duration variance
as potentially unstable (e.g., due to external dependency timing).

Usage:
    uv run python scripts/check-flaky-tests.py [--min-runs N]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

REPORTS_DIR = Path(".test_reports")
MIN_RUNS = 3  # require at least this many runs to detect flakiness

# Markers that indicate tests with inherent external-dependency variance.
# These tests are excluded from duration-variance checks because their
# timing depends on network, API keys, or tmux sessions rather than code stability.
EXTERNAL_DEPENDENCY_MARKERS = {"integration", "tmux", "flaky"}


def load_reports() -> list[dict]:
    """Load all archived JSON test reports sorted by timestamp."""
    reports = []
    for path in sorted(REPORTS_DIR.glob("report_*.json")):
        try:
            with open(path) as f:
                reports.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return reports


def detect_outcome_flaky(reports: list[dict]) -> list[str]:
    """Find tests that flip between passed and failed across runs."""
    test_outcomes: dict[str, set[str]] = defaultdict(set)
    for report in reports:
        for test in report.get("tests", []):
            outcome = test.get("outcome", "unknown")
            test_outcomes[test["nodeid"]].add(outcome)

    flaky_tests = []
    for nodeid, outcomes in sorted(test_outcomes.items()):
        passed = "passed" in outcomes
        failed = "failed" in outcomes or "error" in outcomes
        if passed and failed:
            flaky_tests.append(nodeid)
    return flaky_tests


def detect_duration_flaky(reports: list[dict], coefficient_threshold: float = 0.5) -> list[str]:
    """Find tests with high duration variance across runs (CV > threshold).

    Excludes tests marked integration, tmux, or flaky since their timing
    inherently depends on external resources (API keys, tmux sessions).
    """
    test_durations: dict[str, list[float]] = defaultdict(list)
    for report in reports:
        for test in report.get("tests", []):
            keywords = set(test.get("keywords", []))
            if keywords & EXTERNAL_DEPENDENCY_MARKERS:
                continue
            duration = test.get("call", {}).get("duration", 0)
            if duration > 0:
                test_durations[test["nodeid"]].append(duration)

    flaky_duration = []
    for nodeid, durations in sorted(test_durations.items()):
        if len(durations) < MIN_RUNS:
            continue
        avg = mean(durations)
        if avg < 0.1:  # skip very fast tests - variance at low durations is noise
            continue
        sd = stdev(durations)
        cv = sd / avg if avg > 0 else 0
        if cv > coefficient_threshold:
            flaky_duration.append((nodeid, cv, avg, sd))

    flaky_duration.sort(key=lambda x: -x[1])
    return [item[0] for item in flaky_duration]


def find_flaky_tests(reports: list[dict]) -> tuple[list[str], list[str]]:
    """Analyze reports and return outcome-flaky and duration-flaky tests."""
    outcome_flaky = detect_outcome_flaky(reports)
    duration_flaky = detect_duration_flaky(reports)
    return outcome_flaky, duration_flaky


def main() -> int:
    if not REPORTS_DIR.exists():
        print("No .test_reports directory found. Run tests first to generate reports.")
        return 0

    reports = load_reports()
    if len(reports) < MIN_RUNS:
        print(
            f"Only {len(reports)} report(s) found; "
            f"need at least {MIN_RUNS} runs for flaky detection."
        )
        return 0

    outcome_flaky, duration_flaky = find_flaky_tests(reports)

    if not outcome_flaky and not duration_flaky:
        print(f"No flaky tests detected across {len(reports)} runs.")
        return 0

    exit_code = 0

    if outcome_flaky:
        exit_code = 1
        print("=" * 60)
        print("FLAKY TESTS DETECTED (outcome flips between runs):")
        print("=" * 60)
        for nodeid in outcome_flaky:
            print(f"  {nodeid}")
        print(
            f"\n{len(outcome_flaky)} flaky test(s) found. "
            f"Mark with @pytest.mark.flaky to quarantine, "
            f"or fix the underlying cause."
        )

    if duration_flaky:
        exit_code = 1
        print()
        print("=" * 60)
        print("POTENTIALLY UNSTABLE TESTS (high duration variance):")
        print("=" * 60)
        for nodeid in duration_flaky:
            print(f"  {nodeid}")
        print(
            f"\n{len(duration_flaky)} unstable test(s) found. "
            f"These may depend on external resources or timing."
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
