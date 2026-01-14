"""Submit tool for signaling task completion."""

from __future__ import annotations

from tunacode.tools.xml_helper import load_prompt_from_xml

SUBMIT_SUCCESS_MESSAGE = "Task completion submitted."
SUBMIT_SUMMARY_LABEL = "Summary:"


def _normalize_summary(summary: str | None) -> str | None:
    if summary is None:
        return None

    trimmed = summary.strip()
    if not trimmed:
        return None

    return trimmed


def _format_submit_message(summary: str | None) -> str:
    normalized_summary = _normalize_summary(summary)
    if normalized_summary is None:
        return SUBMIT_SUCCESS_MESSAGE

    return f"{SUBMIT_SUCCESS_MESSAGE} {SUBMIT_SUMMARY_LABEL} {normalized_summary}"


async def submit(summary: str | None = None) -> str:
    """Signal that the task is complete and ready for final response.

    Args:
        summary: Optional brief summary of what was completed.

    Returns:
        Confirmation that completion was recorded.
    """
    return _format_submit_message(summary)


# Load XML prompt if available
_prompt = load_prompt_from_xml("submit")
if _prompt:
    submit.__doc__ = _prompt
