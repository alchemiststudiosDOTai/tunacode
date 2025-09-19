"""Task completion detection utilities."""

import re
from typing import Tuple

_COMPLETION_MARKERS = (
    re.compile(r"^\s*TUNACODE\s+DONE:\s*", re.IGNORECASE),
    re.compile(r"^\s*TUNACODE[_\s]+TASK_COMPLETE\s*:?[\s]*", re.IGNORECASE),
)


def check_task_completion(content: str) -> Tuple[bool, str]:
    """
    Check if the content indicates task completion.

    Args:
        content: The text content to check

    Returns:
        Tuple of (is_complete, cleaned_content)
        - is_complete: True if task completion marker found
        - cleaned_content: Content with marker removed
    """
    if not content:
        return False, content

    lines = content.split("\n")

    for idx, line in enumerate(lines):
        for pattern in _COMPLETION_MARKERS:
            match = pattern.match(line)
            if match:
                remainder = line[match.end() :].strip()
                cleaned_lines = lines[:idx]
                if remainder:
                    cleaned_lines.append(remainder)
                cleaned_lines.extend(lines[idx + 1 :])
                cleaned = "\n".join(cleaned_lines).strip()
                return True, cleaned

    return False, content
