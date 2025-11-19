"""Node processing functionality for agent responses."""

import json
from typing import Any, Awaitable, Callable, Optional, Tuple

from tunacode.constants import UI_COLORS
from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.exceptions import UserAbortError
from tunacode.types import AgentState, UsageTrackerProtocol
from tunacode.ui.tool_descriptions import get_batch_description, get_tool_description
from tunacode.utils.file_utils import DotDict

from .response_state import ResponseState
from .task_completion import check_task_completion
from .tool_buffer import ToolBuffer
from .truncation_checker import check_for_truncation

logger = get_logger(__name__)
colors = DotDict(UI_COLORS)


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
    """
    Process tool calls from the node using smart batching strategy.

    Smart batching optimization:
    - Collect all read-only tools into a single batch (regardless of write tools in between)
    - Execute all read-only tools in one parallel batch
    - Execute write/execute tools sequentially in their original order

    This maximizes parallel execution efficiency by avoiding premature buffer flushes.
    """
    from tunacode.constants import READ_ONLY_TOOLS
    from tunacode.ui import console as ui

    # Track if we're processing tool calls
    is_processing_tools = False

    # Phase 1: Collect and categorize all tools
    read_only_tasks = []
    research_agent_tasks = []
    write_execute_tasks = []

    for part in node.model_response.parts:
        if hasattr(part, "part_kind") and part.part_kind == "tool-call":
            is_processing_tools = True
            # Transition to TOOL_EXECUTION on first tool call
            if response_state and response_state.can_transition_to(AgentState.TOOL_EXECUTION):
                response_state.transition_to(AgentState.TOOL_EXECUTION)
                if state_manager.session.show_thoughts:
                    await ui.muted("STATE → TOOL_EXECUTION (executing tools)")

            if tool_callback:
                # Categorize: research agent vs read-only vs write/execute
                if part.tool_name == "research_codebase":
                    research_agent_tasks.append((part, node))
                    if state_manager.session.show_thoughts:
                        await ui.muted(
                            f"COLLECTED: {part.tool_name} (research agent - special display)"
                        )
                elif part.tool_name in READ_ONLY_TOOLS:
                    read_only_tasks.append((part, node))
                    if state_manager.session.show_thoughts:
                        await ui.muted(
                            f"COLLECTED: {part.tool_name} (will execute in parallel batch)"
                        )
                else:
                    write_execute_tasks.append((part, node))
                    if state_manager.session.show_thoughts:
                        await ui.muted(f"COLLECTED: {part.tool_name} (will execute sequentially)")

    # Phase 2: Execute research agent with special UI display
    if research_agent_tasks and tool_callback:
        from tunacode.ui import console as ui

        from .tool_executor import execute_tools_parallel

        # Display research agent panel with query details
        for part, _ in research_agent_tasks:
            tool_args = getattr(part, "args", {}) if hasattr(part, "args") else {}
            # Parse args if they're a JSON string
            if isinstance(tool_args, str):
                import json

                try:
                    tool_args = json.loads(tool_args)
                except (json.JSONDecodeError, TypeError):
                    tool_args = {}

            # Build research agent panel content
            query = tool_args.get("query", "Unknown query")
            directories = tool_args.get("directories", ["."])
            max_files = tool_args.get("max_files", 3)

            # Format panel text (batch-style format)
            dirs_str = ", ".join(directories) if isinstance(directories, list) else str(directories)
            panel_text = f"""**RESEARCH AGENT**: {query}

**Directories:** {dirs_str} | **Max files:** {max_files}

**Tools available:** grep, read_file, list_dir, glob (read-only)"""

            # Display purple research agent panel
            await ui.research_agent(panel_text)

            # Update spinner to show research in progress
            query_preview = query[:60] + "..." if len(query) > 60 else query
            await ui.update_spinner_message(
                f"[bold {colors.accent}]Researching: {query_preview}[/bold {colors.accent}]",
                state_manager,
            )

        # Execute the research agent tool
        results = await execute_tools_parallel(research_agent_tasks, tool_callback)

        # Show completion summary if results available
        if results and len(results) > 0:
            result = results[0]  # Research agent typically returns single result
            if isinstance(result, dict) and not result.get("error"):
                files = result.get("relevant_files", [])
                findings_count = len(result.get("key_findings", []))
                if files:
                    summary = (
                        f"[bold {colors.accent}]Research complete: analyzed {len(files)} file(s), "
                        f"{findings_count} finding(s)[/bold {colors.accent}]"
                    )
                    await ui.update_spinner_message(summary, state_manager)
                    # Brief pause to show summary before resetting
                    import asyncio

                    await asyncio.sleep(0.5)

        # Reset spinner message back to thinking
        from tunacode.constants import UI_THINKING_MESSAGE

        await ui.update_spinner_message(UI_THINKING_MESSAGE, state_manager)

    # Phase 3: Execute read-only tools in ONE parallel batch
    if read_only_tasks and tool_callback:
        from .tool_executor import execute_tools_parallel

        batch_id = getattr(state_manager.session, "batch_counter", 0) + 1
        state_manager.session.batch_counter = batch_id

        # Update spinner to show batch collection
        collection_msg = (
            f"[bold {colors.primary}]Collected {len(read_only_tasks)} "
            f"read-only tools...[/bold {colors.primary}]"
        )
        await ui.update_spinner_message(collection_msg, state_manager)

        # Update spinner message for batch execution
        tool_names = [part.tool_name for part, _ in read_only_tasks]
        batch_msg = get_batch_description(len(read_only_tasks), tool_names)
        await ui.update_spinner_message(
            f"[bold {colors.primary}]{batch_msg}...[/bold {colors.primary}]", state_manager
        )

        # Build batch content as markdown for Rich panel
        batch_content = (
            f"**PARALLEL BATCH #{batch_id}**: "
            f"Executing {len(read_only_tasks)} read-only tools concurrently\n\n"
        )

        # Display details of what's being executed
        from .agent_helpers import get_readable_tool_description

        for idx, (part, _) in enumerate(read_only_tasks, 1):
            tool_args = getattr(part, "args", {}) if hasattr(part, "args") else {}
            # Parse args if they're a JSON string
            if isinstance(tool_args, str):
                import json

                try:
                    tool_args = json.loads(tool_args)
                except (json.JSONDecodeError, TypeError):
                    tool_args = {}
            readable_desc = get_readable_tool_description(part.tool_name, tool_args)
            tool_desc = f"  **[{idx}]** {readable_desc}"
            batch_content += f"{tool_desc}\n"

        await execute_tools_parallel(read_only_tasks, tool_callback)

        # Display batch execution in green Rich panel
        await ui.batch(batch_content)

        # Reset spinner message back to thinking
        from tunacode.constants import UI_THINKING_MESSAGE

        await ui.update_spinner_message(UI_THINKING_MESSAGE, state_manager)

    # Phase 4: Execute write/execute tools sequentially
    for part, node in write_execute_tasks:
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
            f"[bold {colors.primary}]{tool_desc}...[/bold {colors.primary}]", state_manager
        )

        # Execute the tool with robust error handling
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
                    f"❌ Tool failed: {getattr(part, 'tool_name', '<unknown>')} — continuing"
                )
        finally:
            # Tool execution completed - resource cleanup handled by BaseTool.execute()
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
