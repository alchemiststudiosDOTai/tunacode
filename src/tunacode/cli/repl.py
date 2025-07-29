"""
Module: tunacode.cli.repl

Interactive REPL (Read-Eval-Print Loop) implementation for TunaCode.
Handles user input, command processing, and agent interaction in an interactive shell.
"""

# ============================================================================
# IMPORTS AND DEPENDENCIES
# ============================================================================

import json
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
from tunacode.core.tool_handler import ToolHandler
from tunacode.exceptions import AgentError, UserAbortError, ValidationError
from tunacode.ui import console as ui
from tunacode.ui.output import get_context_window_display
from tunacode.ui.tool_ui import ToolUI
from tunacode.utils.security import CommandSecurityError, safe_subprocess_run

from ..types import CommandContext, CommandResult, StateManager, ToolArgs
from .commands import CommandRegistry

# ============================================================================
# MODULE-LEVEL CONSTANTS AND CONFIGURATION
# ============================================================================

_tool_ui = ToolUI()

MSG_OPERATION_ABORTED = "Operation aborted."
MSG_OPERATION_ABORTED_BY_USER = "Operation aborted by user."
MSG_TOOL_INTERRUPTED = "Tool execution was interrupted"
MSG_REQUEST_CANCELLED = "Request cancelled"
MSG_REQUEST_COMPLETED = "Request completed"
MSG_JSON_RECOVERY = "Recovered using JSON tool parsing"
MSG_SESSION_ENDED = "Session ended. Happy coding!"
MSG_AGENT_BUSY = "Agent is busy, press Ctrl+C to interrupt."
MSG_HIT_CTRL_C = "Hit Ctrl+C again to exit"
SHELL_ENV_VAR = "SHELL"
DEFAULT_SHELL = "bash"

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def _parse_args(args) -> ToolArgs:
    """
    Parse tool arguments from a JSON string or dictionary.

    Args:
        args (str or dict): A JSON-formatted string or a dictionary containing tool arguments.

    Returns:
        dict: The parsed arguments.

    Raises:
        ValueError: If 'args' is not a string or dictionary, or if the string is not valid JSON.
    """
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            raise ValidationError(f"Invalid JSON: {args}")
    elif isinstance(args, dict):
        return args
    else:
        raise ValidationError(f"Invalid args type: {type(args)}")


# ============================================================================
# TOOL EXECUTION AND CONFIRMATION HANDLERS
# ============================================================================


async def _tool_handler(part, state_manager: StateManager):
    """Handle tool execution with separated business logic and UI."""
    tool_handler = ToolHandler(state_manager)

    if tool_handler.should_confirm(part.tool_name):
        await ui.info(f"Tool({part.tool_name})")

    if not state_manager.session.is_streaming_active and state_manager.session.spinner:
        state_manager.session.spinner.stop()

    streaming_panel = None
    if state_manager.session.is_streaming_active and hasattr(
        state_manager.session, "streaming_panel"
    ):
        streaming_panel = state_manager.session.streaming_panel
        if streaming_panel and tool_handler.should_confirm(part.tool_name):
            await streaming_panel.stop()

    try:
        args = _parse_args(part.args)

        def confirm_func():
            if not tool_handler.should_confirm(part.tool_name):
                return False
            request = tool_handler.create_confirmation_request(part.tool_name, args)

            response = _tool_ui.show_sync_confirmation(request)

            if not tool_handler.process_confirmation(response, part.tool_name):
                return True  # Abort
            return False  # Continue

        should_abort = await run_in_terminal(confirm_func)

        if should_abort:
            raise UserAbortError("User aborted.")

    except UserAbortError:
        patch_tool_messages(MSG_OPERATION_ABORTED_BY_USER, state_manager)
        raise
    finally:
        if streaming_panel and tool_handler.should_confirm(part.tool_name):
            await streaming_panel.start()

        if not state_manager.session.is_streaming_active and state_manager.session.spinner:
            state_manager.session.spinner.start()


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


# ============================================================================
# ERROR RECOVERY
# ============================================================================


