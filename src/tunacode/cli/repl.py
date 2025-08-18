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
from tunacode.core.agents import main as agent
from tunacode.core.agents.main import patch_tool_messages
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


def _transform_to_implementation_request(original_request: str) -> str:
    """
    Transform a planning request into an implementation request.

    This ensures that after plan approval, the agent understands it should
    implement rather than plan again.
    """
    request = original_request.lower()

    if "plan" in request:
        request = request.replace("plan a ", "create a ")
        request = request.replace("plan an ", "create an ")
        request = request.replace("plan to ", "")
        request = request.replace("plan ", "create ")

    # Add clear implementation instruction
    implementation_request = f"{request}\n\nIMPORTANT: Actually implement and create the file(s) - do not just plan or outline. The plan has been approved, now execute the implementation."

    return implementation_request


async def _display_plan(plan_doc) -> None:
    """Display the plan in a formatted way."""
    if not plan_doc:
        await ui.error("⚠️ Error: No plan document found to display")
        return

    output = [f"[bold cyan]🎯 {plan_doc.title}[/bold cyan]", ""]

    if plan_doc.overview:
        output.extend([f"[bold]📝 Overview:[/bold] {plan_doc.overview}", ""])

    sections = [
        ("📝 Files to Modify:", plan_doc.files_to_modify, "•"),
        ("📄 Files to Create:", plan_doc.files_to_create, "•"),
        ("🧪 Testing Approach:", plan_doc.tests, "•"),
        ("✅ Success Criteria:", plan_doc.success_criteria, "•"),
        ("⚠️ Risks & Considerations:", plan_doc.risks, "•"),
        ("❓ Open Questions:", plan_doc.open_questions, "•"),
        ("📚 References:", plan_doc.references, "•"),
    ]

    for title, items, prefix in sections:
        if items:
            output.append(f"[bold]{title}[/bold]")
            output.extend(f"  {prefix} {item}" for item in items)
            output.append("")

    output.append("[bold]🔧 Implementation Steps:[/bold]")
    output.extend(f"  {i}. {step}" for i, step in enumerate(plan_doc.steps, 1))
    output.append("")

    if plan_doc.rollback:
        output.extend([f"[bold]🔄 Rollback Plan:[/bold] {plan_doc.rollback}", ""])

    await ui.panel("📋 IMPLEMENTATION PLAN", "\n".join(output), border_style="cyan")


async def _detect_and_handle_text_plan(state_manager, agent_response, original_request):
    """Detect if agent presented a plan in text format and handle it."""
    try:
        # Extract response text
        response_text = ""
        if hasattr(agent_response, "messages") and agent_response.messages:
            msg = agent_response.messages[-1]
            response_text = str(getattr(msg, "content", getattr(msg, "text", msg)))
        elif hasattr(agent_response, "result"):
            response_text = str(getattr(agent_response.result, "output", agent_response.result))
        else:
            response_text = str(agent_response)

        if "TUNACODE_TASK_COMPLETE" in response_text:
            await ui.warning(
                "⚠️ Agent failed to call present_plan tool. Please provide clearer instructions."
            )
            return

        if "present_plan(" in response_text:
            await ui.error(
                "❌ Agent showed present_plan as text instead of EXECUTING it as a tool!"
            )
            await ui.info("Try again with: 'Execute the present_plan tool to create a plan for...'")
            return

        # Check for plan indicators
        plan_indicators = {
            "plan for",
            "implementation plan",
            "here's a plan",
            "i'll create a plan",
            "plan to",
            "outline for",
            "overview:",
            "steps:",
        }
        has_plan = any(ind in response_text.lower() for ind in plan_indicators)
        has_structure = (
            any(x in response_text for x in ["1.", "2.", "•"]) and response_text.count("\n") > 5
        )

        if has_plan and has_structure:
            await ui.info("📋 Plan detected in text format - extracting for review")
            from tunacode.types import PlanDoc, PlanPhase

            plan_doc = PlanDoc(
                title="Implementation Plan",
                overview="Automated plan extraction from text",
                steps=["Review and implement the described functionality"],
                files_to_modify=[],
                files_to_create=[],
                success_criteria=[],
            )

            state_manager.session.plan_phase = PlanPhase.PLAN_READY
            state_manager.session.current_plan = plan_doc
            await _handle_plan_approval(state_manager, original_request)

    except Exception as e:
        logger.error(f"Error detecting text plan: {e}")


