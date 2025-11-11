"""Interactive REPL implementation for TunaCode."""

import asyncio
import logging
import os
import subprocess
from asyncio.exceptions import CancelledError
from pathlib import Path

from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.application.current import get_app
from pydantic_ai.exceptions import UnexpectedModelBehavior

from tunacode.configuration.models import ModelRegistry
from tunacode.constants import DEFAULT_CONTEXT_WINDOW
from tunacode.core import agents as agent
from tunacode.core.agents import patch_tool_messages
from tunacode.core.token_usage.api_response_parser import ApiResponseParser
from tunacode.core.token_usage.cost_calculator import CostCalculator
from tunacode.core.token_usage.usage_tracker import UsageTracker
from tunacode.exceptions import UserAbortError, ValidationError
from tunacode.ui import console as ui
from tunacode.ui.output import get_context_window_display
from tunacode.utils.security import CommandSecurityError, safe_subprocess_run

from ..types import CommandContext, CommandResult, StateManager
from .commands import CommandRegistry
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


_command_registry = CommandRegistry()
_command_registry.register_all_default_commands()


async def _handle_command(command: str, state_manager: StateManager) -> CommandResult:
    """Handles a command string using the command registry."""
    context = CommandContext(state_manager=state_manager, process_request=execute_repl_request)
    try:
        _command_registry.set_process_request_callback(execute_repl_request)
        return await _command_registry.execute(command, context)
    except ValidationError as e:
        await ui.error(str(e))
        return None


def _extract_feedback_from_last_message(state_manager: StateManager) -> str | None:
    """Extract user guidance feedback from recent messages in session.messages.

    When option 3 is selected with feedback, a message is added with format:
    "Tool '...' execution cancelled before running.\nUser guidance:\n{guidance}\n..."

    Note: patch_tool_messages() adds "Operation aborted by user." AFTER the feedback,
    so we check the last few messages, not just the last one.

    Args:
        state_manager: State manager containing session messages

    Returns:
        The guidance text if found, None otherwise
    """
    if not state_manager.session.messages:
        return None

    # Check last 3 messages since patch_tool_messages() adds a message after feedback
    messages_to_check = state_manager.session.messages[-3:]

    for msg in reversed(messages_to_check):
        # Extract content from message parts
        if not hasattr(msg, "parts"):
            continue

        for part in msg.parts:
            if hasattr(part, "content") and isinstance(part.content, str):
                content = part.content

                # Look for "User guidance:" pattern
                if "User guidance:" in content:
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if "User guidance:" in line and i + 1 < len(lines):
                            guidance = lines[i + 1].strip()
                            # Only return non-empty guidance
                            cancelled_msg = "User cancelled without additional instructions."
                            if guidance and guidance != cancelled_msg:
                                return guidance

    return None


