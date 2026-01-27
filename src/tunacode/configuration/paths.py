"""Path utilities, session management, device identification, and update checking."""

import hashlib
import os
import subprocess
from pathlib import Path

from tunacode.configuration.settings import ApplicationSettings
from tunacode.constants import SESSIONS_SUBDIR, TUNACODE_HOME_DIR


def get_tunacode_home():
    """
    Get the path to the TunaCode home directory (~/.tunacode).
    Creates it if it doesn't exist.

    Returns:
        Path: The path to the TunaCode home directory.
    """
    home = Path.home() / TUNACODE_HOME_DIR
    home.mkdir(exist_ok=True)
    return home


def get_session_dir(state_manager):
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


def get_cwd():
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


def cleanup_session(state_manager):
    """
    Clean up temporary session runtime files after the CLI exits.
    Session data is preserved in XDG_DATA_HOME for persistence.

    Args:
        state_manager: The StateManager instance containing session info.

    Returns:
        bool: True if cleanup was successful, False otherwise.
    """
    try:
        if state_manager.session.session_id is None:
            return True

        session_dir = get_session_dir(state_manager)

        if session_dir.exists():
            import shutil

            shutil.rmtree(session_dir)

        return True
    except Exception as e:
        print(f"Error cleaning up session: {e}")
        return False


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


def check_for_updates():
    """
    Check if there's a newer version of tunacode-cli available on PyPI.

    Returns:
        tuple: (has_update, latest_version)
            - has_update (bool): True if a newer version is available
            - latest_version (str): The latest version available
    """
    app_settings = ApplicationSettings()
    current_version = app_settings.version
    try:
        result = subprocess.run(
            ["pip", "index", "versions", "tunacode-cli"], capture_output=True, text=True, check=True
        )
        output = result.stdout

        if "Available versions:" in output:
            versions_line = output.split("Available versions:")[1].strip()
            versions = versions_line.split(", ")
            latest_version = versions[0]

            latest_version = latest_version.strip()

            if latest_version > current_version:
                return True, latest_version

        return False, current_version
    except Exception:
        return False, current_version
