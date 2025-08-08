"""
Module: tunacode.cli.repl

Interactive REPL (Read-Eval-Print Loop) implementation for TunaCode.
Handles user input, command processing, and agent interaction in an interactive shell.

CLAUDE_ANCHOR[repl-module]: Core REPL loop and user interaction handling
"""

# ============================================================================
# IMPORTS AND DEPENDENCIES
# ============================================================================

import logging
import os
import subprocess
from asyncio.exceptions import CancelledError
from pathlib import Path

from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.application.current import get_app
from pydantic_ai.exceptions import UnexpectedModelBehavior

from tunacode.constants import DEFAULT_CONTEXT_WINDOW
from tunacode.core.agents import main as agent
from tunacode.core.agents.main import patch_tool_messages
from tunacode.exceptions import AgentError, UserAbortError, ValidationError
from tunacode.ui import console as ui
from tunacode.ui.output import get_context_window_display
from tunacode.utils.security import CommandSecurityError, safe_subprocess_run

from ..types import CommandContext, CommandResult, StateManager
from .commands import CommandRegistry

# ============================================================================
# MODULE-LEVEL CONSTANTS AND CONFIGURATION
# ============================================================================
from .repl_components import attempt_tool_recovery, display_agent_output, tool_handler
from .repl_components.output_display import MSG_REQUEST_COMPLETED

MSG_OPERATION_ABORTED = "Operation aborted."
MSG_TOOL_INTERRUPTED = "Tool execution was interrupted"
MSG_REQUEST_CANCELLED = "Request cancelled"
MSG_SESSION_ENDED = "Session ended. Happy coding!"
MSG_AGENT_BUSY = "Agent is busy, press Ctrl+C to interrupt."
MSG_HIT_ABORT_KEY = "Hit ESC or Ctrl+C again to exit"
SHELL_ENV_VAR = "SHELL"
DEFAULT_SHELL = "bash"

# Configure logging
logger = logging.getLogger(__name__)

# The _parse_args function has been moved to repl_components.command_parser
# The _tool_handler function has been moved to repl_components.tool_executor


# ============================================================================
# COMMAND SYSTEM
# ============================================================================

_command_registry = CommandRegistry()
_command_registry.register_all_default_commands()


async def _handle_command(command: str, state_manager: StateManager) -> CommandResult:
    """
    Handles a command string using the command registry.

    Args:
        command: The command string entered by the user.
        state_manager: The state manager instance.

    Returns:
        Command result (varies by command).
    """
    context = CommandContext(state_manager=state_manager, process_request=process_request)

    try:
        _command_registry.set_process_request_callback(process_request)

        return await _command_registry.execute(command, context)
    except ValidationError as e:
        await ui.error(str(e))
        return None


# The _attempt_tool_recovery function has been moved to repl_components.error_recovery


# The _display_agent_output function has been moved to repl_components.output_display


# ============================================================================
# MAIN AGENT REQUEST PROCESSING
# ============================================================================


