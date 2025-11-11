"""
Module: tunacode.cli.repl_components.output_display

Output formatting and display utilities for the REPL.
"""

from tunacode.ui import console as ui

# MSG_REQUEST_COMPLETED is used in repl.py
MSG_REQUEST_COMPLETED = "Request completed"


async def display_agent_output(res, enable_streaming: bool, state_manager=None) -> None:
    """Display agent output using guard clauses to flatten nested conditionals."""
    if enable_streaming:
        return

    if not hasattr(res, "result") or res.result is None or not hasattr(res.result, "output"):
        await ui.muted(MSG_REQUEST_COMPLETED)
        return

    output = res.result.output

    if not isinstance(output, str):
        return

    if output.strip().startswith('{"thought"'):
        return

    if '"tool_uses"' in output:
        return

    # Filter out system prompts and tool definitions
    if any(
        phrase in output
        for phrase in [
            "namespace functions {",
            "namespace multi_tool_use {",
            "You are trained on data up to",
        ]
    ):
        return

    await ui.agent(output)