async def _handle_plan_approval(state_manager, original_request=None):
    """Handle plan approval when a plan has been presented via present_plan tool."""
    try:
        import time

        from tunacode.types import PlanPhase
        from tunacode.ui.keybindings import create_key_bindings

        state_manager.session.plan_phase = PlanPhase.REVIEW_DECISION
        plan_doc = state_manager.session.current_plan
        state_manager.exit_plan_mode(plan_doc)

        await ui.info("📋 Plan has been prepared and Plan Mode exited")
        await _display_plan(plan_doc)

        content = (
            "[bold cyan]The implementation plan has been presented.[/bold cyan]\n\n"
            "[yellow]Choose your action:[/yellow]\n\n"
            "  [bold green]a[/bold green] → Approve and proceed\n"
            "  [bold yellow]m[/bold yellow] → Modify the plan\n"
            "  [bold red]r[/bold red] → Reject and recreate\n"
        )
        await ui.panel("🎯 Plan Review", content, border_style="cyan")

        kb = create_key_bindings(state_manager)
        while True:
            try:
                response = await ui.input(
                    "plan_approval", "  → Your choice [a/m/r]: ", kb, state_manager
                )
                response = response.strip().lower()
                state_manager.session.approval_abort_pressed = False
                state_manager.session.approval_last_abort_time = 0.0
                break
            except UserAbortError:
                current_time = time.time()
                abort_pressed = getattr(state_manager.session, "approval_abort_pressed", False)
                last_abort = getattr(state_manager.session, "approval_last_abort_time", 0.0)

                if current_time - last_abort > 3.0:
                    abort_pressed = False

                if abort_pressed:
                    await ui.info("🔄 Returning to Plan Mode")
                    state_manager.enter_plan_mode()
                    state_manager.session.approval_abort_pressed = False
                    return

                state_manager.session.approval_abort_pressed = True
                state_manager.session.approval_last_abort_time = current_time
                await ui.warning("Hit ESC or Ctrl+C again to return to Plan Mode")

        actions = {
            "a": (
                "✅ Plan approved - proceeding with implementation",
                lambda: state_manager.approve_plan(),
            ),
            "m": (
                "📝 Returning to Plan Mode for modifications",
                lambda: state_manager.enter_plan_mode(),
            ),
            "r": (
                "🔄 Plan rejected - returning to Plan Mode",
                lambda: state_manager.enter_plan_mode(),
            ),
        }

        if response in actions or response in ["approve", "modify", "reject"]:
            key = response[0] if len(response) > 1 else response
            msg, action = actions.get(key, (None, None))
            if msg:
                await ui.info(msg) if key == "a" else await ui.warning(msg)
                action()
                if key == "a" and original_request:
                    await ui.info("🚀 Executing implementation...")
                    await process_request(
                        _transform_to_implementation_request(original_request),
                        state_manager,
                        output=True,
                    )
        else:
            await ui.warning("⚠️ Invalid choice - please enter a, m, or r")

        state_manager.session.plan_phase = None

    except Exception as e:
        logger.error(f"Error in plan approval: {e}")
        state_manager.session.plan_phase = None


_command_registry = CommandRegistry()
_command_registry.register_all_default_commands()


async def _handle_command(command: str, state_manager: StateManager) -> CommandResult:
    """Handles a command string using the command registry."""
    context = CommandContext(state_manager=state_manager, process_request=process_request)
    try:
        _command_registry.set_process_request_callback(process_request)
        return await _command_registry.execute(command, context)
    except ValidationError as e:
        await ui.error(str(e))
        return None


async def process_request(text: str, state_manager: StateManager, output: bool = True):
    """Process input using the agent, handling cancellation safely."""
    import uuid

    from tunacode.types import PlanPhase
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
            streaming_panel = ui.StreamingAgentPanel()
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
        else:
            res = await agent.process_request(
                text,
                state_manager.session.current_model,
                state_manager,
                tool_callback=tool_callback_with_state,
                usage_tracker=usage_tracker,
            )

        # Handle plan approval or detection
        if (
            hasattr(state_manager.session, "plan_phase")
            and state_manager.session.plan_phase == PlanPhase.PLAN_READY
        ):
            await _handle_plan_approval(state_manager, text)
        elif state_manager.is_plan_mode() and not getattr(
            state_manager.session, "_continuing_from_plan", False
        ):
            await _detect_and_handle_text_plan(state_manager, res, text)

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
        await ui.muted(MSG_OPERATION_ABORTED)
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
                process_request(line, state_manager)
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
