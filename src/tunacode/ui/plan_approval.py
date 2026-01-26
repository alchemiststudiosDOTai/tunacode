"""Plan approval UI components.

Renders plan approval panel and handles key events for plan mode.
Follows NeXTSTEP 4-zone layout pattern.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from textual import events
from textual.widgets import RichLog

from tunacode.constants import EXIT_PLAN_MODE_SENTINEL

from tunacode.ui.repl_support import PendingPlanApprovalState
from tunacode.ui.styles import (
    STYLE_ERROR,
    STYLE_MUTED,
    STYLE_PRIMARY,
    STYLE_SUCCESS,
    STYLE_WARNING,
)


class PlanApprovalHolder(Protocol):
    """Protocol for objects that hold pending plan approval state."""

    pending_plan_approval: PendingPlanApprovalState | None


def render_plan_approval_panel(plan_content: str) -> Panel:
    """Render plan approval panel with NeXTSTEP 4-zone layout.

    Zones:
    1. Title bar (mode identity) - Panel title
    2. Primary viewport (plan content)
    3. Context zone (output info)
    4. Actions zone (user choices)
    """
    context = Text()
    context.append("Output: ", style=STYLE_MUTED)
    context.append("PLAN.md", style=STYLE_PRIMARY)
    context.append(" will be created in project root", style=STYLE_MUTED)

    actions = Text()
    actions.append("[1]", style=f"bold {STYLE_SUCCESS}")
    actions.append(" Approve    ")
    actions.append("[2]", style=f"bold {STYLE_WARNING}")
    actions.append(" Feedback    ")
    actions.append("[3]", style=f"bold {STYLE_ERROR}")
    actions.append(" Exit")

    content_parts: list[Text | Markdown | Rule] = [
        Markdown(plan_content),
        Rule(style=STYLE_MUTED),
        context,
        Rule(style=STYLE_MUTED),
        actions,
    ]

    return Panel(
        Group(*content_parts),
        border_style=STYLE_PRIMARY,
        padding=(0, 1),
        expand=True,
        title="Plan Mode",
        subtitle="Review Implementation Plan",
    )


def handle_plan_approval_key(
    event: events.Key,
    pending: PendingPlanApprovalState,
    rich_log: RichLog,
) -> bool:
    """Handle key events for plan approval.

    Args:
        event: The key event to handle.
        pending: The pending plan approval state with future to resolve.
        rich_log: The RichLog widget for feedback.

    Returns:
        True if the key was handled, False otherwise.
    """
    if event.key == "1":
        rich_log.write(Text("Plan approved", style=STYLE_SUCCESS))
        pending.future.set_result((True, ""))
        event.stop()
        return True

    if event.key == "2":
        rich_log.write(Text("Plan denied - provide feedback for revision", style=STYLE_WARNING))
        pending.future.set_result((False, "Please revise the plan based on my requirements."))
        event.stop()
        return True

    if event.key == "3":
        rich_log.write(Text("Plan mode exited", style=STYLE_ERROR))
        pending.future.set_result((False, EXIT_PLAN_MODE_SENTINEL))
        event.stop()
        return True

    return False


async def request_plan_approval(
    plan_content: str,
    pending_state_holder: PlanApprovalHolder,
    rich_log: RichLog,
) -> tuple[bool, str]:
    """Request user approval for a plan.

    Args:
        plan_content: The plan markdown content to display.
        pending_state_holder: Object with pending_plan_approval attribute.
        rich_log: The RichLog widget for display.

    Returns:
        Tuple of (approved, feedback).

    Raises:
        RuntimeError: If a previous plan approval is still pending.
    """
    if (
        pending_state_holder.pending_plan_approval is not None
        and not pending_state_holder.pending_plan_approval.future.done()
    ):
        raise RuntimeError("Previous plan approval still pending")

    future: asyncio.Future[tuple[bool, str]] = asyncio.Future()
    pending = PendingPlanApprovalState(future=future, plan_content=plan_content)
    pending_state_holder.pending_plan_approval = pending

    panel = render_plan_approval_panel(plan_content)
    rich_log.write(panel, expand=True)

    return await future