async def _attempt_tool_recovery(e: Exception, state_manager: StateManager) -> bool:
    """
    Attempt to recover from tool calling failures using guard clauses.

    Returns:
        bool: True if recovery was successful, False otherwise
    """
    error_str = str(e).lower()
    tool_keywords = ["tool", "function", "call", "schema"]
    if not any(keyword in error_str for keyword in tool_keywords):
        return False

    if not state_manager.session.messages:
        return False

    last_msg = state_manager.session.messages[-1]
    if not hasattr(last_msg, "parts"):
        return False

    for part in last_msg.parts:
        if not hasattr(part, "content") or not isinstance(part.content, str):
            continue

        try:
            from tunacode.core.agents.main import extract_and_execute_tool_calls

            def tool_callback_with_state(part, node):
                return _tool_handler(part, state_manager)

            await extract_and_execute_tool_calls(
                part.content, tool_callback_with_state, state_manager
            )

            await ui.warning(f" {MSG_JSON_RECOVERY}")
            return True

        except Exception as e:
            logger.debug(f"Failed to check triple quotes: {e}")
            continue

    return False


# ============================================================================
# AGENT OUTPUT DISPLAY
# ============================================================================


async def _display_agent_output(res, enable_streaming: bool) -> None:
    """Display agent output using guard clauses to flatten nested conditionals."""
    if enable_streaming:
        return

    if not hasattr(res, "result") or res.result is None or not hasattr(res.result, "output"):
        await ui.muted(MSG_REQUEST_COMPLETED)
        return

    output = res.result.output

    if not isinstance(output, str):
        return

    if output.strip().startswith('{"thought"'):
        return

    if '"tool_uses"' in output:
        return

    await ui.agent(output)


# ============================================================================
# MAIN AGENT REQUEST PROCESSING
# ============================================================================


async def process_request(text: str, state_manager: StateManager, output: bool = True):
    """Process input using the agent, handling cancellation safely."""

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

        def tool_callback_with_state(part, node):
            return _tool_handler(part, state_manager)

        try:
            from tunacode.utils.text_utils import expand_file_refs

            text, referenced_files = expand_file_refs(text)
            for file_path in referenced_files:
                state_manager.session.files_in_context.add(file_path)
        except ValueError as e:
            await ui.error(str(e))
            return

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
                    state_manager.session.current_model,
                    text,
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
                state_manager.session.current_model,
                text,
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
                await _display_agent_output(res, enable_streaming)

            # Always show files in context after agent response
            if state_manager.session.files_in_context:
                filenames = [Path(f).name for f in sorted(state_manager.session.files_in_context)]
                await ui.muted(f"\nFiles in context: {', '.join(filenames)}")

    # --- ERROR HANDLING ---
    except CancelledError:
        await ui.muted(MSG_REQUEST_CANCELLED)
    except UserAbortError:
        await ui.muted(MSG_OPERATION_ABORTED_BY_USER)
    except UnexpectedModelBehavior as e:
        error_message = str(e)
        await ui.muted(error_message)
        patch_tool_messages(error_message, state_manager)
    except Exception as e:
        # Try tool recovery for tool-related errors
        if await _attempt_tool_recovery(e, state_manager):
            return  # Successfully recovered

        agent_error = AgentError(f"Agent processing failed: {str(e)}")
        agent_error.__cause__ = e  # Preserve the original exception chain
        await ui.error(str(e))
    finally:
        await ui.spinner(False, state_manager.session.spinner, state_manager)
        state_manager.session.current_task = None

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
    ctrl_c_pressed = False

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
                if ctrl_c_pressed:
                    break
                ctrl_c_pressed = True
                await ui.warning(MSG_HIT_CTRL_C)
                continue

            if not line:
                continue

            ctrl_c_pressed = False

            if line.lower() in ["exit", "quit"]:
                break

            if line.startswith("/"):
                action = await _handle_command(line, state_manager)
                if action == "restart":
                    break
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

            state_manager.session.current_task = get_app().create_background_task(
                process_request(line, state_manager)
            )

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
