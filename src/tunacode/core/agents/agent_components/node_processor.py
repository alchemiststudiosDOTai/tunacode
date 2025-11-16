"""Node processing functionality for agent responses."""

import json
from typing import Any, Awaitable, Callable, Optional, Tuple

from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.exceptions import UserAbortError
from tunacode.types import AgentState, UsageTrackerProtocol
from tunacode.ui.tool_descriptions import get_batch_description, get_tool_description

from .response_state import ResponseState
from .task_completion import check_task_completion
from .tool_buffer import ToolBuffer
from .truncation_checker import check_for_truncation

logger = get_logger(__name__)

# Import streaming types with fallback for older versions
try:
    from pydantic_ai.messages import PartDeltaEvent, TextPartDelta

    STREAMING_AVAILABLE = True
except ImportError:
    # Fallback for older pydantic-ai versions
    PartDeltaEvent = None
    TextPartDelta = None
    STREAMING_AVAILABLE = False


async def _process_node(
    node,
    tool_callback: Optional[Callable],
    state_manager: StateManager,
    tool_buffer: Optional[ToolBuffer] = None,
    streaming_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    usage_tracker: Optional[UsageTrackerProtocol] = None,
    response_state: Optional[ResponseState] = None,
) -> Tuple[bool, Optional[str]]:
    """Process a single node from the agent response.

    Returns:
        tuple: (is_empty: bool, reason: Optional[str]) - True if empty/problematic
               response detected, with reason being one of: "empty", "truncated",
               "intention_without_action"
    """
    from tunacode.ui import console as ui

    # Use the original callback directly - parallel execution will be handled differently
    buffering_callback = tool_callback
    empty_response_detected = False
    has_non_empty_content = False
    appears_truncated = False
    has_intention = False
    has_tool_calls = False

    # Transition to ASSISTANT at the start of node processing
    if response_state and response_state.can_transition_to(AgentState.ASSISTANT):
        response_state.transition_to(AgentState.ASSISTANT)
        if state_manager.session.show_thoughts:
            await ui.muted("STATE → ASSISTANT (reasoning)")

    if hasattr(node, "request"):
        state_manager.session.messages.append(node.request)

    if hasattr(node, "thought") and node.thought:
        state_manager.session.messages.append({"thought": node.thought})
        # Display thought immediately if show_thoughts is enabled
        if state_manager.session.show_thoughts:
            await ui.muted(f"THOUGHT: {node.thought}")

    if hasattr(node, "model_response"):
        state_manager.session.messages.append(node.model_response)

        if usage_tracker:
            await usage_tracker.track_and_display(node.model_response)

        # Check for task completion marker in response content
        if response_state:
            has_non_empty_content = False
            appears_truncated = False
            all_content_parts = []

            # First, check if there are any tool calls in this response
            has_queued_tools = any(
                hasattr(part, "part_kind") and part.part_kind == "tool-call"
                for part in node.model_response.parts
            )

            for part in node.model_response.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    # Check if we have any non-empty content
                    if part.content.strip():
                        has_non_empty_content = True
                        all_content_parts.append(part.content)

                    is_complete, cleaned_content = check_task_completion(part.content)
                    if is_complete:
                        # Validate completion - check for premature completion
                        if has_queued_tools:
                            # Agent is trying to complete with pending tools!
                            if state_manager.session.show_thoughts:
                                await ui.warning(
                                    "⚠️ PREMATURE COMPLETION DETECTED - "
                                    "Agent queued tools but marked complete"
                                )
                                await ui.muted("   Overriding completion to allow tool execution")
                            # Don't mark as complete - let the tools run first
                            # Update the content to remove the marker but don't set task_completed
                            part.content = cleaned_content
                            # Log this as an issue
                            pending_tools_count = sum(
                                1
                                for p in node.model_response.parts
                                if getattr(p, "part_kind", "") == "tool-call"
                            )
                            logger.warning(
                                f"Agent attempted premature completion with {pending_tools_count} "
                                f"pending tools"
                            )
                        else:
                            # Check if content suggests pending actions
                            combined_text = " ".join(all_content_parts).lower()
                            pending_phrases = [
                                "let me",
                                "i'll check",
                                "i will",
                                "going to",
                                "about to",
                                "need to check",
                                "let's check",
                                "i should",
                                "need to find",
                                "let me see",
                                "i'll look",
                                "let me search",
                                "let me find",
                            ]
                            has_pending_intention = any(
                                phrase in combined_text for phrase in pending_phrases
                            )

                            # Also check for action verbs at end of content
                            # suggesting incomplete action
                            action_endings = [
                                "checking",
                                "searching",
                                "looking",
                                "finding",
                                "reading",
                                "analyzing",
                            ]
                            ends_with_action = any(
                                combined_text.rstrip().endswith(ending) for ending in action_endings
                            )

                            if (
                                has_pending_intention or ends_with_action
                            ) and state_manager.session.iteration_count <= 1:
                                # Too early to complete with pending intentions
                                if state_manager.session.show_thoughts:
                                    await ui.warning(
                                        "⚠️ SUSPICIOUS COMPLETION - "
                                        "Stated intentions but completing early"
                                    )
                                    found_phrases = [
                                        p for p in pending_phrases if p in combined_text
                                    ]
                                    iteration_msg = (
                                        f"   Iteration {state_manager.session.iteration_count} "
                                        f"with pending: {found_phrases}"
                                    )
                                    await ui.muted(iteration_msg)
                                    if ends_with_action:
                                        action_verb = (
                                            combined_text.split()[-1]
                                            if combined_text.split()
                                            else ""
                                        )
                                        await ui.muted(
                                            f"   Content ends with action verb: '{action_verb}'"
                                        )
                                # Still allow it but log warning
                                logger.warning(
                                    f"Task completion with pending intentions detected: "
                                    f"{found_phrases}"
                                )

                            # Normal completion - transition to RESPONSE state and mark completion
                            response_state.transition_to(AgentState.RESPONSE)
                            if state_manager.session.show_thoughts:
                                await ui.muted("STATE → RESPONSE (completion detected)")
                            response_state.set_completion_detected(True)
                            response_state.has_user_response = True
                            # Update the part content to remove the marker
                            part.content = cleaned_content
                            if state_manager.session.show_thoughts:
                                await ui.muted("✅ TASK COMPLETION DETECTED")
                        break

            # Check for truncation patterns
            if all_content_parts:
                combined_content = " ".join(all_content_parts).strip()
                appears_truncated = check_for_truncation(combined_content)

            # If we only got empty content and no tool calls, we should NOT consider this
            # a valid response
            # This prevents the agent from stopping when it gets empty responses
            if not has_non_empty_content and not any(
                hasattr(part, "part_kind") and part.part_kind == "tool-call"
                for part in node.model_response.parts
            ):
                # Empty response with no tools - keep going
                empty_response_detected = True
                if state_manager.session.show_thoughts:
                    await ui.muted("⚠️ EMPTY RESPONSE - CONTINUING")

            # Check if response appears truncated
            elif appears_truncated and not any(
                hasattr(part, "part_kind") and part.part_kind == "tool-call"
                for part in node.model_response.parts
            ):
                # Truncated response detected
                empty_response_detected = True
                if state_manager.session.show_thoughts:
                    await ui.muted("⚠️ TRUNCATED RESPONSE DETECTED - CONTINUING")
                    await ui.muted(f"   Last content: ...{combined_content[-100:]}")

        # Stream content to callback if provided
        # Use this as fallback when true token streaming is not available
        if streaming_callback and not STREAMING_AVAILABLE:
            # Basic diagnostics for first-chunk behavior in fallback streaming
            first_emitted = False
            raw_accum = ""
            for part in node.model_response.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    content = part.content
                    # Only check for empty content and JSON thoughts, don't strip whitespace
                    # as it may remove important leading spaces/characters
                    if content and not content.lstrip().startswith('{"thought"'):
                        if not first_emitted:
                            try:
                                import time as _t

                                ts_ns = _t.perf_counter_ns()
                            except Exception:
                                ts_ns = 0
                            # We cannot guarantee session access here; log via logger only
                            logger.debug(
                                "[src-fallback] first_chunk ts_ns=%s chunk_repr=%r len=%d",
                                ts_ns,
                                content[:5],
                                len(content),
                            )
                            first_emitted = True
                        raw_accum += content
                        # Stream the original content without stripping
                        if streaming_callback:
                            await streaming_callback(content)

        # Enhanced display when thoughts are enabled
        if state_manager.session.show_thoughts:
            await _display_raw_api_response(node, ui)

        # Process tool calls
        await _process_tool_calls(
            node, buffering_callback, state_manager, tool_buffer, response_state
        )

    # If there were no tools and we processed a model response, transition to RESPONSE
    if response_state and response_state.can_transition_to(AgentState.RESPONSE):
        # Only transition if not already completed (set by completion marker path)
        if not response_state.is_completed():
            response_state.transition_to(AgentState.RESPONSE)
            if state_manager.session.show_thoughts:
                await ui.muted("STATE → RESPONSE (handled output)")

    # Determine empty response reason
    if empty_response_detected:
        if appears_truncated:
            return True, "truncated"
        else:
            return True, "empty"

    # Check for intention without action
    if has_intention and not has_tool_calls and not has_non_empty_content:
        return True, "intention_without_action"

    return False, None