async def process_request(text: str, state_manager: StateManager, output: bool = True):
    """Process input using the agent, handling cancellation safely.

    CLAUDE_ANCHOR[process-request-repl]: REPL's main request processor with error handling
    """
    import uuid

    # Generate a unique ID for this request for correlated logging
    request_id = str(uuid.uuid4())
    logger.debug(
        "Processing new request", extra={"request_id": request_id, "input_text": text[:100]}
    )
    state_manager.session.request_id = request_id

    # Check for cancellation before starting (only if explicitly set to True)
    operation_cancelled = getattr(state_manager.session, "operation_cancelled", False)
    if operation_cancelled is True:
        logger.debug("Operation cancelled before processing started")
        raise CancelledError("Operation was cancelled")

    state_manager.session.spinner = await ui.spinner(
        True, state_manager.session.spinner, state_manager
    )
    try:
        patch_tool_messages(MSG_TOOL_INTERRUPTED, state_manager)

        if state_manager.session.show_thoughts:
            state_manager.session.tool_calls = []
            state_manager.session.iteration_count = 0
            state_manager.session.current_iteration = 0

        start_idx = len(state_manager.session.messages)

        def tool_callback_with_state(part, _node):
            return tool_handler(part, state_manager)

        try:
            from tunacode.utils.text_utils import expand_file_refs

            text, referenced_files = expand_file_refs(text)
            for file_path in referenced_files:
                state_manager.session.files_in_context.add(file_path)
        except ValueError as e:
            await ui.error(str(e))
            return

        # Check for cancellation before proceeding with agent call (only if explicitly set to True)
        operation_cancelled = getattr(state_manager.session, "operation_cancelled", False)
        if operation_cancelled is True:
            logger.debug("Operation cancelled before agent processing")
            raise CancelledError("Operation was cancelled")

        enable_streaming = state_manager.session.user_config.get("settings", {}).get(
            "enable_streaming", True
        )

        if enable_streaming:
            await ui.spinner(False, state_manager.session.spinner, state_manager)

            state_manager.session.is_streaming_active = True

            streaming_panel = ui.StreamingAgentPanel()
            await streaming_panel.start()

            state_manager.session.streaming_panel = streaming_panel

            try:

                async def streaming_callback(content: str):
                    await streaming_panel.update(content)

                res = await agent.process_request(
                    text,
                    state_manager.session.current_model,
                    state_manager,
                    tool_callback=tool_callback_with_state,
                    streaming_callback=streaming_callback,
                )
            finally:
                await streaming_panel.stop()
                state_manager.session.streaming_panel = None
                state_manager.session.is_streaming_active = False
        else:
            # Use normal agent processing
            res = await agent.process_request(
                text,
                state_manager.session.current_model,
                state_manager,
                tool_callback=tool_callback_with_state,
            )

        if output:
            if state_manager.session.show_thoughts:
                new_msgs = state_manager.session.messages[start_idx:]
                for msg in new_msgs:
                    if isinstance(msg, dict) and "thought" in msg:
                        await ui.muted(f"THOUGHT: {msg['thought']}")

            # Only display result if not streaming (streaming already showed content)
            if enable_streaming:
                pass  # Guard: streaming already showed content
            elif (
                not hasattr(res, "result")
                or res.result is None
                or not hasattr(res.result, "output")
            ):
                # Fallback: show that the request was processed
                await ui.muted(MSG_REQUEST_COMPLETED)
            else:
                # Use the dedicated function for displaying agent output
                await display_agent_output(res, enable_streaming)

            # Always show files in context after agent response
            if state_manager.session.files_in_context:
                filenames = [Path(f).name for f in sorted(state_manager.session.files_in_context)]
                await ui.muted(f"Files in context: {', '.join(filenames)}")

    # --- ERROR HANDLING ---
    except CancelledError:
        await ui.muted(MSG_REQUEST_CANCELLED)
    except UserAbortError:
        await ui.muted(MSG_OPERATION_ABORTED)
    except UnexpectedModelBehavior as e:
        error_message = str(e)
        await ui.muted(error_message)
        patch_tool_messages(error_message, state_manager)
    except Exception as e:
        # Try tool recovery for tool-related errors
        if await attempt_tool_recovery(e, state_manager):
            return  # Successfully recovered

        agent_error = AgentError(f"Agent processing failed: {str(e)}")
        agent_error.__cause__ = e  # Preserve the original exception chain
        await ui.error(str(e))
    finally:
        await ui.spinner(False, state_manager.session.spinner, state_manager)
        state_manager.session.current_task = None
        # Reset cancellation flag when task completes (if attribute exists)
        if hasattr(state_manager.session, "operation_cancelled"):
            state_manager.session.operation_cancelled = False

        if "multiline" in state_manager.session.input_sessions:
            await run_in_terminal(
                lambda: state_manager.session.input_sessions["multiline"].app.invalidate()
            )


# ============================================================================
# MAIN REPL LOOP
# ============================================================================


