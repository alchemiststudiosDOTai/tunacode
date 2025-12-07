"""File update tool for agent operations."""

import os

from pydantic_ai.exceptions import ModelRetry

from tunacode.tools.decorators import file_tool
from tunacode.tools.utils.text_match import replace


@file_tool
async def update_file(filepath: str, target: str, patch: str) -> str:
    """Update an existing file by replacing a target text block with a patch.

    Args:
        filepath: The path to the file to update.
        target: The entire, exact block of text to be replaced.
        patch: The new block of text to insert.

    Returns:
        A message indicating success.
    """
    if not os.path.exists(filepath):
        raise ModelRetry(
            f"File '{filepath}' not found. Cannot update. "
            "Verify the filepath or use `write_file` if it's a new file."
        )

    with open(filepath, encoding="utf-8") as f:
        original = f.read()

    try:
        new_content = replace(original, target, patch, replace_all=False)
    except ValueError as e:
        lines = original.splitlines()
        preview_lines = min(20, len(lines))
        snippet = "\n".join(lines[:preview_lines])
        raise ModelRetry(
            f"{e}\n\nFile '{filepath}' preview ({preview_lines} lines):\n---\n{snippet}\n---"
        ) from e

    if original == new_content:
        raise ModelRetry(
            f"Update target found, but replacement resulted in no changes to '{filepath}'. "
            "Was the `target` identical to the `patch`? Please check the file content."
        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    return f"File '{filepath}' updated successfully."