async def _display_raw_api_response(node: Any, ui: Any) -> None:
    """Display raw API response data when thoughts are enabled."""

    # Display the raw model response parts
    await ui.muted("\n" + "=" * 60)
    await ui.muted(" RAW API RESPONSE DATA:")
    await ui.muted("=" * 60)

    for idx, part in enumerate(node.model_response.parts):
        part_data = {"part_index": idx, "part_kind": getattr(part, "part_kind", "unknown")}

        # Add part-specific data
        if hasattr(part, "content"):
            part_data["content"] = (
                part.content[:200] + "..." if len(str(part.content)) > 200 else part.content
            )
        if hasattr(part, "tool_name"):
            part_data["tool_name"] = part.tool_name
        if hasattr(part, "args"):
            part_data["args"] = part.args
        if hasattr(part, "tool_call_id"):
            part_data["tool_call_id"] = part.tool_call_id

        await ui.muted(json.dumps(part_data, indent=2))

    await ui.muted("=" * 60)

    # Count how many tool calls are in this response
    tool_count = sum(
        1
        for part in node.model_response.parts
        if hasattr(part, "part_kind") and part.part_kind == "tool-call"
    )
    if tool_count > 0:
        await ui.muted(f"\n MODEL RESPONSE: Contains {tool_count} tool call(s)")

    # Display LLM response content
    for part in node.model_response.parts:
        if hasattr(part, "content") and isinstance(part.content, str):
            content = part.content.strip()

            # Skip empty content
            if not content:
                continue

            # Skip thought content (JSON)
            if content.startswith('{"thought"'):
                continue

            # Skip tool result content
            if hasattr(part, "part_kind") and part.part_kind == "tool-return":
                continue

            # Display text part
            await ui.muted(f" TEXT PART: {content[:200]}{'...' if len(content) > 200 else ''}")


