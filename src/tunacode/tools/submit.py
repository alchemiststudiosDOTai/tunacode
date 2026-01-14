"""Submit tool for signaling task completion."""

from __future__ import annotations

import inspect
from collections.abc import Callable

from tunacode.tools.xml_helper import load_prompt_from_xml
from tunacode.types import StateManagerProtocol

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


def create_submit_tool(state_manager: StateManagerProtocol) -> Callable:
    """Factory to create a submit tool bound to a state manager.

    Args:
        state_manager: The state manager instance to use.

    Returns:
        An async function that implements the submit tool.
    """

    async def submit(summary: str | None = None) -> str:
        """Signal that the task is complete and ready for final response.

        Args:
            summary: Optional brief summary of what was completed.

        Returns:
            Confirmation that completion was recorded.
        """
        return _format_submit_message(summary)

    prompt = load_prompt_from_xml("submit")
    if prompt:
        submit.__doc__ = prompt

    submit.__signature__ = inspect.signature(submit)  # type: ignore[attr-defined]

    return submit