async def execute_repl_request(text: str, state_manager: StateManager, output: bool = True):
    """Process input using the agent, handling cancellation safely."""
    import uuid

    from tunacode.utils.text_utils import expand_file_refs

    state_manager.session.request_id = str(uuid.uuid4())

    if getattr(state_manager.session, "operation_cancelled", False) is True:
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

        def tool_callback_with_state(part, _):
            return tool_handler(part, state_manager)

        try:
            text, referenced_files = expand_file_refs(text)
            state_manager.session.files_in_context.update(referenced_files)
        except ValueError as e:
            await ui.error(str(e))
            return

        if getattr(state_manager.session, "operation_cancelled", False) is True:
            raise CancelledError("Operation was cancelled")

        enable_streaming = state_manager.session.user_config.get("settings", {}).get(
            "enable_streaming", True
        )

        # Create UsageTracker to ensure session cost tracking
        model_registry = ModelRegistry()
        parser = ApiResponseParser()
        calculator = CostCalculator(model_registry)
        usage_tracker = UsageTracker(parser, calculator, state_manager)

        if enable_streaming:
            await ui.spinner(False, state_manager.session.spinner, state_manager)
            state_manager.session.is_streaming_active = True
            streaming_panel = ui.StreamingAgentPanel(
                debug=bool(state_manager.session.show_thoughts)
            )
            await streaming_panel.start()
            state_manager.session.streaming_panel = streaming_panel

            try:
                res = await agent.process_request(
                    text,
                    state_manager.session.current_model,
                    state_manager,
                    tool_callback=tool_callback_with_state,
                    streaming_callback=lambda content: streaming_panel.update(content),
                    usage_tracker=usage_tracker,
                )
            finally:
                await streaming_panel.stop()
                state_manager.session.streaming_panel = None
                state_manager.session.is_streaming_active = False
                # Emit source-side streaming diagnostics if thoughts are enabled
                if state_manager.session.show_thoughts:
                    try:
                        raw = getattr(state_manager.session, "_debug_raw_stream_accum", "") or ""
                        events = getattr(state_manager.session, "_debug_events", []) or []
                        raw_first5 = repr(raw[:5])
                        await ui.muted(
                            f"[debug] raw_stream_first5={raw_first5} total_len={len(raw)}"
                        )
                        for line in events:
                            await ui.muted(line)
                    except Exception:
                        # Don't let diagnostics break normal flow
                        pass
        else:
            res = await agent.process_request(
                text,
                state_manager.session.current_model,
                state_manager,
                tool_callback=tool_callback_with_state,
                usage_tracker=usage_tracker,
            )

        if output:
            if state_manager.session.show_thoughts:
                for msg in state_manager.session.messages[start_idx:]:
                    if isinstance(msg, dict) and "thought" in msg:
                        await ui.muted(f"THOUGHT: {msg['thought']}")
            if not enable_streaming:
                if (
                    not hasattr(res, "result")
                    or res.result is None
                    or not hasattr(res.result, "output")
                ):
                    await ui.muted(MSG_REQUEST_COMPLETED)
                else:
                    await display_agent_output(res, enable_streaming, state_manager)
            if state_manager.session.files_in_context:
                filenames = [Path(f).name for f in sorted(state_manager.session.files_in_context)]
                await ui.muted(f"Files in context: {', '.join(filenames)}")

    except CancelledError:
        await ui.muted(MSG_REQUEST_CANCELLED)
    except UserAbortError:
        # CLAUDE_ANCHOR[7b2c1d4e]: Guided aborts inject user instructions; skip legacy banner.
        # Check if there's feedback to process immediately
        feedback = _extract_feedback_from_last_message(state_manager)
        if feedback:
            # Process the feedback as a new request immediately
            # Stop spinner first to clean up state before recursive call
            await ui.spinner(False, state_manager.session.spinner, state_manager)
            # Clear current_task so recursive call can set its own
            state_manager.session.current_task = None
            try:
                await execute_repl_request(feedback, state_manager, output=output)
            except Exception:
                # If recursive call fails, don't let it bubble up - just continue
                pass
            # Return early to skip the finally block's cleanup (already done above)
            return
        # No feedback, just abort normally
        pass
    except UnexpectedModelBehavior as e:
        await ui.muted(str(e))
        patch_tool_messages(str(e), state_manager)
    except Exception as e:
        if not await attempt_tool_recovery(e, state_manager):
            await ui.error(str(e))
    finally:
        await ui.spinner(False, state_manager.session.spinner, state_manager)
        state_manager.session.current_task = None
        if hasattr(state_manager.session, "operation_cancelled"):
            state_manager.session.operation_cancelled = False
        if "multiline" in state_manager.session.input_sessions:
            await run_in_terminal(
                lambda: state_manager.session.input_sessions["multiline"].app.invalidate()
            )


# Backwards compatibility: exported name expected by external integrations/tests
process_request = execute_repl_request


async def warm_code_index():
    """Pre-warm the code index in background for faster directory operations."""
    try:
        from tunacode.core.code_index import CodeIndex

        # Build index in thread to avoid blocking
        index = await asyncio.to_thread(lambda: CodeIndex.get_instance())
        await asyncio.to_thread(index.build_index)

        logger.debug(f"Code index pre-warmed with {len(index._all_files)} files")
    except Exception as e:
        logger.debug(f"Failed to pre-warm code index: {e}")


