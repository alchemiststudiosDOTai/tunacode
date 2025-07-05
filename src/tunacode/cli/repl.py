"""
Module: tunacode.cli.repl

Interactive REPL (Read-Eval-Print Loop) implementation for TunaCode.
Handles user input, command processing, and agent interaction in an interactive shell.
"""

import json
import os
import subprocess
from asyncio.exceptions import CancelledError
from pathlib import Path

from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.application.current import get_app
from pydantic_ai.exceptions import UnexpectedModelBehavior

from tunacode.configuration.settings import ApplicationSettings
from tunacode.core.agents import main as agent
from tunacode.core.agents.main import patch_tool_messages
from tunacode.core.tool_handler import ToolHandler
from tunacode.exceptions import AgentError, UserAbortError, ValidationError
from tunacode.ui import console as ui
from tunacode.ui.tool_ui import ToolUI
from tunacode.utils.security import CommandSecurityError, safe_subprocess_run

from ..types import CommandContext, CommandResult, StateManager, ToolArgs
from .commands import CommandRegistry

# Tool UI instance
_tool_ui = ToolUI()

# Message constants
MSG_OPERATION_ABORTED = "Operation aborted."
MSG_OPERATION_ABORTED_BY_USER = "Operation aborted by user."
MSG_TOOL_INTERRUPTED = "Tool execution was interrupted"
MSG_REQUEST_CANCELLED = "Request cancelled"
MSG_REQUEST_COMPLETED = "Request completed"
MSG_JSON_RECOVERY = "Recovered using JSON tool parsing"
MSG_SESSION_ENDED = "Session ended. Happy coding!"
MSG_AGENT_BUSY = "Agent is busy, press Ctrl+C to interrupt."
MSG_HIT_CTRL_C = "Hit Ctrl+C again to exit"

# Shell constants
SHELL_ENV_VAR = "SHELL"
DEFAULT_SHELL = "bash"


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


async def _tool_confirm(tool_call, node, state_manager: StateManager):
    """Confirm tool execution with separated business logic and UI."""
    # Create tool handler with state
    tool_handler = ToolHandler(state_manager)
    args = _parse_args(tool_call.args)

    # Check if confirmation is needed
    if not tool_handler.should_confirm(tool_call.tool_name):
        # Log MCP tools when skipping confirmation
        app_settings = ApplicationSettings()
        if tool_call.tool_name not in app_settings.internal_tools:
            title = _tool_ui._get_tool_title(tool_call.tool_name)
            await _tool_ui.log_mcp(title, args)
        return

    # Stop spinner during user interaction (only if not streaming)
    if not state_manager.session.is_streaming_active and state_manager.session.spinner:
        state_manager.session.spinner.stop()

    # Create confirmation request
    request = tool_handler.create_confirmation_request(tool_call.tool_name, args)

    # Show UI and get response
    response = await _tool_ui.show_confirmation(request, state_manager)

    # Process the response
    if not tool_handler.process_confirmation(response, tool_call.tool_name):
        raise UserAbortError("User aborted.")

    await ui.line()  # Add line after user input

    # Restart spinner (only if not streaming)
    if not state_manager.session.is_streaming_active and state_manager.session.spinner:
        state_manager.session.spinner.start()


async def _tool_handler(part, node, state_manager: StateManager):
    """Handle tool execution with separated business logic and UI."""
    # Create tool handler with state first to check if confirmation is needed
    tool_handler = ToolHandler(state_manager)

    # Only show tool info for tools that require confirmation
    if tool_handler.should_confirm(part.tool_name):
        await ui.info(f"Tool({part.tool_name})")

    # Stop spinner only if not streaming
    if not state_manager.session.is_streaming_active and state_manager.session.spinner:
        state_manager.session.spinner.stop()

    # Track if we need to stop/restart streaming panel
    streaming_panel = None
    if state_manager.session.is_streaming_active and hasattr(
        state_manager.session, "streaming_panel"
    ):
        streaming_panel = state_manager.session.streaming_panel
        # Stop the streaming panel to prevent UI interference during confirmation
        if streaming_panel and tool_handler.should_confirm(part.tool_name):
            await streaming_panel.stop()

    try:
        args = _parse_args(part.args)

        # Use a synchronous function in run_in_terminal to avoid async deadlocks
        def confirm_func():
            # Skip confirmation if not needed
            if not tool_handler.should_confirm(part.tool_name):
                return False

            # Create confirmation request
            request = tool_handler.create_confirmation_request(part.tool_name, args)

            # Show sync UI and get response
            response = _tool_ui.show_sync_confirmation(request)

            # Process the response
            if not tool_handler.process_confirmation(response, part.tool_name):
                return True  # Abort
            return False  # Continue

        # Run the confirmation in the terminal
        should_abort = await run_in_terminal(confirm_func)

        if should_abort:
            raise UserAbortError("User aborted.")

    except UserAbortError:
        patch_tool_messages(MSG_OPERATION_ABORTED_BY_USER, state_manager)
        raise
    finally:
        # Restart streaming panel if it was stopped
        if streaming_panel and tool_handler.should_confirm(part.tool_name):
            await streaming_panel.start()

        # Restart spinner only if not streaming
        if (
            not state_manager.session.is_streaming_active
            and state_manager.session.spinner
        ):
            state_manager.session.spinner.start()