async def repl(state_manager: StateManager):
    """Main REPL loop that handles user interaction and input processing."""
    action = None
    abort_pressed = False
    last_abort_time = 0.0

    model_name = state_manager.session.current_model
    max_tokens = (
        state_manager.session.user_config.get("context_window_size") or DEFAULT_CONTEXT_WINDOW
    )
    state_manager.session.max_tokens = max_tokens

    state_manager.session.update_token_count()
    context_display = get_context_window_display(state_manager.session.total_tokens, max_tokens)

    # Only show startup info if thoughts are enabled or on first run
    if state_manager.session.show_thoughts or not hasattr(state_manager.session, "_startup_shown"):
        await ui.muted(f"• Model: {model_name} • {context_display}")
        await ui.success("Ready to assist")
        await ui.line()
        state_manager.session._startup_shown = True

    instance = agent.get_or_create_agent(state_manager.session.current_model, state_manager)

    async with instance.run_mcp_servers():
        while True:
            try:
                line = await ui.multiline_input(state_manager, _command_registry)
            except UserAbortError:
                import time

                current_time = time.time()

                # Reset if more than 3 seconds have passed
                if current_time - last_abort_time > 3.0:
                    abort_pressed = False

                if abort_pressed:
                    break

                abort_pressed = True
                last_abort_time = current_time
                await ui.warning(MSG_HIT_ABORT_KEY)
                continue

            if not line:
                continue

            abort_pressed = False

            if line.lower() in ["exit", "quit"]:
                break

            if line.startswith("/"):
                action = await _handle_command(line, state_manager)
                if action == "restart":
                    break
                elif isinstance(action, str) and action:
                    # If the command returned a string (e.g., from template shortcut),
                    # process it as a prompt
                    line = action
                    # Fall through to process as normal text
                else:
                    continue

            if line.startswith("!"):
                command = line[1:].strip()

                cmd_display = command if command else "Interactive shell"
                await ui.panel("Tool(bash)", f"Command: {cmd_display}", border_style="yellow")

                def run_shell():
                    try:
                        if command:
                            try:
                                result = safe_subprocess_run(
                                    command,
                                    shell=True,
                                    validate=True,  # Still validate for basic safety
                                    capture_output=False,
                                )
                                if result.returncode != 0:
                                    ui.console.print(
                                        f"\nCommand exited with code {result.returncode}"
                                    )
                            except CommandSecurityError as e:
                                ui.console.print(f"\nSecurity validation failed: {str(e)}")
                                ui.console.print(
                                    "If you need to run this command, please ensure it's safe."
                                )
                        else:
                            shell = os.environ.get(SHELL_ENV_VAR, DEFAULT_SHELL)
                            subprocess.run(shell)  # Interactive shell is safe
                    except Exception as e:
                        ui.console.print(f"\nShell command failed: {str(e)}")

                await run_in_terminal(run_shell)
                await ui.line()
                continue

            # --- AGENT REQUEST PROCESSING ---
            if state_manager.session.current_task and not state_manager.session.current_task.done():
                await ui.muted(MSG_AGENT_BUSY)
                continue

            # Reset cancellation flag for new operations (if attribute exists)
            if hasattr(state_manager.session, "operation_cancelled"):
                state_manager.session.operation_cancelled = False

            state_manager.session.current_task = get_app().create_background_task(
                process_request(line, state_manager)
            )
            await state_manager.session.current_task

            state_manager.session.update_token_count()
            context_display = get_context_window_display(
                state_manager.session.total_tokens, state_manager.session.max_tokens
            )
            # Only show model/context info if thoughts are enabled
            if state_manager.session.show_thoughts:
                await ui.muted(
                    f"• Model: {state_manager.session.current_model} • {context_display}"
                )

        if action == "restart":
            await repl(state_manager)
        else:
            # Show session cost summary if available
            session_total = state_manager.session.session_total_usage
            if session_total:
                try:
                    prompt = int(session_total.get("prompt_tokens", 0) or 0)
                    completion = int(session_total.get("completion_tokens", 0) or 0)
                    total_tokens = prompt + completion
                    total_cost = float(session_total.get("cost", 0) or 0)

                    # Only show summary if we have actual token usage
                    if state_manager.session.show_thoughts and (total_tokens > 0 or total_cost > 0):
                        summary = (
                            f"\n[bold cyan]TunaCode Session Summary[/bold cyan]\n"
                            f"  - Total Tokens:      {total_tokens:,}\n"
                            f"  - Prompt Tokens:     {prompt:,}\n"
                            f"  - Completion Tokens: {completion:,}\n"
                            f"  - [bold green]Total Session Cost: ${total_cost:.4f}[/bold green]"
                        )
                        ui.console.print(summary)
                except (TypeError, ValueError) as e:
                    # Skip displaying summary if values can't be converted to numbers
                    logger.debug(f"Failed to display token usage summary: {e}")

            await ui.info(MSG_SESSION_ENDED)
