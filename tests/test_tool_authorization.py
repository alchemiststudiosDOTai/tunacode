"""Authorization tests for tool confirmation behavior."""

from types import SimpleNamespace

from tunacode.constants import ToolName
from tunacode.tools.authorization.handler import ToolHandler


class DummyStateManager:
    """Minimal state manager for authorization tests."""

    def __init__(self, *, plan_mode: bool) -> None:
        self.session = SimpleNamespace(yolo=False, plan_mode=plan_mode, tool_ignore=[])
        self.tool_handler: ToolHandler | None = None


def test_present_plan_skips_confirmation() -> None:
    state_manager = DummyStateManager(plan_mode=True)
    handler = ToolHandler(state_manager)  # type: ignore[arg-type]

    tool_name = ToolName.PRESENT_PLAN.value
    assert handler.should_confirm(tool_name) is False