# Initialize command registry
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
    # Create command context
    context = CommandContext(
        state_manager=state_manager, process_request=process_request
    )

    try:
        # Set the process_request callback for commands that need it
        _command_registry.set_process_request_callback(process_request)

        # Execute the command
        return await _command_registry.execute(command, context)
    except ValidationError as e:
        await ui.error(str(e))


async def process_request(text: str, state_manager: StateManager, output: bool = True):
    """Process input using the agent, handling cancellation safely."""
    state_manager.session.spinner = await ui.spinner(
        True, state_manager.session.spinner, state_manager
    )
    try:
        # Patch any orphaned tool calls from previous requests before proceeding
        patch_tool_messages(MSG_TOOL_INTERRUPTED, state_manager)

        # Clear tracking for new request when thoughts are enabled
        if state_manager.session.show_thoughts:
            state_manager.session.tool_calls = []
            # Don't clear files_in_context - keep it cumulative for the session
            state_manager.session.iteration_count = 0
            state_manager.session.current_iteration = 0

        # Track message start for thoughts display
        start_idx = len(state_manager.session.messages)

        # Create a partial function that includes state_manager
        def tool_callback_with_state(part, node):
            return _tool_handler(part, node, state_manager)

        # Expand @file references before sending to the agent
        try:
            from tunacode.utils.text_utils import expand_file_refs

            text, referenced_files = expand_file_refs(text)
            # Track the referenced files
            for file_path in referenced_files:
                state_manager.session.files_in_context.add(file_path)
        except ValueError as e:
            await ui.error(str(e))
            return

        # Check if streaming is enabled (default: True for better UX)
        enable_streaming = state_manager.session.user_config.get("settings", {}).get(
            "enable_streaming", True
        )

        if enable_streaming:
            # Stop spinner before starting streaming display (Rich.Live conflict)
            await ui.spinner(False, state_manager.session.spinner, state_manager)

            # Mark that streaming is active to prevent spinner conflicts
            state_manager.session.is_streaming_active = True

            # Use streaming agent processing
            streaming_panel = ui.StreamingAgentPanel()
            await streaming_panel.start()

            # Store streaming panel reference in session for tool handler access
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
                # Clear streaming panel reference
                state_manager.session.streaming_panel = None
                # Mark streaming as inactive
                state_manager.session.is_streaming_active = False
                # Don't restart spinner - it will be stopped in the outer finally block anyway
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
                output = res.result.output
                # Extract complex conditions into explaining variables
                is_string_output = isinstance(output, str)
                is_json_thought = (
                    output.strip().startswith('{"thought"')
                    if is_string_output
                    else False
                )
                has_tool_uses = '"tool_uses"' in output if is_string_output else False
                is_displayable = is_string_output and not (
                    is_json_thought or has_tool_uses
                )

                if is_displayable:
                    await ui.agent(output)

            # Always show files in context after agent response
            if state_manager.session.files_in_context:
                # Extract just filenames from full paths for readability
                filenames = [
                    Path(f).name for f in sorted(state_manager.session.files_in_context)
                ]
                await ui.muted(f"\nFiles in context: {', '.join(filenames)}")
    except CancelledError:
        await ui.muted(MSG_REQUEST_CANCELLED)
    except UserAbortError:
        await ui.muted(MSG_OPERATION_ABORTED)
    except UnexpectedModelBehavior as e:
        error_message = str(e)
        await ui.muted(error_message)
        patch_tool_messages(error_message, state_manager)
    except Exception as e:
        # Check if this might be a tool calling failure that we can recover from
        error_str = str(e).lower()
        if any(
            keyword in error_str for keyword in ["tool", "function", "call", "schema"]
        ):
            # Try to extract and execute tool calls from the last response
            if state_manager.session.messages:
                last_msg = state_manager.session.messages[-1]
                if hasattr(last_msg, "parts"):
                    for part in last_msg.parts:
                        if hasattr(part, "content") and isinstance(part.content, str):
                            from tunacode.core.agents.main import (
                                extract_and_execute_tool_calls,
                            )

                            try:
                                # Create a partial function that includes state_manager
                                def tool_callback_with_state(part, node):
                                    return _tool_handler(part, node, state_manager)

                                await extract_and_execute_tool_calls(
                                    part.content,
                                    tool_callback_with_state,
                                    state_manager,
                                )
                                await ui.warning(f" {MSG_JSON_RECOVERY}")
                                return  # Successfully recovered
                            except Exception:
                                pass  # Fallback failed, continue with normal error handling

        # Wrap unexpected exceptions in AgentError for better tracking
        agent_error = AgentError(f"Agent processing failed: {str(e)}")
        agent_error.__cause__ = e  # Preserve the original exception chain
        await ui.error(str(e))
    finally:
        await ui.spinner(False, state_manager.session.spinner, state_manager)
        state_manager.session.current_task = None

        # Force refresh of the multiline input prompt to restore placeholder
        if "multiline" in state_manager.session.input_sessions:
            await run_in_terminal(
                lambda: state_manager.session.input_sessions[
                    "multiline"
                ].app.invalidate()
            )


