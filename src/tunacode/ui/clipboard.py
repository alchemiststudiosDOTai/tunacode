"""Cross-platform clipboard support with multiple backend fallbacks.

Tries multiple clipboard mechanisms in order of reliability:
1. Platform-specific tools (xclip, wl-copy)
2. OSC 52 escape sequence (works over SSH/tmux)
3. pyperclip (if available)
4. Textual built-in copy_to_clipboard (OSC 52 wrapper)
"""

from __future__ import annotations

import base64
import os
import platform
import shutil
import subprocess
from collections.abc import Callable

from textual.app import App

PREVIEW_MAX_LENGTH = 40


def _copy_osc52(text: str) -> None:
    """Copy via OSC 52 escape sequence, with tmux passthrough."""
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    osc52_seq = f"\033]52;c;{encoded}\a"
    if os.environ.get("TMUX"):
        osc52_seq = f"\033Ptmux;\033{osc52_seq}\033\\"
    with open("/dev/tty", "w") as tty:
        tty.write(osc52_seq)
        tty.flush()


def _copy_xclip(text: str) -> None:
    """Copy via xclip (X11)."""
    subprocess.run(
        ["xclip", "-selection", "clipboard"],
        input=text.encode("utf-8"),
        check=True,
    )


def _copy_wayland(text: str) -> None:
    """Copy via wl-copy (Wayland)."""
    subprocess.run(
        ["wl-copy"],
        input=text.encode("utf-8"),
        check=True,
    )


def _has_cmd(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _build_copy_chain(app: App) -> list[Callable[[str], None]]:
    """Build ordered list of clipboard backends, most reliable first."""
    chain: list[Callable[[str], None]] = []

    is_linux = platform.system() == "Linux"
    if is_linux and _has_cmd("wl-copy"):
        chain.append(_copy_wayland)
    if is_linux and _has_cmd("xclip"):
        chain.append(_copy_xclip)

    chain.append(_copy_osc52)
    chain.append(app.copy_to_clipboard)
    return chain


def _shorten_preview(texts: list[str]) -> str:
    """Collapse multi-line selection into a compact preview string."""
    dense = "\u23ce".join(texts).replace("\n", "\u23ce")
    if len(dense) > PREVIEW_MAX_LENGTH:
        return f"{dense[: PREVIEW_MAX_LENGTH - 1]}\u2026"
    return dense


def collect_selected_text(app: App) -> str | None:
    """Walk all widgets and return the combined selected text, or None."""
    selected_texts: list[str] = []

    for widget in app.query("*"):
        selection = getattr(widget, "text_selection", None)
        if selection is None:
            continue

        get_selection = getattr(widget, "get_selection", None)
        if get_selection is None:
            continue

        try:
            result = get_selection(selection)
        except Exception:
            continue

        if not result:
            continue

        text, _ = result
        stripped = text.strip()
        if stripped:
            selected_texts.append(stripped)

    if not selected_texts:
        return None

    return "\n".join(selected_texts)


def copy_selection_to_clipboard(app: App) -> bool:
    """Copy highlighted selection to the system clipboard.

    Returns True if text was copied, False if nothing was selected.
    """
    combined = collect_selected_text(app)
    if combined is None:
        return False

    copy_chain = _build_copy_chain(app)
    copied = False
    for copy_fn in copy_chain:
        try:
            copy_fn(combined)
        except Exception:
            continue
        else:
            copied = True
            break

    if copied:
        preview = _shorten_preview(combined.split("\n"))
        app.notify(
            f'"{preview}" copied to clipboard',
            severity="information",
            timeout=2,
        )
    else:
        app.notify(
            "Failed to copy \u2014 no clipboard method available",
            severity="warning",
            timeout=3,
        )

    return copied
