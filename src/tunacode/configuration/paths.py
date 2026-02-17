"""Path utilities, session management, device identification, and update checking."""

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any

from tunacode.constants import SESSIONS_SUBDIR, TUNACODE_HOME_DIR


def get_tunacode_home() -> Path:
    """
    Get the path to the TunaCode home directory (~/.tunacode).
    Creates it if it doesn't exist.

    Returns:
        Path: The path to the TunaCode home directory.
    """
    home = Path.home() / TUNACODE_HOME_DIR
    home.mkdir(exist_ok=True)
    return home


def get_session_dir(state_manager: Any) -> Path:
    """
    Get the path to the current session directory.

    Args:
        state_manager: The StateManager instance containing session info.

    Returns:
        Path: The path to the current session directory.
    """
    session_dir = get_tunacode_home() / SESSIONS_SUBDIR / state_manager.session.session_id
    session_dir.mkdir(exist_ok=True, parents=True)
    return session_dir


def get_cwd() -> str:
    """Returns the current working directory."""
    return os.getcwd()


def get_project_id() -> str:
    """
    Get a project identifier based on the git repository root or cwd.

    Returns:
        str: A 16-character hash identifying the current project.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            repo_root = result.stdout.strip()
            return hashlib.sha256(repo_root.encode()).hexdigest()[:16]
    except Exception:
        pass
    return hashlib.sha256(os.getcwd().encode()).hexdigest()[:16]


def get_session_storage_dir() -> Path:
    """
    Get the XDG-compliant session storage directory.

    Returns:
        Path: The directory where session files are stored.
    """
    xdg_data = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    storage_dir = Path(xdg_data) / "tunacode" / "sessions"
    storage_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    return storage_dir


def delete_session_file(project_id: str, session_id: str) -> bool:
    """
    Delete a persisted session file.

    Args:
        project_id: The project identifier.
        session_id: The session identifier.

    Returns:
        bool: True if deletion was successful, False otherwise.
    """
    try:
        storage_dir = get_session_storage_dir()
        session_file = storage_dir / f"{project_id}_{session_id}.json"
        if session_file.exists():
            session_file.unlink()
        return True
    except Exception as e:
        print(f"Error deleting session file: {e}")
        return False


def _get_installed_version() -> str:
    """Get the actually installed package version via importlib.metadata.

    Falls back to APP_VERSION constant if the package is not installed
    (e.g. running from an editable install or raw source checkout).
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("tunacode-cli")
    except PackageNotFoundError:
        from tunacode.constants import APP_VERSION

        return APP_VERSION


def check_for_updates() -> tuple[bool, str]:
    """Check if there's a newer version of tunacode-cli available on PyPI.

    Returns:
        tuple: (has_update, latest_version)
            - has_update (bool): True if a newer version is available
            - latest_version (str): The latest version available

    Raises:
        RuntimeError: If the PyPI version check fails.
    """
    from packaging.version import Version

    current_version = _get_installed_version()

    result = subprocess.run(
        ["pip", "index", "versions", "tunacode-cli"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        msg = f"pip index versions failed: {result.stderr.strip()}"
        raise RuntimeError(msg)

    output = result.stdout
    if "Available versions:" not in output:
        msg = f"Unexpected pip output: {output.strip()}"
        raise RuntimeError(msg)

    versions_line = output.split("Available versions:")[1].strip()
    versions = versions_line.split(", ")
    latest_version = versions[0].strip()

    if Version(latest_version) > Version(current_version):
        return True, latest_version

    return False, current_version
