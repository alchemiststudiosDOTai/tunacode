"""Ratchet test: pydantic usage can only decrease, never increase.

This test ensures we're making progress on decoupling from pydantic-ai.
If you add new pydantic imports to src/, this test fails.

To update the baseline after REMOVING pydantic usage:
    uv run python scripts/pydantic_usage_report.py --root src > scripts/pydantic_usage_baseline.json
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
SRC_ROOT = REPO_ROOT / "src"
BASELINE_PATH = REPO_ROOT / "scripts" / "pydantic_usage_baseline.json"
REPORT_SCRIPT = REPO_ROOT / "scripts" / "pydantic_usage_report.py"

# Groups that matter for the ratchet
RATCHET_GROUPS = frozenset(
    {
        "pydantic_ai_imports",
        "pydantic_imports",
        "type_adapter",
        "agent_call",
    }
)


def _run_report() -> dict:
    """Run the pydantic usage report on src/ only."""
    result = subprocess.run(
        ["python", str(REPORT_SCRIPT), "--root", "src"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _load_baseline() -> dict:
    """Load the baseline JSON."""
    return json.loads(BASELINE_PATH.read_text())


@pytest.fixture(scope="module")
def current_report() -> dict:
    """Get current pydantic usage report."""
    return _run_report()


@pytest.fixture(scope="module")
def baseline() -> dict:
    """Get baseline pydantic usage."""
    return _load_baseline()


class TestPydanticRatchet:
    """Ensure pydantic coupling only decreases."""

    def test_baseline_exists(self) -> None:
        """Baseline file must exist."""
        assert BASELINE_PATH.exists(), (
            f"Baseline not found: {BASELINE_PATH}\n"
            "Generate with: uv run python scripts/pydantic_usage_report.py "
            "--root src > scripts/pydantic_usage_baseline.json"
        )

    def test_total_match_count_not_increased(self, current_report: dict, baseline: dict) -> None:
        """Total pydantic matches must not increase."""
        current_total = current_report["totals"]["match_count"]
        baseline_total = baseline["totals"]["match_count"]

        assert current_total <= baseline_total, (
            f"Pydantic usage increased! {baseline_total} → {current_total}\n"
            "You added pydantic imports. Remove them or update the baseline if justified."
        )

    def test_total_file_count_not_increased(self, current_report: dict, baseline: dict) -> None:
        """Total files with pydantic must not increase."""
        current_files = current_report["totals"]["file_count"]
        baseline_files = baseline["totals"]["file_count"]

        assert current_files <= baseline_files, (
            f"Files with pydantic increased! {baseline_files} → {current_files}\n"
            "You added pydantic to new files. Remove or update baseline if justified."
        )

    @pytest.mark.parametrize("group_name", list(RATCHET_GROUPS))
    def test_group_match_count_not_increased(
        self, group_name: str, current_report: dict, baseline: dict
    ) -> None:
        """Per-group pydantic matches must not increase."""
        current_group = current_report["groups"].get(group_name, {})
        baseline_group = baseline["groups"].get(group_name, {})

        current_count = current_group.get("match_count", 0)
        baseline_count = baseline_group.get("match_count", 0)

        assert current_count <= baseline_count, (
            f"[{group_name}] matches increased! {baseline_count} → {current_count}\n"
            "Remove the new pydantic usage or update baseline if justified."
        )

    def test_print_progress_if_improved(self, current_report: dict, baseline: dict) -> None:
        """Report progress when pydantic usage decreases."""
        current_total = current_report["totals"]["match_count"]
        baseline_total = baseline["totals"]["match_count"]

        if current_total < baseline_total:
            delta = baseline_total - current_total
            print(f"\n🎉 Pydantic usage decreased by {delta} matches!")
            print("Consider updating the baseline to lock in progress:")
            print(
                "  uv run python scripts/pydantic_usage_report.py "
                "--root src > scripts/pydantic_usage_baseline.json"
            )
