"""CLI entry point for TunaCode."""

import asyncio
import json
import os
import sys

import typer

from tunacode.core import ConfigurationError, UserAbortError
from tunacode.core.session import StateManager
from tunacode.core.ui_api.configuration import ApplicationSettings
from tunacode.core.ui_api.constants import ENV_OPENAI_BASE_URL
from tunacode.core.ui_api.system_paths import check_for_updates

from tunacode.ui.headless import resolve_output
from tunacode.ui.repl_support import run_textual_repl

DEFAULT_TIMEOUT_SECONDS = 600
BASE_URL_HELP_TEXT = "API base URL (e.g., https://openrouter.ai/api/v1)"
HEADLESS_NO_RESPONSE_ERROR = "Error: No response generated"
AUTO_APPROVE_SETTING_KEY = "auto_approve"
USER_SETTINGS_KEY = "settings"

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
    from tunacode.core.ui_api.constants import APP_VERSION

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
        await run_textual_repl(state_manager, show_setup=show_setup)
    except (KeyboardInterrupt, UserAbortError):
        update_task.cancel()
        return
    except Exception as exc:
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


def _validate_cwd(cwd: str | None) -> None:
    """Validate and change to the given working directory."""
    if not cwd:
        return
    if not os.path.isdir(cwd):
        raise SystemExit(f"Invalid working directory: {cwd} (not a directory)")
    if not os.access(cwd, os.R_OK | os.X_OK):
        raise SystemExit(f"Inaccessible working directory: {cwd}")
    os.chdir(cwd)


def _build_trajectory_json(sm: StateManager) -> str:
    """Build JSON trajectory output from session state."""
    conversation = sm.session.conversation
    runtime = sm.session.runtime
    usage = sm.session.usage
    tool_records = runtime.tool_registry.to_legacy_records()
    trajectory = {
        "messages": [_serialize_message(msg) for msg in conversation.messages],
        "tool_calls": tool_records,
        "usage": usage.session_total_usage.to_dict(),
        "success": True,
    }
    return json.dumps(trajectory, indent=2)


def _print_headless_error(output_json: bool, error: str) -> None:
    """Print an error in the appropriate format."""
    if output_json:
        print(json.dumps({"success": False, "error": error}))
    else:
        print(f"Error: {error}", file=sys.stderr)


@app.command(name="run")
def run_headless(
    prompt: str = typer.Argument(..., help="The prompt/instruction to execute"),
    output_json: bool = typer.Option(False, "--output-json", help="Output trajectory as JSON"),
    auto_approve: bool = typer.Option(
        False,
        "--auto-approve",
        help="Automatically approve tool actions in headless mode",
    ),
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
        _validate_cwd(cwd)

        if model:
            state_manager.session.current_model = model

        _apply_base_url_override(state_manager, baseurl)

        settings = state_manager.session.user_config.setdefault(USER_SETTINGS_KEY, {})
        settings[AUTO_APPROVE_SETTING_KEY] = auto_approve

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
                print(_build_trajectory_json(state_manager))
                return 0

            headless_output = resolve_output(agent_run, state_manager.session.conversation.messages)
            if headless_output is None:
                print(HEADLESS_NO_RESPONSE_ERROR, file=sys.stderr)
                return 1

            print(headless_output)
            return 0

        except TimeoutError:
            _print_headless_error(output_json, "timeout" if output_json else "Execution timed out")
            return 1
        except Exception as e:
            _print_headless_error(output_json, str(e))
            return 1

    exit_code = asyncio.run(async_run())
    raise typer.Exit(code=exit_code)


def _serialize_message(msg: object) -> dict:
    """Serialize a message object to a JSON-compatible dictionary.

    Per hard-break policy (state.py:167-171), all messages MUST be dicts.
    Non-dict messages indicate a bug upstream.
    """
    if isinstance(msg, dict):
        return msg
    raise TypeError(f"Expected dict message, got {type(msg).__name__}")


if __name__ == "__main__":
    app()
