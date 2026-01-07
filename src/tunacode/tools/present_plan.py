"""Present plan tool for plan mode.

When in plan mode, the agent uses this tool to present a plan for user approval.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tunacode.tools.xml_helper import load_prompt_from_xml
from tunacode.types import StateManagerProtocol

PLAN_APPROVED_MESSAGE = (
    "Plan approved and saved to PLAN.md. Plan mode exited. You may now use write tools."
)
PLAN_DENIED_MESSAGE = (
    "Plan denied by user. Feedback: {feedback}\n\n"
    "Revise your plan based on this feedback and call present_plan again."
)
PLAN_NOT_IN_PLAN_MODE = (
    "Error: present_plan can only be used in plan mode. Use /plan to enter plan mode first."
)


def create_present_plan_tool(state_manager: StateManagerProtocol) -> Callable:
    """Factory to create a present_plan tool bound to a state manager.

    The tool requires a plan_approval_callback to be set on the session
    for interactive approval. If not set, the plan is auto-approved.

    Args:
        state_manager: The state manager instance to use.

    Returns:
        An async function that implements the present_plan tool.
    """

    async def present_plan(plan_content: str) -> str:
        """Present a plan to the user for approval.

        Call this tool when you have gathered enough context and are ready
        to present your implementation plan. The user will review and either
        approve (saving to PLAN.md) or deny with feedback for revision.

        Args:
            plan_content: The complete plan in markdown format. Should include:
                - Goal/objective summary
                - Files to be modified
                - Step-by-step implementation approach
                - Potential risks or considerations

        Returns:
            Success message if approved, or denial feedback for revision.
        """
        session = state_manager.session

        if not session.plan_mode:
            return PLAN_NOT_IN_PLAN_MODE

        # Check if there's an approval callback (set by UI)
        approval_callback = getattr(session, "plan_approval_callback", None)

        if approval_callback is not None:
            # Interactive mode - wait for user approval
            approved, feedback = await approval_callback(plan_content)
        else:
            # Non-interactive mode - auto-approve
            approved, feedback = True, ""

        if approved:
            # Write plan to file
            plan_path = Path.cwd() / "PLAN.md"
            plan_path.write_text(plan_content, encoding="utf-8")

            # Exit plan mode
            session.plan_mode = False

            return PLAN_APPROVED_MESSAGE
        else:
            return PLAN_DENIED_MESSAGE.format(feedback=feedback or "No specific feedback provided")

    # Load prompt from XML if available
    prompt = load_prompt_from_xml("present_plan")
    if prompt:
        present_plan.__doc__ = prompt

    return present_plan
