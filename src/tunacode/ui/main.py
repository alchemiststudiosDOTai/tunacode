"""CLI entry point for TunaCode."""

import asyncio
import json
import os
import sys

import typer

from tunacode.configuration.settings import ApplicationSettings
from tunacode.constants import ENV_OPENAI_BASE_URL
from tunacode.exceptions import UserAbortError
from tunacode.utils.system import check_for_updates

from tunacode.tools.authorization.handler import ToolHandler

from tunacode.core.state import StateManager

from tunacode.ui.headless import resolve_output
from tunacode.ui.repl_support import run_textual_repl

DEFAULT_TIMEOUT_SECONDS = 600
BASE_URL_HELP_TEXT = "API base URL (e.g., https://openrouter.ai/api/v1)"
HEADLESS_NO_RESPONSE_ERROR = "Error: No response generated"

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


def _print_version() -> None:
    from tunacode.constants import APP_VERSION

    print(f"tunacode {APP_VERSION}")


def _config_exists() -> bool:
    return app_settings.paths.config_file.exists()


def _apply_base_url_override(state_manager: StateManager, base_url: str | None) -> None:
    """Apply --baseurl CLI flag as OPENAI_BASE_URL env override."""
    if not base_url:
        return

    user_config = state_manager.session.user_config
    env = user_config.get("env")
    if env is None:
        env = {}
        user_config["env"] = env

    env[ENV_OPENAI_BASE_URL] = base_url


async def _run_textual_app(*, model: str | None, show_setup: bool) -> None:
    update_task = asyncio.create_task(asyncio.to_thread(check_for_updates), name="update_check")
    update_task.add_done_callback(_handle_background_task_error)

    if model:
        state_manager.session.current_model = model

    try:
        tool_handler = ToolHandler(state_manager)
        state_manager.set_tool_handler(tool_handler)

        await run_textual_repl(state_manager, show_setup=show_setup)
    except (KeyboardInterrupt, UserAbortError):
        update_task.cancel()
        return
    except Exception as exc:
        from tunacode.exceptions import ConfigurationError

        if isinstance(exc, ConfigurationError):
            print(f"Error: {exc}")
            update_task.cancel()
            return

        import traceback

        print(f"Error: {exc}\n\nTraceback:\n{traceback.format_exc()}")
        update_task.cancel()
        return

    try:
        has_update, latest_version = await update_task
        if has_update:
            print(f"Update available: {latest_version}")
    except asyncio.CancelledError:
        return


def _run_textual_cli(*, model: str | None, show_setup: bool) -> None:
    asyncio.run(_run_textual_app(model=model, show_setup=show_setup))


@app.callback(invoke_without_command=True)
def _default_command(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit."),
    setup: bool = typer.Option(False, "--setup", help="Run setup wizard"),
    baseurl: str | None = typer.Option(None, "--baseurl", help=BASE_URL_HELP_TEXT),
    model: str | None = typer.Option(
        None, "--model", help="Default model to use (e.g., openai/gpt-4)"
    ),
    _key: str = typer.Option(None, "--key", help="API key for the provider"),  # noqa: ARG001
    _context: int = typer.Option(  # noqa: ARG001 - reserved for future use
        None, "--context", help="Maximum context window size for custom models"
    ),
) -> None:
    if version:
        _print_version()
        raise typer.Exit(code=0)

    if ctx.invoked_subcommand is not None:
        if setup:
            raise typer.BadParameter("Use `tunacode --setup` without a subcommand.")
        _apply_base_url_override(state_manager, baseurl)
        if model:
            state_manager.session.current_model = model
        return

    _apply_base_url_override(state_manager, baseurl)
    _run_textual_cli(model=model, show_setup=setup or not _config_exists())


@app.command(hidden=True)
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit."),
    baseurl: str | None = typer.Option(None, "--baseurl", help=BASE_URL_HELP_TEXT),
    model: str | None = typer.Option(
        None, "--model", help="Default model to use (e.g., openai/gpt-4)"
    ),
    _key: str = typer.Option(None, "--key", help="API key for the provider"),  # noqa: ARG001
    _context: int = typer.Option(  # noqa: ARG001 - reserved for future use
        None, "--context", help="Maximum context window size for custom models"
    ),
    setup: bool = typer.Option(False, "--setup", help="Run setup wizard"),
) -> None:
    """Deprecated alias for `tunacode`."""
    if version:
        _print_version()
        raise typer.Exit(code=0)

    _apply_base_url_override(state_manager, baseurl)
    _run_textual_cli(model=model, show_setup=setup or not _config_exists())


@app.command(name="run")
def run_headless(
    prompt: str = typer.Argument(..., help="The prompt/instruction to execute"),
    auto_approve: bool = typer.Option(
        False, "--auto-approve", help="Skip tool authorization prompts"
    ),
    output_json: bool = typer.Option(False, "--output-json", help="Output trajectory as JSON"),
    timeout: int = typer.Option(
        DEFAULT_TIMEOUT_SECONDS, "--timeout", help="Execution timeout in seconds"
    ),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory for execution"),
    baseurl: str | None = typer.Option(None, "--baseurl", help=BASE_URL_HELP_TEXT),
    model: str | None = typer.Option(None, "--model", "-m", help="Model to use"),
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

        _apply_base_url_override(state_manager, baseurl)

        # Auto-approve mode (reuses existing yolo infrastructure)
        if auto_approve:
            state_manager.session.yolo = True

        # Initialize tool handler
        tool_handler = ToolHandler(state_manager)
        state_manager.set_tool_handler(tool_handler)

        try:
            agent_run = await asyncio.wait_for(
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
                conversation = state_manager.session.conversation
                runtime = state_manager.session.runtime
                usage = state_manager.session.usage
                tool_records = runtime.tool_registry.to_legacy_records()
                trajectory = {
                    "messages": [_serialize_message(msg) for msg in conversation.messages],
                    "tool_calls": tool_records,
                    "usage": usage.session_total_usage.to_dict(),
                    "success": True,
                }
                print(json.dumps(trajectory, indent=2))
                return 0

            headless_output = resolve_output(agent_run, state_manager.session.conversation.messages)
            if headless_output is None:
                print(HEADLESS_NO_RESPONSE_ERROR, file=sys.stderr)
                return 1

            print(headless_output)

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
