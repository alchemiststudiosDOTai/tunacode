"""Helper functions for agent operations to reduce code duplication."""

from typing import Any

from tunacode.core.state import StateManager
from tunacode.types import FallbackResponse


class UserPromptPartFallback:
    """Fallback class for UserPromptPart when pydantic_ai is not available."""

    def __init__(self, content: str, part_kind: str):
        self.content = content
        self.part_kind = part_kind


# Cache for UserPromptPart class
_USER_PROMPT_PART_CLASS = None


def get_user_prompt_part_class():
    """Get UserPromptPart class with caching and fallback for test environment."""
    global _USER_PROMPT_PART_CLASS

    if _USER_PROMPT_PART_CLASS is not None:
        return _USER_PROMPT_PART_CLASS

    try:
        import importlib

        messages = importlib.import_module("pydantic_ai.messages")
        _USER_PROMPT_PART_CLASS = getattr(messages, "UserPromptPart", None)

        if _USER_PROMPT_PART_CLASS is None:
            _USER_PROMPT_PART_CLASS = UserPromptPartFallback
    except Exception:
        _USER_PROMPT_PART_CLASS = UserPromptPartFallback

    return _USER_PROMPT_PART_CLASS


def create_user_message(content: str, state_manager: StateManager):
    """Create a user message and add it to the session messages."""
    from .message_handler import get_model_messages

    model_request_cls = get_model_messages()[0]
    UserPromptPart = get_user_prompt_part_class()
    user_prompt_part = UserPromptPart(content=content, part_kind="user-prompt")
    message = model_request_cls(parts=[user_prompt_part], kind="request")
    state_manager.session.messages.append(message)
    return message


def get_tool_summary(tool_calls: list[dict[str, Any]]) -> dict[str, int]:
    """Generate a summary of tool usage from tool calls."""
    tool_summary: dict[str, int] = {}
    for tc in tool_calls:
        tool_name = tc.get("tool", "unknown")
        tool_summary[tool_name] = tool_summary.get(tool_name, 0) + 1
    return tool_summary


