from __future__ import annotations

import difflib
import os

from tunacode.constants import MAX_CALLBACK_CONTENT, MAX_LINE_LENGTH
from tunacode.types import ToolArgs, ToolConfirmationRequest, ToolName

from tunacode.tools.utils.text_match import replace

MAX_PREVIEW_LINES: int = 100
MAX_PREVIEW_LINE_LENGTH: int = MAX_LINE_LENGTH
TRUNCATION_NOTICE: str = "... [truncated for safety]"


def _preview_lines(text: str) -> tuple[list[str], bool]:
    """Return bounded preview lines for UI confirmation panels.

    This must be safe for extremely large or single-line payloads (e.g., minified files)
    so the TUI doesn't hang while rendering Rich Syntax blocks.
    """
    if not text:
        return [], False

    truncated = False
    preview = text
    if len(preview) > MAX_CALLBACK_CONTENT:
        preview = preview[:MAX_CALLBACK_CONTENT]
        truncated = True

    lines: list[str] = []
    offset = 0

    while len(lines) < MAX_PREVIEW_LINES and offset < len(preview):
        newline_index = preview.find("\n", offset)
        if newline_index == -1:
            lines.append(preview[offset:])
            offset = len(preview)
            break

        lines.append(preview[offset:newline_index])
        offset = newline_index + 1

    if offset < len(preview):
        truncated = True

    bounded_lines: list[str] = []
    for line in lines:
        if len(line) <= MAX_PREVIEW_LINE_LENGTH:
            bounded_lines.append(line)
            continue

        bounded_lines.append(line[:MAX_PREVIEW_LINE_LENGTH] + "...")
        truncated = True

    return bounded_lines, truncated


def _generate_creation_diff(filepath: str, content: str) -> str:
    """Generate a unified diff for new file creation."""
    lines, truncated = _preview_lines(content)

    diff_parts = [
        "--- /dev/null\n",
        f"+++ b/{filepath}\n",
        f"@@ -0,0 +1,{len(lines)} @@\n",
    ]

    for line in lines:
        diff_parts.append(f"+{line}\n")

    if truncated:
        diff_parts.append(f"\n{TRUNCATION_NOTICE}\n")

    return "".join(diff_parts)


class ConfirmationRequestFactory:
    """Create structured confirmation requests for UI surfaces."""

    def create(self, tool_name: ToolName, args: ToolArgs) -> ToolConfirmationRequest:
        filepath = args.get("filepath")
        diff_content: str | None = None

        if tool_name == "update_file" and filepath and os.path.exists(filepath):
            old_text = args.get("old_text")
            new_text = args.get("new_text")
            if old_text and new_text:
                try:
                    with open(filepath, encoding="utf-8") as f:
                        original = f.read()

                    # Attempt to generate what the new content will look like
                    new_content = replace(original, old_text, new_text, replace_all=False)

                    diff_lines = list(
                        difflib.unified_diff(
                            original.splitlines(keepends=True),
                            new_content.splitlines(keepends=True),
                            fromfile=f"a/{filepath}",
                            tofile=f"b/{filepath}",
                        )
                    )
                    if diff_lines:
                        raw_diff = "".join(diff_lines)
                        diff_preview_lines, truncated = _preview_lines(raw_diff)
                        diff_content = "\n".join(diff_preview_lines)
                        if truncated:
                            diff_content = f"{diff_content}\n{TRUNCATION_NOTICE}"
                except Exception:
                    # If anything fails (file read, fuzzy match, etc), we just don't show the diff
                    pass

        elif tool_name == "write_file" and filepath:
            content = args.get("content", "")
            if content:
                diff_content = _generate_creation_diff(filepath, content)

        return ToolConfirmationRequest(
            tool_name=tool_name, args=args, filepath=filepath, diff_content=diff_content
        )
