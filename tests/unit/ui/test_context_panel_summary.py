from rich.text import Text
from textual.widgets import Static

from tunacode.types.canonical import UsageMetrics

from tunacode.core.session import StateManager

from tunacode.ui.app import TextualReplApp
from tunacode.ui.commands.clear import ClearCommand
from tunacode.ui.widgets import ToolResultDisplay


def _context_panel_text(app: TextualReplApp) -> str:
    context_panel = app.query_one("#context-panel", Static)
    renderable = context_panel.render()
    if isinstance(renderable, Text):
        return renderable.plain
    return str(renderable)


async def test_context_panel_summary_includes_model_tokens_cost_and_edited_files() -> None:
    state_manager = StateManager()
    state_manager.session.current_model = "openai/gpt-4o-mini"
    state_manager.session.conversation.max_tokens = 4096
    state_manager.session.usage.session_total_usage = UsageMetrics.from_dict(
        {
            "input": 100,
            "output": 50,
            "cache_read": 0,
            "cache_write": 0,
            "total_tokens": 150,
            "cost": {
                "input": 0.10,
                "output": 0.32,
                "cache_read": 0.0,
                "cache_write": 0.0,
                "total": 0.42,
            },
        }
    )

    app = TextualReplApp(state_manager=state_manager)

    async with app.run_test(headless=True):
        app._update_resource_bar()
        app.on_tool_result_display(
            ToolResultDisplay(
                tool_name="write_file",
                status="completed",
                args={"filepath": "/tmp/example.py"},
                result="ok",
                duration_ms=5.0,
            )
        )

        context_text = _context_panel_text(app)
        assert "Context Summary" in context_text
        assert "Model: openai/gpt-4o-mini" in context_text
        assert "Token Usage:" in context_text
        assert "Session Cost: $0.42" in context_text
        assert "Edited Files:" in context_text
        assert "/tmp/example.py" in context_text


async def test_reset_context_panel_state_clears_edited_files() -> None:
    app = TextualReplApp(state_manager=StateManager())

    async with app.run_test(headless=True):
        app.on_tool_result_display(
            ToolResultDisplay(
                tool_name="update_file",
                status="completed",
                args={"filepath": "/tmp/reset-me.py"},
                result="ok",
                duration_ms=2.0,
            )
        )

        app.reset_context_panel_state()

        context_text = _context_panel_text(app)
        assert "/tmp/reset-me.py" not in context_text
        assert "  - none" in context_text


async def test_clear_command_resets_context_panel_state() -> None:
    app = TextualReplApp(state_manager=StateManager())

    async with app.run_test(headless=True):
        app.on_tool_result_display(
            ToolResultDisplay(
                tool_name="write_file",
                status="completed",
                args={"filepath": "/tmp/clear-me.py"},
                result="ok",
                duration_ms=2.0,
            )
        )

        command = ClearCommand()
        await command.execute(app, "")

        context_text = _context_panel_text(app)
        assert app._edited_files == set()
        assert "/tmp/clear-me.py" not in context_text
        assert "  - none" in context_text
