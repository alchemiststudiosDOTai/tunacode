"""CLI entry point for TunaCode."""

import asyncio
import sys
from pathlib import Path

import typer

from tunacode.core import ConfigurationError, UserAbortError
from tunacode.core.session import StateManager
from tunacode.core.ui_api.configuration import ApplicationSettings, get_model_context_window
from tunacode.core.ui_api.constants import ENV_OPENAI_BASE_URL
from tunacode.core.ui_api.system_paths import check_for_updates

from tunacode.ui.repl_support import run_textual_repl
from tunacode.ui.rpc.mode import apply_rpc_cwd, run_rpc_mode, validate_rpc_cwd

DEFAULT_TIMEOUT_SECONDS = 600
BASE_URL_HELP_TEXT = "API base URL (e.g., https://openrouter.ai/api/v1)"

app_settings = ApplicationSettings()
app = typer.Typer(help="TunaCode - OS AI-powered development assistant")
state_manager: StateManager | None = None


def _get_state_manager() -> StateManager:
    """Lazily construct the state manager after CLI parsing succeeds."""
    global state_manager
    if state_manager is None:
        state_manager = StateManager()
    return state_manager


def _reset_state_manager() -> None:
    global state_manager
    state_manager = None


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

    state_manager.session.user_config["env"][ENV_OPENAI_BASE_URL] = base_url


async def _run_textual_app(*, model: str | None, baseurl: str | None, show_setup: bool) -> None:
    try:
        try:
            sm = _get_state_manager()
        except ConfigurationError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return

        _apply_base_url_override(sm, baseurl)

        update_task = asyncio.create_task(asyncio.to_thread(check_for_updates), name="update_check")
        update_task.add_done_callback(_handle_background_task_error)

        if model:
            sm.session.current_model = model

        try:
            await run_textual_repl(sm, show_setup=show_setup)
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
    finally:
        _reset_state_manager()


def _run_textual_cli(*, model: str | None, baseurl: str | None, show_setup: bool) -> None:
    asyncio.run(_run_textual_app(model=model, baseurl=baseurl, show_setup=show_setup))


async def _run_rpc_app(
    *,
    cwd: Path | None,
    model: str | None,
    baseurl: str | None,
    auto_approve: bool,
) -> None:
    _ = auto_approve
    try:
        if cwd is not None:
            apply_rpc_cwd(cwd)

        try:
            sm = _get_state_manager()
        except ConfigurationError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return

        _apply_base_url_override(sm, baseurl)

        if model:
            sm.session.current_model = model
            sm.session.conversation.max_tokens = get_model_context_window(model)

        await run_rpc_mode(state_manager=sm)
    finally:
        _reset_state_manager()


def _run_rpc_cli(
    *,
    cwd: str | None,
    model: str | None,
    baseurl: str | None,
    auto_approve: bool,
) -> None:
    try:
        validated_cwd = validate_rpc_cwd(cwd)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from exc

    asyncio.run(
        _run_rpc_app(
            cwd=validated_cwd,
            model=model,
            baseurl=baseurl,
            auto_approve=auto_approve,
        )
    )


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
        return
    _run_textual_cli(model=model, baseurl=baseurl, show_setup=setup or not _config_exists())


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

    _run_textual_cli(model=model, baseurl=baseurl, show_setup=setup or not _config_exists())


@app.command(name="rpc")
def rpc(
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory for the RPC session."),
    baseurl: str | None = typer.Option(None, "--baseurl", help=BASE_URL_HELP_TEXT),
    model: str | None = typer.Option(
        None, "--model", help="Default model to use (e.g., openai/gpt-4)"
    ),
    auto_approve: bool = typer.Option(
        False,
        "--auto-approve",
        help="Accepted for protocol compatibility. Current TunaCode tools are non-interactive.",
    ),
) -> None:
    """Run TunaCode in long-lived JSONL RPC mode."""
    _run_rpc_cli(
        cwd=cwd,
        model=model,
        baseurl=baseurl,
        auto_approve=auto_approve,
    )


if __name__ == "__main__":
    app()