def get_tool_description(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Get a descriptive string for a tool call."""
    tool_desc = tool_name
    if tool_name in ["grep", "glob"] and isinstance(tool_args, dict):
        pattern = tool_args.get("pattern", "")
        tool_desc = f"{tool_name}('{pattern}')"
    elif tool_name == "read_file" and isinstance(tool_args, dict):
        path = tool_args.get("file_path", tool_args.get("filepath", ""))
        tool_desc = f"{tool_name}('{path}')"
    return tool_desc


def get_recent_tools_context(tool_calls: list[dict[str, Any]], limit: int = 3) -> str:
    """Get a context string describing recent tool usage."""
    if not tool_calls:
        return "No tools used yet"

    last_tools = []
    for tc in tool_calls[-limit:]:
        tool_name = tc.get("tool", "unknown")
        tool_args = tc.get("args", {})
        tool_desc = get_tool_description(tool_name, tool_args)
        last_tools.append(tool_desc)

    return f"Recent tools: {', '.join(last_tools)}"


def create_empty_response_message(
    message: str,
    empty_reason: str,
    tool_calls: list[dict[str, Any]],
    iteration: int,
    state_manager: StateManager,
) -> str:
    """Create a constructive message for handling empty responses."""
    tools_context = get_recent_tools_context(tool_calls)

    content = f"""Response appears {empty_reason if empty_reason != "empty" else "empty"} or incomplete. Let's troubleshoot and try again.

Task: {message[:200]}...
{tools_context}
Attempt: {iteration}

Please take one of these specific actions:

1. **Search yielded no results?** → Try alternative search terms or broader patterns
2. **Found what you need?** → Use TUNACODE DONE: to finalize
3. **Encountering a blocker?** → Explain the specific issue preventing progress
4. **Need more context?** → Use list_dir or expand your search scope

**Expected in your response:**
- Execute at least one tool OR provide substantial analysis
- If stuck, clearly describe what you've tried and what's blocking you
- Avoid empty responses - the system needs actionable output to proceed

Ready to continue with a complete response."""

    return content


def create_progress_summary(tool_calls: list[dict[str, Any]]) -> tuple[dict[str, int], str]:
    """Create a progress summary from tool calls."""
    tool_summary = get_tool_summary(tool_calls)

    if tool_summary:
        summary_str = ", ".join([f"{name}: {count}" for name, count in tool_summary.items()])
    else:
        summary_str = "No tools used yet"

    return tool_summary, summary_str


def create_fallback_response(
    iterations: int,
    max_iterations: int,
    tool_calls: list[dict[str, Any]],
    messages: list[Any],
    verbosity: str = "normal",
) -> FallbackResponse:
    """Create a comprehensive fallback response when iteration limit is reached."""
    fallback = FallbackResponse(
        summary="Reached maximum iterations without producing a final response.",
        progress=f"Completed {iterations} iterations (limit: {max_iterations})",
    )

    # Extract context from messages
    tool_calls_summary = []
    files_modified = set()
    commands_run = []

    for msg in messages:
        if hasattr(msg, "parts"):
            for part in msg.parts:
                if hasattr(part, "part_kind") and part.part_kind == "tool-call":
                    tool_name = getattr(part, "tool_name", "unknown")
                    tool_calls_summary.append(tool_name)

                    # Track specific operations
                    if tool_name in ["write_file", "update_file"] and hasattr(part, "args"):
                        if isinstance(part.args, dict) and "file_path" in part.args:
                            files_modified.add(part.args["file_path"])
                    elif tool_name in ["run_command", "bash"] and hasattr(part, "args"):
                        if isinstance(part.args, dict) and "command" in part.args:
                            commands_run.append(part.args["command"])

    if verbosity in ["normal", "detailed"]:
        # Add what was attempted
        if tool_calls_summary:
            tool_counts: dict[str, int] = {}
            for tool in tool_calls_summary:
                tool_counts[tool] = tool_counts.get(tool, 0) + 1

            fallback.issues.append(f"Executed {len(tool_calls_summary)} tool calls:")
            for tool, count in sorted(tool_counts.items()):
                fallback.issues.append(f"  • {tool}: {count}x")

        if verbosity == "detailed":
            if files_modified:
                fallback.issues.append(f"\nFiles modified ({len(files_modified)}):")
                for f in sorted(files_modified)[:5]:
                    fallback.issues.append(f"  • {f}")
                if len(files_modified) > 5:
                    fallback.issues.append(f"  • ... and {len(files_modified) - 5} more")

            if commands_run:
                fallback.issues.append(f"\nCommands executed ({len(commands_run)}):")
                for cmd in commands_run[:3]:
                    display_cmd = cmd if len(cmd) <= 60 else cmd[:57] + "..."
                    fallback.issues.append(f"  • {display_cmd}")
                if len(commands_run) > 3:
                    fallback.issues.append(f"  • ... and {len(commands_run) - 3} more")

    # Add helpful next steps
    fallback.next_steps.append("The task may be too complex - try breaking it into smaller steps")
    fallback.next_steps.append("Check the output above for any errors or partial progress")
    if files_modified:
        fallback.next_steps.append("Review modified files to see what changes were made")

    return fallback


async def handle_empty_response(
    message: str,
    reason: str,
    iter_index: int,
    state: Any,
) -> None:
    """Handle empty responses by creating a synthetic user message with retry guidance."""
    from tunacode.ui import console as ui

    force_action_content = create_empty_response_message(
        message,
        reason,
        getattr(state.sm.session, "tool_calls", []),
        iter_index,
        state.sm,
    )
    create_user_message(force_action_content, state.sm)

    if state.show_thoughts:
        await ui.warning("\nEMPTY RESPONSE FAILURE - AGGRESSIVE RETRY TRIGGERED")
        await ui.muted(f"   Reason: {reason}")
        await ui.muted(
            f"   Recent tools: {get_recent_tools_context(getattr(state.sm.session, 'tool_calls', []))}"
        )
        await ui.muted("   Injecting retry guidance prompt")


def format_fallback_output(fallback: FallbackResponse) -> str:
    """Format a fallback response into a comprehensive output string."""
    output_parts = [fallback.summary, ""]

    if fallback.progress:
        output_parts.append(f"Progress: {fallback.progress}")

    if fallback.issues:
        output_parts.append("\nWhat happened:")
        output_parts.extend(fallback.issues)

    if fallback.next_steps:
        output_parts.append("\nSuggested next steps:")
        for step in fallback.next_steps:
            output_parts.append(f"  • {step}")

    return "\n".join(output_parts)
