"""Ratchet the reduced core.ui_api adapter surface."""

from pathlib import Path

UI_API_DIR = Path(__file__).resolve().parents[2] / "src" / "tunacode" / "core" / "ui_api"
EXPECTED_FILES = {
    "__init__.py",
    "file_filter.py",
    "formatting.py",
}


def test_ui_api_file_surface_matches_expected_adapter_set() -> None:
    """core.ui_api should contain only the surviving behaviorful adapters."""
    actual_files = {path.name for path in UI_API_DIR.iterdir() if path.is_file()}
    assert actual_files == EXPECTED_FILES
