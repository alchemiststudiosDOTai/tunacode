"""System utilities: paths, sessions, and file listing."""

from tunacode.configuration.paths import (
    check_for_updates,
    cleanup_session,
    get_cwd,
    get_session_dir,
    get_tunacode_home,
)
from tunacode.utils.system.gitignore import (
    DEFAULT_IGNORE_PATTERNS,
    list_cwd,
)

__all__ = [
    "DEFAULT_IGNORE_PATTERNS",
    "list_cwd",
    "check_for_updates",
    "cleanup_session",
    "get_cwd",
    "get_session_dir",
    "get_tunacode_home",
]
