"""CLI entry point for TunaCode."""

import asyncio

import typer

from tunacode.configuration.settings import ApplicationSettings
from tunacode.core.state import StateManager
from tunacode.exceptions import UserAbortError
from tunacode.tools.authorization.handler import ToolHandler
from tunacode.ui.app import run_textual_repl
from tunacode.utils.system import check_for_updates

app_settings = ApplicationSettings()
app = typer.Typer(help="TunaCode - OS AI-powered development assistant")
state_manager = StateManager()


def _handle_background_task_error(task: asyncio.Task) -> None:
    try:
        exception = task.exception()
        if exception is not None:
            task_name = task.get_name()
            # Background task failed - just pass without logging
            pass
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


@app.command()
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit."),
    _baseurl: str = typer.Option(  # noqa: ARG001 - reserved for future use
        None, "--baseurl", help="API base URL (e.g., https://openrouter.ai/api/v1)"
    ),
    model: str = typer.Option(None, "--model", help="Default model to use (e.g., openai/gpt-4)"),
    _key: str = typer.Option(None, "--key", help="API key for the provider"),  # noqa: ARG001
    _context: int = typer.Option(  # noqa: ARG001 - reserved for future use
        None, "--context", help="Maximum context window size for custom models"
    ),
    setup: bool = typer.Option(False, "--setup", help="Run setup wizard"),
):
    """Start TunaCode - Your AI-powered development assistant"""

    async def async_main():
        if version:
            from tunacode.constants import APP_VERSION

            print(f"tunacode {APP_VERSION}")
            return

        update_task = asyncio.create_task(asyncio.to_thread(check_for_updates), name="update_check")
        update_task.add_done_callback(_handle_background_task_error)

        if model:
            state_manager.session.current_model = model

        try:
            tool_handler = ToolHandler(state_manager)
            state_manager.set_tool_handler(tool_handler)

            await run_textual_repl(state_manager, show_setup=setup)
        except (KeyboardInterrupt, UserAbortError):
            update_task.cancel()
            return
        except Exception as e:
            from tunacode.exceptions import ConfigurationError

            if isinstance(e, ConfigurationError):
                print(f"Error: {e}")
                update_task.cancel()
                return
            import traceback

            print(f"Error: {e}\n\nTraceback:\n{traceback.format_exc()}")

        try:
            has_update, latest_version = await update_task
            if has_update:
                print(f"Update available: {latest_version}")
        except asyncio.CancelledError:
            pass

    asyncio.run(async_main())


if __name__ == "__main__":
    app()