async def repl(state_manager: StateManager):
    """Main REPL loop that handles user interaction and input processing."""
    import time

    # Start pre-warming code index in background (non-blocking)
    asyncio.create_task(warm_code_index())

    action = None
    abort_pressed = False
    last_abort_time = 0.0

    max_tokens = (
        state_manager.session.user_config.get("context_window_size") or DEFAULT_CONTEXT_WINDOW
    )
    state_manager.session.max_tokens = max_tokens
    state_manager.session.update_token_count()

    async def show_context():
        context = get_context_window_display(state_manager.session.total_tokens, max_tokens)

        # Get session cost for display
        session_cost = 0.0
        if state_manager.session.session_total_usage:
            session_cost = float(state_manager.session.session_total_usage.get("cost", 0.0) or 0.0)

        await ui.muted(f"• Model: {state_manager.session.current_model} • {context}")
        if session_cost > 0:
            await ui.muted(f"• Session Cost: ${session_cost:.4f}")

    # Always show context
    await show_context()

    # Show startup message only once
    if not hasattr(state_manager.session, "_startup_shown"):
        await ui.success("Ready to assist")
        state_manager.session._startup_shown = True

        # Offer tutorial to first-time users
        await _offer_tutorial_if_appropriate(state_manager)

    instance = agent.get_or_create_agent(state_manager.session.current_model, state_manager)

    async with instance.run_mcp_servers():
        while True:
            try:
                line = await ui.multiline_input(state_manager, _command_registry)
            except UserAbortError:
                current_time = time.time()
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
                    line = action
                else:
                    continue

            if line.startswith("!"):
                command = line[1:].strip()
                await ui.panel(
                    "Tool(bash)",
                    f"Command: {command or 'Interactive shell'}",
                    border_style="yellow",
                )

                def run_shell():
                    try:
                        if command:
                            result = safe_subprocess_run(
                                command, shell=True, validate=True, capture_output=False
                            )
                            if result.returncode != 0:
                                ui.console.print(f"\nCommand exited with code {result.returncode}")
                        else:
                            subprocess.run(os.environ.get(SHELL_ENV_VAR, DEFAULT_SHELL))
                    except CommandSecurityError as e:
                        ui.console.print(f"\nSecurity validation failed: {str(e)}")
                    except Exception as e:
                        ui.console.print(f"\nShell command failed: {str(e)}")

                await run_in_terminal(run_shell)
                continue

            if state_manager.session.current_task and not state_manager.session.current_task.done():
                await ui.muted(MSG_AGENT_BUSY)
                continue

            if hasattr(state_manager.session, "operation_cancelled"):
                state_manager.session.operation_cancelled = False

            state_manager.session.current_task = get_app().create_background_task(
                execute_repl_request(line, state_manager)
            )
            await state_manager.session.current_task

            state_manager.session.update_token_count()
            await show_context()

    if action == "restart":
        await repl(state_manager)
    else:
        session_total = state_manager.session.session_total_usage
        if session_total:
            try:
                total_tokens = int(session_total.get("prompt_tokens", 0) or 0) + int(
                    session_total.get("completion_tokens", 0) or 0
                )
                total_cost = float(session_total.get("cost", 0) or 0)
                if total_tokens > 0 or total_cost > 0:
                    ui.console.print(
                        f"\n[bold cyan]TunaCode Session Summary[/bold cyan]\n"
                        f"  - Total Tokens: {total_tokens:,}\n"
                        f"  - Total Cost: ${total_cost:.4f}"
                    )
            except (TypeError, ValueError):
                pass
        await ui.info(MSG_SESSION_ENDED)


async def _offer_tutorial_if_appropriate(state_manager: StateManager) -> None:
    """Offer tutorial to first-time users if appropriate."""
    try:
        from tunacode.tutorial import TutorialManager

        tutorial_manager = TutorialManager(state_manager)

        # Check if we should offer tutorial
        if await tutorial_manager.should_offer_tutorial():
            # Offer tutorial to user
            accepted = await tutorial_manager.offer_tutorial()
            if accepted:
                # Run tutorial
                await tutorial_manager.run_tutorial()
    except ImportError:
        # Tutorial system not available, silently continue
        pass
    except Exception as e:
        # Don't let tutorial errors crash the REPL
        logger.warning(f"Tutorial offer failed: {e}")
