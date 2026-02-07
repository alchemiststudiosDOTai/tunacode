"""Multi-backend clipboard module.

Tries system clipboard tools first (xclip, wl-copy, xsel, pbcopy),
then falls back to Textual's built-in OSC 52 escape sequence.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence

# Backend command templates: (executable, args_to_write_stdin)
_SYSTEM_BACKENDS: Sequence[tuple[str, list[str]]] = [
    ("xclip", ["-selection", "clipboard"]),
    ("wl-copy", []),
    ("xsel", ["--clipboard", "--input"]),
    ("pbcopy", []),
]


def _try_system_copy(text: str) -> bool:
    """Attempt to copy via a system clipboard tool.

    Iterates through known backends and uses the first available one.

    Returns:
        True if copy succeeded, False otherwise.
    """
    for executable, args in _SYSTEM_BACKENDS:
        if shutil.which(executable) is None:
            continue
        try:
            subprocess.run(
                [executable, *args],
                input=text.encode("utf-8"),
                check=True,
                timeout=2,
            )
            return True
        except (subprocess.SubprocessError, OSError):
            continue
    return False


def copy_to_clipboard(text: str, *, app: object | None = None) -> bool:
    """Copy text to the system clipboard.

    Tries system backends first, then Textual's OSC 52 via app.

    Args:
        text: The text to copy.
        app: Optional Textual App instance for OSC 52 fallback.

    Returns:
        True if any backend succeeded, False if all failed.
    """
    if _try_system_copy(text):
        return True

    if app is not None and hasattr(app, "copy_to_clipboard"):
        app.copy_to_clipboard(text)
        return True

    return False
