"""tinyagent integration.

This package is scaffolding for the tunacode migration from pydantic-ai to tinyagent.

Phase 1 (tun-00df) only ensures the dependency is installed and importable.
No runtime behavior is wired up yet.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

_TINYAGENT_DISTRIBUTION = "tinyagent"


def get_tinyagent_version() -> str:
    """Return the installed tinyagent distribution version.

    Raises:
        RuntimeError: If tinyagent is not installed in the current environment.
    """

    try:
        return version(_TINYAGENT_DISTRIBUTION)
    except PackageNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "tinyagent is required but not installed. Run `uv sync` from the project root."
        ) from exc


def ensure_tinyagent_importable() -> None:
    """Fail fast if tinyagent cannot be imported."""

    import tinyagent

    _ = tinyagent.Agent