async def repl(state_manager: StateManager):
    action = None
    ctrl_c_pressed = False

    await ui.muted(f"• Model: {state_manager.session.current_model}")
    await ui.success("Ready to assist")
    await ui.line()

    instance = agent.get_or_create_agent(
        state_manager.session.current_model, state_manager
    )

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

                # Show tool-style header for bash commands
                cmd_display = command if command else "Interactive shell"
                await ui.panel(
                    "Tool(bash)", f"Command: {cmd_display}", border_style="yellow"
                )

                def run_shell():
                    try:
                        if command:
                            # Use secure subprocess execution for shell commands
                            # Note: User shell commands are inherently risky but this is by design
                            # We validate but allow shell features since it's explicit user intent
                            try:
                                result = safe_subprocess_run(
                                    command,
                                    shell=True,
                                    validate=True,  # Still validate for basic safety
                                    capture_output=False,
                                )
                                if result.returncode != 0:
                                    print(
                                        f"\nCommand exited with code {result.returncode}"
                                    )
                            except CommandSecurityError as e:
                                print(f"\nSecurity validation failed: {str(e)}")
                                print(
                                    "If you need to run this command, please ensure it's safe."
                                )
                        else:
                            shell = os.environ.get(SHELL_ENV_VAR, DEFAULT_SHELL)
                            subprocess.run(shell)  # Interactive shell is safe
                    except Exception as e:
                        print(f"\nShell command failed: {str(e)}")

                await run_in_terminal(run_shell)
                await ui.line()
                continue

            # Check if another task is already running
            if (
                state_manager.session.current_task
                and not state_manager.session.current_task.done()
            ):
                await ui.muted(MSG_AGENT_BUSY)
                continue

            state_manager.session.current_task = get_app().create_background_task(
                process_request(line, state_manager)
            )

    if action == "restart":
        await repl(state_manager)
    else:
        session_total = state_manager.session.session_total_usage
        if session_total:
            prompt = session_total.get("prompt_tokens", 0)
            completion = session_total.get("completion_tokens", 0)
            total_tokens = prompt + completion
            total_cost = session_total.get("cost", 0)

            summary = (
                f"\n[bold cyan]TunaCode Session Summary[/bold cyan]\n"
                f"  - Total Tokens:      {total_tokens:,}\n"
                f"  - Prompt Tokens:     {prompt:,}\n"
                f"  - Completion Tokens: {completion:,}\n"
                f"  - [bold green]Total Session Cost: ${total_cost:.4f}[/bold green]"
            )
            ui.console.print(summary)

        await ui.info(MSG_SESSION_ENDED)
