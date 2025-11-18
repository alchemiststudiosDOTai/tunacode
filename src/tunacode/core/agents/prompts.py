"""Prompt templates for agent intervention mechanisms.

Extracted from main.py to centralize all prompt strings and formatting logic.
"""


def format_no_progress(
    message: str,
    unproductive_count: int,
    last_productive: int,
    current: int,
    max_iterations: int,
) -> str:
    """Format the no-progress alert message.

    Reference: main.py _force_action_if_unproductive() lines 265-275
    """
    return (
        f"ALERT: No tools executed for {unproductive_count} iterations.\n\n"
        f"Last productive iteration: {last_productive}\n"
        f"Current iteration: {current}/{max_iterations}\n"
        f"Task: {message[:200]}...\n\n"
        "You're describing actions but not executing them. You MUST:\n\n"
        "1. If task is COMPLETE: Start response with TUNACODE DONE:\n"
        "2. If task needs work: Execute a tool RIGHT NOW (grep, read_file, bash, etc.)\n"
        "3. If stuck: Explain the specific blocker\n\n"
        "NO MORE DESCRIPTIONS. Take ACTION or mark COMPLETE."
    )


def format_clarification(original_query: str, iteration: int, tools_used: str) -> str:
    """Format the clarification request message.

    Reference: main.py _ask_for_clarification() lines 284-292
    """
    return (
        "I need clarification to continue.\n\n"
        f"Original request: {original_query}\n\n"
        "Progress so far:\n"
        f"- Iterations: {iteration}\n"
        f"- Tools used: {tools_used}\n\n"
        "If the task is complete, I should respond with TUNACODE DONE:\n"
        "Otherwise, please provide specific guidance on what to do next."
    )


def format_iteration_limit(max_iterations: int, iteration: int, tools_used: str) -> str:
    """Format the iteration limit reached message.

    Reference: main.py process_request() lines 495-501
    """
    if tools_used == "No tools used yet":
        tools_used = "No tools used"

    return (
        f"I've reached the iteration limit ({max_iterations}).\n\n"
        "Progress summary:\n"
        f"- Tools used: {tools_used}\n"
        f"- Iterations completed: {iteration}\n\n"
        "Please add more context to the task."
    )


# Note: Empty response handling is delegated to agent_components.handle_empty_response()
# which uses create_empty_response_message() from agent_helpers.py
# No template needed here as it's already modularized.

