"""Session resume helpers (tinyagent-only).

This package contains utilities for cleaning up conversation history between runs.

TunaCode persists history as tinyagent-style dict messages:

    {"role": "user|assistant|tool_result", "content": [...]}.

Legacy pydantic-ai message formats are intentionally not supported.
"""

from tunacode.core.agents.resume.sanitize import (
    find_dangling_tool_call_ids,
    remove_consecutive_requests,
    remove_dangling_tool_calls,
    remove_empty_responses,
    run_cleanup_loop,
    sanitize_history_for_resume,
)
from tunacode.core.agents.resume.sanitize_debug import log_message_history_debug

__all__ = [
    "sanitize_history_for_resume",
    "run_cleanup_loop",
    "remove_dangling_tool_calls",
    "remove_empty_responses",
    "remove_consecutive_requests",
    "find_dangling_tool_call_ids",
    "log_message_history_debug",
]
