"""CLI entry point for TunaCode."""

import asyncio
import json
import os
import sys

import typer

from tunacode.configuration.settings import ApplicationSettings
from tunacode.core.state import StateManager
from tunacode.exceptions import UserAbortError
from tunacode.tools.authorization.handler import ToolHandler
from tunacode.ui.app import run_textual_repl
from tunacode.utils.system import check_for_updates

DEFAULT_TIMEOUT_SECONDS = 600

app_settings = ApplicationSettings()
app = typer.Typer(help="TunaCode - OS AI-powered development assistant")
state_manager = StateManager()


def _handle_background_task_error(task: asyncio.Task) -> None:
    try:
        exception = task.exception()
        if exception is not None:
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


@app.command(name="run")
def run_headless(
    prompt: str = typer.Argument(..., help="The prompt/instruction to execute"),
    auto_approve: bool = typer.Option(
        False, "--auto-approve", help="Skip tool authorization prompts"
    ),
    output_json: bool = typer.Option(
        False, "--output-json", help="Output trajectory as JSON"
    ),
    timeout: int = typer.Option(
        DEFAULT_TIMEOUT_SECONDS, "--timeout", help="Execution timeout in seconds"
    ),
    cwd: str = typer.Option(None, "--cwd", help="Working directory for execution"),
    model: str = typer.Option(None, "--model", "-m", help="Model to use"),
) -> None:
    """Run TunaCode in non-interactive headless mode."""
    from tunacode.core.agents.main import process_request

    async def async_run() -> int:
        # Change working directory if specified
        if cwd:
            if not os.path.isdir(cwd):
                raise SystemExit(f"Invalid working directory: {cwd} (not a directory)")
            if not os.access(cwd, os.R_OK | os.X_OK):
                raise SystemExit(f"Inaccessible working directory: {cwd}")
            os.chdir(cwd)

        # Set model if provided
        if model:
            state_manager.session.current_model = model

        # Auto-approve mode (reuses existing yolo infrastructure)
        if auto_approve:
            state_manager.session.yolo = True

        # Initialize tool handler
        tool_handler = ToolHandler(state_manager)
        state_manager.set_tool_handler(tool_handler)

        try:
            await asyncio.wait_for(
                process_request(
                    message=prompt,
                    model=state_manager.session.current_model,
                    state_manager=state_manager,
                    tool_callback=None,
                    streaming_callback=None,
                    tool_result_callback=None,
                    tool_start_callback=None,
                ),
                timeout=timeout,
            )

            if output_json:
                trajectory = {
                    "messages": [
                        _serialize_message(msg) for msg in state_manager.session.messages
                    ],
                    "tool_calls": state_manager.session.tool_calls,
                    "usage": state_manager.session.session_total_usage,
                    "success": True,
                }
                print(json.dumps(trajectory, indent=2))

            return 0

        except TimeoutError:
            if output_json:
                print(json.dumps({"success": False, "error": "timeout"}))
            else:
                print("Error: Execution timed out", file=sys.stderr)
            return 1
        except Exception as e:
            if output_json:
                print(json.dumps({"success": False, "error": str(e)}))
            else:
                print(f"Error: {e}", file=sys.stderr)
            return 1

    exit_code = asyncio.run(async_run())
    raise typer.Exit(code=exit_code)


def _serialize_message(msg: object) -> dict:
    """Serialize a message object to a dictionary."""
    if hasattr(msg, "model_dump"):
        return msg.model_dump()
    if hasattr(msg, "__dict__"):
        return msg.__dict__
    return {"content": str(msg)}


if __name__ == "__main__":
    app()
