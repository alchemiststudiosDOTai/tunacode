"""Helper functions for agent operations to reduce code duplication."""

from typing import Any

from tunacode.types import CanonicalToolCall

RECENT_TOOL_LIMIT = 3


def _describe_read_file(tool_args: dict[str, Any]) -> str:
    path = tool_args.get("file_path", tool_args.get("filepath", ""))
    return f"Reading `{path}`" if path else "Reading file"


def get_tool_description(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Get a descriptive string for a tool call."""
    tool_desc = tool_name
    if tool_name == "read_file" and isinstance(tool_args, dict):
        path = tool_args.get("file_path", tool_args.get("filepath", ""))
        tool_desc = f"{tool_name}('{path}')"
    return tool_desc


def get_readable_tool_description(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Get a human-readable description of a tool operation for batch panel display."""
    if not isinstance(tool_args, dict):
        return f"Executing `{tool_name}`"

    if tool_name == "read_file":
        return _describe_read_file(tool_args)
    return f"Executing `{tool_name}`"


def get_recent_tools_context(
    tool_calls: list[CanonicalToolCall], limit: int = RECENT_TOOL_LIMIT
) -> str:
    """Get a context string describing recent tool usage."""
    if not tool_calls:
        return "No tools used yet"

    last_tools = []
    for tc in tool_calls[-limit:]:
        tool_name = tc.tool_name
        tool_args = tc.args
        tool_desc = get_tool_description(tool_name, tool_args)
        last_tools.append(tool_desc)

    return f"Recent tools: {', '.join(last_tools)}"


def create_empty_response_message(
    message: str,
    empty_reason: str,
    tool_calls: list[CanonicalToolCall],
    iteration: int,
) -> str:
    """Create a constructive message for handling empty responses."""
    tools_context = get_recent_tools_context(tool_calls)

    reason = empty_reason if empty_reason != "empty" else "empty"
    content = f"""Response appears {reason} or incomplete. Let's troubleshoot and try again.

Task: {message[:200]}...
{tools_context}
Attempt: {iteration}

Please take one of these specific actions:

1. **Search yielded no results?** → Try alternative search terms or broader patterns
2. **Found what you need?** → Call the submit tool to finalize
3. **Encountering a blocker?** → Explain the specific issue preventing progress
4. **Need more context?** → Use discover or expand your search scope

**Expected in your response:**
- Execute at least one tool OR provide substantial analysis
- If stuck, clearly describe what you've tried and what's blocking you
- Avoid empty responses - the system needs actionable output to proceed

Ready to continue with a complete response."""

    return content


async def handle_empty_response(
    message: str,
    reason: str,
    iter_index: int,
    state: Any,
) -> str:
    """Build a user-facing notice for empty responses."""
    tool_registry = state.sm.session.runtime.tool_registry
    recent_calls = tool_registry.recent_calls(limit=RECENT_TOOL_LIMIT)
    force_action_content = create_empty_response_message(
        message,
        reason,
        recent_calls,
        iter_index,
    )
    return force_action_content