async def _process_tool_calls(
    node: Any,
    tool_callback: Optional[Callable],
    state_manager: StateManager,
    tool_buffer: Optional[ToolBuffer],
    response_state: Optional[ResponseState],
) -> None:
    """Process tool calls from the node."""
    from tunacode.constants import READ_ONLY_TOOLS
    from tunacode.ui import console as ui

    # Track if we're processing tool calls
    is_processing_tools = False

    # Process tool calls
    for part in node.model_response.parts:
        if hasattr(part, "part_kind") and part.part_kind == "tool-call":
            is_processing_tools = True
            # Transition to TOOL_EXECUTION on first tool call
            if response_state and response_state.can_transition_to(AgentState.TOOL_EXECUTION):
                response_state.transition_to(AgentState.TOOL_EXECUTION)
                if state_manager.session.show_thoughts:
                    await ui.muted("STATE → TOOL_EXECUTION (executing tools)")
            if tool_callback:
                # Check if this is a read-only tool that can be batched
                if tool_buffer is not None and part.tool_name in READ_ONLY_TOOLS:
                    # Add to buffer instead of executing immediately
                    tool_buffer.add(part, node)

                    # Update spinner to show we're collecting tools
                    buffered_count = len(tool_buffer.read_only_tasks)
                    spinner_msg = (
                        f"[bold #00d7ff]Collecting tools ({buffered_count}) "
                        f"buffered...[/bold #00d7ff]"
                    )
                    await ui.update_spinner_message(spinner_msg, state_manager)

                    if state_manager.session.show_thoughts:
                        await ui.muted(
                            f"⏸️ BUFFERED: {part.tool_name} (will execute in parallel batch)"
                        )
                else:
                    # Write/execute tool - process any buffered reads first
                    if tool_buffer is not None and tool_buffer.has_tasks():
                        import time

                        from .tool_executor import execute_tools_parallel

                        buffered_tasks = tool_buffer.flush()
                        batch_id = getattr(state_manager.session, "batch_counter", 0) + 1
                        state_manager.session.batch_counter = batch_id

                        start_time = time.time()

                        # Update spinner message for batch execution
                        tool_names = [part.tool_name for part, _ in buffered_tasks]
                        batch_msg = get_batch_description(len(buffered_tasks), tool_names)
                        await ui.update_spinner_message(
                            f"[bold #00d7ff]{batch_msg}...[/bold #00d7ff]", state_manager
                        )

                        # Enhanced visual feedback for parallel execution
                        await ui.muted("\n" + "=" * 60)
                        batch_title = (
                            f"🚀 PARALLEL BATCH #{batch_id}: "
                            f"Executing {len(buffered_tasks)} read-only tools concurrently"
                        )
                        await ui.muted(batch_title)
                        await ui.muted("=" * 60)

                        # Display details of what's being executed
                        for idx, (buffered_part, _) in enumerate(buffered_tasks, 1):
                            tool_desc = f"  [{idx}] {buffered_part.tool_name}"
                            if hasattr(buffered_part, "args") and isinstance(
                                buffered_part.args, dict
                            ):
                                if (
                                    buffered_part.tool_name == "read_file"
                                    and "file_path" in buffered_part.args
                                ):
                                    tool_desc += f" → {buffered_part.args['file_path']}"
                                elif (
                                    buffered_part.tool_name == "grep"
                                    and "pattern" in buffered_part.args
                                ):
                                    tool_desc += f" → pattern: '{buffered_part.args['pattern']}'"
                                    if "include_files" in buffered_part.args:
                                        tool_desc += (
                                            f", files: '{buffered_part.args['include_files']}'"
                                        )
                                elif (
                                    buffered_part.tool_name == "list_dir"
                                    and "directory" in buffered_part.args
                                ):
                                    tool_desc += f" → {buffered_part.args['directory']}"
                                elif (
                                    buffered_part.tool_name == "glob"
                                    and "pattern" in buffered_part.args
                                ):
                                    tool_desc += f" → pattern: '{buffered_part.args['pattern']}'"
                            await ui.muted(tool_desc)
                        await ui.muted("=" * 60)

                        await execute_tools_parallel(buffered_tasks, tool_callback)

                        elapsed_time = (time.time() - start_time) * 1000
                        sequential_estimate = (
                            len(buffered_tasks) * 100
                        )  # Assume 100ms per tool average
                        speedup = sequential_estimate / elapsed_time if elapsed_time > 0 else 1.0

                        await ui.muted(
                            f"✅ Parallel batch completed in {elapsed_time:.0f}ms "
                            f"(~{speedup:.1f}x faster than sequential)\n"
                        )

                        # Reset spinner message back to thinking
                        from tunacode.constants import UI_THINKING_MESSAGE

                        await ui.update_spinner_message(UI_THINKING_MESSAGE, state_manager)

                    # Now execute the write/execute tool
                    if state_manager.session.show_thoughts:
                        await ui.warning(f"⚠️ SEQUENTIAL: {part.tool_name} (write/execute tool)")

                    # Update spinner for sequential tool
                    tool_args = getattr(part, "args", {}) if hasattr(part, "args") else {}
                    # Parse args if they're a JSON string
                    if isinstance(tool_args, str):
                        import json

                        try:
                            tool_args = json.loads(tool_args)
                        except (json.JSONDecodeError, TypeError):
                            tool_args = {}
                    tool_desc = get_tool_description(part.tool_name, tool_args)
                    await ui.update_spinner_message(
                        f"[bold #00d7ff]{tool_desc}...[/bold #00d7ff]", state_manager
                    )

                    # Execute the tool with robust error handling
                    # so one failure doesn't crash the run
                    try:
                        await tool_callback(part, node)
                    except UserAbortError:
                        raise
                    except Exception as tool_err:
                        logger.error(
                            "Tool callback failed: tool=%s iter=%s err=%s",
                            getattr(part, "tool_name", "<unknown>"),
                            getattr(state_manager.session, "current_iteration", "?"),
                            tool_err,
                            exc_info=True,
                        )
                        # Surface to UI when thoughts are enabled, then continue gracefully
                        if getattr(state_manager.session, "show_thoughts", False):
                            await ui.warning(
                                f"❌ Tool failed: {getattr(part, 'tool_name', '<unknown>')} — "
                                f"continuing"
                            )
                    finally:
                        # Tool execution completed - resource cleanup handled by BaseTool.execute()
                        # Each tool's cleanup() method is called automatically in its execute()
                        # finally block. This ensures resources (file handles, connections,
                        # processes) are freed regardless of success or failure.
                        tool_name = getattr(part, "tool_name", "<unknown>")
                        logger.debug(
                            "Tool execution completed (success or failure): tool=%s",
                            tool_name,
                        )

    # Track tool calls in session
    if is_processing_tools:
        # Extract tool information for tracking
        for part in node.model_response.parts:
            if hasattr(part, "part_kind") and part.part_kind == "tool-call":
                tool_info = {
                    "tool": part.tool_name,
                    "args": getattr(part, "args", {}),
                    "timestamp": getattr(part, "timestamp", None),
                }
                state_manager.session.tool_calls.append(tool_info)

    # After tools are processed, transition back to RESPONSE
    if (
        is_processing_tools
        and response_state
        and response_state.can_transition_to(AgentState.RESPONSE)
    ):
        response_state.transition_to(AgentState.RESPONSE)
        if state_manager.session.show_thoughts:
            await ui.muted("STATE → RESPONSE (tools finished)")

    # Update has_user_response based on presence of actual response content
    if (
        response_state
        and hasattr(node, "result")
        and node.result
        and hasattr(node.result, "output")
    ):
        if node.result.output:
            response_state.has_user_response = True
