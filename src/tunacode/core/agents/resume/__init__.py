"""Session resume module.

Provides utilities for sanitizing, pruning, and managing message history
when resuming conversations after abort or session restart.

Public API:
- sanitize_history: Clean message history for resume
- run_cleanup_loop: Iterative cleanup until stable
- prune_old_tool_outputs: Remove old tool output content
- filter_compacted: Truncate history at summary checkpoint
- should_compact: Check if summary generation needed
- generate_summary: Create rolling summary
"""

from tunacode.core.agents.resume.filter import filter_compacted, prepare_history
from tunacode.core.agents.resume.prune import prune_old_tool_outputs
from tunacode.core.agents.resume.sanitize import (
    run_cleanup_loop,
    sanitize_history_for_resume,
)
from tunacode.core.agents.resume.sanitize_debug import log_message_history_debug
from tunacode.core.agents.resume.summary import (
    SummaryMessage,
    generate_summary,
    is_summary_message,
    should_compact,
)

__all__ = [
    # Sanitization
    "sanitize_history_for_resume",
    "run_cleanup_loop",
    "log_message_history_debug",
    # Pruning
    "prune_old_tool_outputs",
    # Filtering
    "filter_compacted",
    "prepare_history",
    # Summary
    "SummaryMessage",
    "generate_summary",
    "is_summary_message",
    "should_compact",
]
