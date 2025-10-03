"""Golden baseline tests for project version metadata consistency."""

from __future__ import annotations

import pathlib

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11 fallback
    import tomli as tomllib  # type: ignore[import-not-found]

from tunacode.constants import APP_VERSION

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def read_pyproject_versions() -> tuple[str, str]:
    """Return the [project] version and Hatch script version from pyproject.toml."""
    toml_data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    project_version = toml_data["project"]["version"]
    script_version = toml_data["tool"]["hatch"]["envs"]["default"]["scripts"]["version"]
    return project_version, script_version


def test_app_version_matches_pyproject_metadata() -> None:
    """Ensure APP_VERSION matches both pyproject.toml version declarations."""
    project_version, script_version = read_pyproject_versions()
    assert project_version == script_version == APP_VERSION
