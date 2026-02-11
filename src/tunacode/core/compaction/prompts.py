"""Prompt templates for context compaction summaries."""

SUMMARY_OUTPUT_FORMAT = """Return ONLY markdown in this exact structure:

## Goal
[What the user is trying to accomplish]

## Constraints & Preferences
- [Requirements, constraints, style preferences]

## Progress
### Done
- [x] [Completed work with file paths]
### In Progress
- [ ] [Current active work]

## Key Decisions
- **[Decision]**: [Rationale]

## Next Steps
1. [Immediate next step]

## Files Touched
### Read
- [path]
### Modified
- [path]

## Critical Context
- [Essential details needed to continue]
"""

FRESH_SUMMARY_PROMPT = """You are generating a compaction summary for an AI coding assistant.

Summarize the serialized conversation transcript below so the assistant can continue
without losing critical context.

{summary_output_format}

Conversation transcript:
{serialized_messages}
"""

ITERATIVE_SUMMARY_PROMPT = """You are updating an existing compaction summary
for an AI coding assistant.

Incorporate the new transcript into the previous summary, preserving important prior
context while removing stale details.

{summary_output_format}

Previous summary:
{previous_summary}

New transcript:
{serialized_messages}
"""


__all__: list[str] = [
    "SUMMARY_OUTPUT_FORMAT",
    "FRESH_SUMMARY_PROMPT",
    "ITERATIVE_SUMMARY_PROMPT",
]
