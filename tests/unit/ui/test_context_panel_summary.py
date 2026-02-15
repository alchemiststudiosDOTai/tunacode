from rich.text import Text
from textual.widgets import Static

from tunacode.types.canonical import UsageMetrics

from tunacode.core.session import StateManager

from tunacode.ui.app import TextualReplApp
from tunacode.ui.commands.clear import ClearCommand
from tunacode.ui.widgets import ToolResultDisplay


def _context_panel_text(app: TextualReplApp) -> str:
    context_panel = app.query_one("#context-panel")
    field_texts: list[str] = []

    for field in context_panel.query(Static):
        if field.border_title:
            field_texts.append(field.border_title)

        renderable = field.render()
        if isinstance(renderable, Text):
            field_texts.append(renderable.plain)
        else:
            field_texts.append(str(renderable))

    return "\n".join(field_texts).upper()


def _static_text(widget: Static) -> str:
    renderable = widget.render()
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
        assert "SESSION INSPECTOR" in context_text
        assert "TAMAGOTCHI" in context_text
        assert "OA/GPT-4O-MINI" in context_text
        assert "CONTEXT" in context_text
        assert "COST" in context_text
        assert "$0.42" in context_text
        assert "FILES" in context_text
        assert "SLOPBAR HEALTH" in context_text
        assert "50%" in context_text
        assert "/TMP/EXAMPLE.PY" in context_text


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
        assert "(NONE)" in context_text


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
        assert "(NONE)" in context_text


async def test_tamagochi_looks_sad_by_default() -> None:
    app = TextualReplApp(state_manager=StateManager())
    async with app.run_test(headless=True):
        pet_field = app.query_one("#field-pet", Static)
        assert "T.T" in _static_text(pet_field) or ";.;" in _static_text(pet_field)


async def test_tamagochi_shows_heart_only_after_touch() -> None:
    app = TextualReplApp(state_manager=StateManager())
    async with app.run_test(headless=True):
        pet_field = app.query_one("#field-pet", Static)
        assert "\N{BLACK HEART SUIT}" not in _static_text(pet_field)
        app._touch_tamagochi()

        assert "\N{BLACK HEART SUIT}" in _static_text(pet_field)


async def test_tamagochi_slopbar_health_is_half_full_by_default() -> None:
    app = TextualReplApp(state_manager=StateManager())
    async with app.run_test(headless=True):
        health_field = app.query_one("#field-slopbar-health", Static)
        health_text = _static_text(health_field)
        assert "50%" in health_text
        assert "\u2588\u2588\u2588\u2588\u2588" in health_text
        assert "\u2591\u2591\u2591\u2591\u2591" in health_text
