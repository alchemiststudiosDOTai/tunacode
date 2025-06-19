"""Module: tunacode.core.agents.main

Main agent functionality and coordination for the TunaCode CLI.
Handles agent creation, configuration, and request processing.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tunacode.context import get_code_style

from tunacode.core.state import StateManager
from tunacode.services.mcp import get_mcp_servers
from tunacode.tools.bash import bash
from tunacode.tools.grep import grep
from tunacode.tools.list_dir import list_dir
from tunacode.tools.read_file import read_file
from tunacode.tools.run_command import run_command
from tunacode.tools.update_file import update_file
from tunacode.tools.write_file import write_file
from tunacode.types import (AgentRun, ErrorMessage, FallbackResponse, ModelName, PydanticAgent,
                            ResponseState, SimpleResult, ToolCallback, ToolCallId, ToolName)


# Lazy import for Agent and Tool
def get_agent_tool():
    import importlib

    pydantic_ai = importlib.import_module("pydantic_ai")
    return pydantic_ai.Agent, pydantic_ai.Tool


def get_model_messages():
    import importlib

    messages = importlib.import_module("pydantic_ai.messages")
    return messages.ModelRequest, messages.ToolReturnPart


async def _process_node(node, tool_callback: Optional[ToolCallback], state_manager: StateManager):
    from tunacode.ui import console as ui
    from tunacode.utils.token_counter import estimate_tokens

    if hasattr(node, "request"):
        state_manager.session.messages.append(node.request)

    if hasattr(node, "thought") and node.thought:
        state_manager.session.messages.append({"thought": node.thought})
        # Display thought immediately if show_thoughts is enabled
        if state_manager.session.show_thoughts:
            await ui.muted(f"THOUGHT: {node.thought}")

    if hasattr(node, "model_response"):
        state_manager.session.messages.append(node.model_response)

        # Enhanced display when thoughts are enabled
        if state_manager.session.show_thoughts:
            import json
            import re

            # Display LLM response content
            for part in node.model_response.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    content = part.content.strip()

                    # Skip empty content
                    if not content:
                        continue

                    # Estimate tokens in this response
                    token_count = estimate_tokens(content)

                    # Display non-JSON content as LLM response
                    if not content.startswith('{"thought"'):
                        # Truncate very long responses for display
                        display_content = content[:500] + "..." if len(content) > 500 else content
                        await ui.muted(f"\nRESPONSE: {display_content}")
                        await ui.muted(f"TOKENS: ~{token_count}")

                    # Pattern 1: Inline JSON thoughts {"thought": "..."}
                    thought_pattern = r'\{"thought":\s*"([^"]+)"\}'
                    matches = re.findall(thought_pattern, content)
                    for thought in matches:
                        await ui.muted(f"REASONING: {thought}")

                    # Pattern 2: Standalone thought JSON objects
                    try:
                        if content.startswith('{"thought"'):
                            thought_obj = json.loads(content)
                            if "thought" in thought_obj:
                                await ui.muted(f"REASONING: {thought_obj['thought']}")
                    except (json.JSONDecodeError, KeyError):
                        pass

                    # Pattern 3: Multi-line thoughts with context
                    multiline_pattern = r'\{"thought":\s*"([^"]+(?:\\.[^"]*)*?)"\}'
                    multiline_matches = re.findall(multiline_pattern, content, re.DOTALL)
                    for thought in multiline_matches:
                        if thought not in [m for m in matches]:  # Avoid duplicates
                            # Clean up escaped characters
                            cleaned_thought = thought.replace('\\"', '"').replace("\\n", " ")
                            await ui.muted(f"REASONING: {cleaned_thought}")

        # Check for tool calls and fallback to JSON parsing if needed
        has_tool_calls = False
        for part in node.model_response.parts:
            if part.part_kind == "tool-call" and tool_callback:
                has_tool_calls = True

                # Display tool call details when thoughts are enabled
                if state_manager.session.show_thoughts:
                    await ui.muted(f"\nTOOL: {part.tool_name}")
                    if hasattr(part, "args"):
                        # Check if args is a dictionary before accessing keys
                        if isinstance(part.args, dict):
                            # Simplify display based on tool type
                            if part.tool_name == "read_file" and "file_path" in part.args:
                                file_path = part.args["file_path"]
                                filename = Path(file_path).name
                                await ui.muted(f"Reading: {filename}")
                            elif part.tool_name == "write_file" and "file_path" in part.args:
                                file_path = part.args["file_path"]
                                filename = Path(file_path).name
                                await ui.muted(f"Writing: {filename}")
                            elif part.tool_name == "update_file" and "file_path" in part.args:
                                file_path = part.args["file_path"]
                                filename = Path(file_path).name
                                await ui.muted(f"Updating: {filename}")
                            elif (
                                part.tool_name in ["run_command", "bash"] and "command" in part.args
                            ):
                                command = part.args["command"]
                                # Truncate long commands
                                display_cmd = (
                                    command if len(command) <= 60 else command[:57] + "..."
                                )
                                await ui.muted(f"Command: {display_cmd}")
                            elif part.tool_name == "list_dir" and "directory" in part.args:
                                directory = part.args["directory"]
                                await ui.muted(f"Listing: {directory}")
                            else:
                                # For other tools, show full args but more compact
                                args_str = json.dumps(part.args, indent=2)
                                await ui.muted(f"ARGS: {args_str}")
                        else:
                            # If args is not a dict (e.g., a string), just display it as is
                            await ui.muted(f"ARGS: {part.args}")

                # Track this tool call (moved outside thoughts block)
                state_manager.session.tool_calls.append(
                    {
                        "tool": part.tool_name,
                        "args": part.args if hasattr(part, "args") else {},
                        "iteration": state_manager.session.current_iteration,
                    }
                )

                # Track files if this is read_file (moved outside thoughts block)
                if (
                    part.tool_name == "read_file"
                    and hasattr(part, "args")
                    and isinstance(part.args, dict)
                    and "file_path" in part.args
                ):
                    state_manager.session.files_in_context.add(part.args["file_path"])
                    # Show files in context when thoughts are enabled
                    if state_manager.session.show_thoughts:
                        await ui.muted(
                            f"\nFILES IN CONTEXT: {list(state_manager.session.files_in_context)}"
                        )

                await tool_callback(part, node)

            elif part.part_kind == "tool-return":
                obs_msg = f"OBSERVATION[{part.tool_name}]: {part.content[:2_000]}"
                state_manager.session.messages.append(obs_msg)

                # Display tool return when thoughts are enabled
                if state_manager.session.show_thoughts:
                    # Truncate for display
                    display_content = (
                        part.content[:200] + "..." if len(part.content) > 200 else part.content
                    )
                    await ui.muted(f"TOOL RESULT: {display_content}")

        # If no structured tool calls found, try parsing JSON from text content
        if not has_tool_calls and tool_callback:
            for part in node.model_response.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    await extract_and_execute_tool_calls(part.content, tool_callback, state_manager)


def get_or_create_agent(model: ModelName, state_manager: StateManager) -> PydanticAgent:
    if model not in state_manager.session.agents:
        max_retries = state_manager.session.user_config.get("settings", {}).get("max_retries", 3)

        # Lazy import Agent and Tool
        Agent, Tool = get_agent_tool()

        # Load system prompt
        prompt_path = Path(__file__).parent.parent.parent / "prompts" / "system.md"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read().strip()
        except FileNotFoundError:
            # Fallback to system.txt if system.md not found
            prompt_path = Path(__file__).parent.parent.parent / "prompts" / "system.txt"
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    system_prompt = f.read().strip()
            except FileNotFoundError:
                # Use a default system prompt if neither file exists
                system_prompt = "You are a helpful AI assistant for software development tasks."

        # Append project context from TUNACODE.md files
        try:
            code_style = get_code_style.sync()  # type: ignore[attr-defined]
            if code_style:
                system_prompt += f"\n\n# Project Context (from TUNACODE.md)\n{code_style}"
        except Exception:
            pass

        state_manager.session.agents[model] = Agent(
            model=model,
            system_prompt=system_prompt,
            tools=[
                Tool(bash, max_retries=max_retries),
                Tool(grep, max_retries=max_retries),
                Tool(list_dir, max_retries=max_retries),
                Tool(read_file, max_retries=max_retries),
                Tool(run_command, max_retries=max_retries),
                Tool(update_file, max_retries=max_retries),
                Tool(write_file, max_retries=max_retries),
            ],
            mcp_servers=get_mcp_servers(state_manager),
        )
    return state_manager.session.agents[model]


def patch_tool_messages(
    error_message: ErrorMessage = "Tool operation failed",
    state_manager: StateManager = None,
):
    """
    Find any tool calls without responses and add synthetic error responses for them.
    Takes an error message to use in the synthesized tool response.

    Ignores tools that have corresponding retry prompts as the model is already
    addressing them.
    """
    if state_manager is None:
        raise ValueError("state_manager is required for patch_tool_messages")

    messages = state_manager.session.messages

    if not messages:
        return

    # Map tool calls to their tool returns
    tool_calls: dict[ToolCallId, ToolName] = {}  # tool_call_id -> tool_name
    tool_returns: set[ToolCallId] = set()  # set of tool_call_ids with returns
    retry_prompts: set[ToolCallId] = set()  # set of tool_call_ids with retry prompts

    for message in messages:
        if hasattr(message, "parts"):
            for part in message.parts:
                if (
                    hasattr(part, "part_kind")
                    and hasattr(part, "tool_call_id")
                    and part.tool_call_id
                ):
                    if part.part_kind == "tool-call":
                        tool_calls[part.tool_call_id] = part.tool_name
                    elif part.part_kind == "tool-return":
                        tool_returns.add(part.tool_call_id)
                    elif part.part_kind == "retry-prompt":
                        retry_prompts.add(part.tool_call_id)

    # Identify orphaned tools (those without responses and not being retried)
    for tool_call_id, tool_name in list(tool_calls.items()):
        if tool_call_id not in tool_returns and tool_call_id not in retry_prompts:
            # Import ModelRequest and ToolReturnPart lazily
            ModelRequest, ToolReturnPart = get_model_messages()
            messages.append(
                ModelRequest(
                    parts=[
                        ToolReturnPart(
                            tool_name=tool_name,
                            content=error_message,
                            tool_call_id=tool_call_id,
                            timestamp=datetime.now(timezone.utc),
                            part_kind="tool-return",
                        )
                    ],
                    kind="request",
                )
            )


async def parse_json_tool_calls(
    text: str, tool_callback: Optional[ToolCallback], state_manager: StateManager
):
    """
    Parse JSON tool calls from text when structured tool calling fails.
    Fallback for when API providers don't support proper tool calling.
    """
    if not tool_callback:
        return

    # Pattern for JSON tool calls: {"tool": "tool_name", "args": {...}}
    # Find potential JSON objects and parse them
    potential_jsons = []
    brace_count = 0
    start_pos = -1

    for i, char in enumerate(text):
        if char == "{":
            if brace_count == 0:
                start_pos = i
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0 and start_pos != -1:
                potential_json = text[start_pos : i + 1]
                try:
                    parsed = json.loads(potential_json)
                    if isinstance(parsed, dict) and "tool" in parsed and "args" in parsed:
                        potential_jsons.append((parsed["tool"], parsed["args"]))
                except json.JSONDecodeError:
                    pass
                start_pos = -1

    matches = potential_jsons

    for tool_name, args in matches:
        try:
            # Create a mock tool call object
            class MockToolCall:
                def __init__(self, tool_name: str, args: dict):
                    self.tool_name = tool_name
                    self.args = args
                    self.tool_call_id = f"fallback_{datetime.now().timestamp()}"

            class MockNode:
                pass

            # Execute the tool through the callback
            mock_call = MockToolCall(tool_name, args)
            mock_node = MockNode()

            await tool_callback(mock_call, mock_node)

            if state_manager.session.show_thoughts:
                from tunacode.ui import console as ui

                await ui.muted(f"FALLBACK: Executed {tool_name} via JSON parsing")

        except Exception as e:
            if state_manager.session.show_thoughts:
                from tunacode.ui import console as ui

                await ui.error(f"Error executing fallback tool {tool_name}: {str(e)}")


async def extract_and_execute_tool_calls(
    text: str, tool_callback: Optional[ToolCallback], state_manager: StateManager
):
    """
    Extract tool calls from text content and execute them.
    Supports multiple formats for maximum compatibility.
    """
    if not tool_callback:
        return

    # Format 1: {"tool": "name", "args": {...}}
    await parse_json_tool_calls(text, tool_callback, state_manager)

    # Format 2: Tool calls in code blocks
    code_block_pattern = r'```json\s*(\{(?:[^{}]|"[^"]*"|(?:\{[^}]*\}))*"tool"(?:[^{}]|"[^"]*"|(?:\{[^}]*\}))*\})\s*```'
    code_matches = re.findall(code_block_pattern, text, re.MULTILINE | re.DOTALL)

    for match in code_matches:
        try:
            tool_data = json.loads(match)
            if "tool" in tool_data and "args" in tool_data:

                class MockToolCall:
                    def __init__(self, tool_name: str, args: dict):
                        self.tool_name = tool_name
                        self.args = args
                        self.tool_call_id = f"codeblock_{datetime.now().timestamp()}"

                class MockNode:
                    pass

                mock_call = MockToolCall(tool_data["tool"], tool_data["args"])
                mock_node = MockNode()

                await tool_callback(mock_call, mock_node)

                if state_manager.session.show_thoughts:
                    from tunacode.ui import console as ui

                    await ui.muted(f"FALLBACK: Executed {tool_data['tool']} from code block")

        except (json.JSONDecodeError, KeyError, Exception) as e:
            if state_manager.session.show_thoughts:
                from tunacode.ui import console as ui

                await ui.error(f"Error parsing code block tool call: {str(e)}")


async def process_request(
    model: ModelName,
    message: str,
    state_manager: StateManager,
    tool_callback: Optional[ToolCallback] = None,
) -> AgentRun:
    agent = get_or_create_agent(model, state_manager)
    mh = state_manager.session.messages.copy()

    # Inject project context from TUNACODE.md files
    try:
        code_style = await get_code_style()
        if code_style:
            message = f"Project context:\n{code_style}\n\nUser request: {message}"
    except Exception:
        pass
    # Get max iterations from config (default: 20)
    max_iterations = state_manager.session.user_config.get("settings", {}).get("max_iterations", 20)
    fallback_enabled = state_manager.session.user_config.get("settings", {}).get(
        "fallback_response", True
    )

    response_state = ResponseState()

    # Reset iteration tracking for this request
    state_manager.session.iteration_count = 0

    async with agent.iter(message, message_history=mh) as agent_run:
        i = 0
        async for node in agent_run:
            state_manager.session.current_iteration = i + 1
            await _process_node(node, tool_callback, state_manager)
            if hasattr(node, "result") and node.result and hasattr(node.result, "output"):
                if node.result.output:
                    response_state.has_user_response = True
            i += 1
            state_manager.session.iteration_count = i

            # Display iteration progress if thoughts are enabled
            if state_manager.session.show_thoughts:
                from tunacode.ui import console as ui

                await ui.muted(f"\nITERATION: {i}/{max_iterations}")

                # Show summary of tools used so far
                if state_manager.session.tool_calls:
                    tool_summary = {}
                    for tc in state_manager.session.tool_calls:
                        tool_name = tc.get("tool", "unknown")
                        tool_summary[tool_name] = tool_summary.get(tool_name, 0) + 1

                    summary_str = ", ".join(
                        [f"{name}: {count}" for name, count in tool_summary.items()]
                    )
                    await ui.muted(f"TOOLS USED: {summary_str}")

            if i >= max_iterations:
                if state_manager.session.show_thoughts:
                    from tunacode.ui import console as ui

                    await ui.warning(f"Reached maximum iterations ({max_iterations})")
                break

        # If we need to add a fallback response, create a wrapper
        if not response_state.has_user_response and i >= max_iterations and fallback_enabled:
            patch_tool_messages("Task incomplete", state_manager=state_manager)
            response_state.has_final_synthesis = True

            # Extract context from the agent run
            tool_calls_summary = []
            files_modified = set()
            commands_run = []

            # Analyze message history for context
            for msg in state_manager.session.messages:
                if hasattr(msg, "parts"):
                    for part in msg.parts:
                        if hasattr(part, "part_kind") and part.part_kind == "tool-call":
                            tool_name = getattr(part, "tool_name", "unknown")
                            tool_calls_summary.append(tool_name)

                            # Track specific operations
                            if tool_name in ["write_file", "update_file"] and hasattr(part, "args"):
                                if isinstance(part.args, dict) and "file_path" in part.args:
                                    files_modified.add(part.args["file_path"])
                            elif tool_name in ["run_command", "bash"] and hasattr(part, "args"):
                                if isinstance(part.args, dict) and "command" in part.args:
                                    commands_run.append(part.args["command"])

            # Build fallback response with context
            fallback = FallbackResponse(
                summary="Reached maximum iterations without producing a final response.",
                progress=f"Completed {i} iterations (limit: {max_iterations})",
            )

            # Get verbosity setting
            verbosity = state_manager.session.user_config.get("settings", {}).get(
                "fallback_verbosity", "normal"
            )

            if verbosity in ["normal", "detailed"]:
                # Add what was attempted
                if tool_calls_summary:
                    tool_counts = {}
                    for tool in tool_calls_summary:
                        tool_counts[tool] = tool_counts.get(tool, 0) + 1

                    fallback.issues.append(f"Executed {len(tool_calls_summary)} tool calls:")
                    for tool, count in sorted(tool_counts.items()):
                        fallback.issues.append(f"  • {tool}: {count}x")

                if verbosity == "detailed":
                    if files_modified:
                        fallback.issues.append(f"\nFiles modified ({len(files_modified)}):")
                        for f in sorted(files_modified)[:5]:  # Limit to 5 files
                            fallback.issues.append(f"  • {f}")
                        if len(files_modified) > 5:
                            fallback.issues.append(f"  • ... and {len(files_modified) - 5} more")

                    if commands_run:
                        fallback.issues.append(f"\nCommands executed ({len(commands_run)}):")
                        for cmd in commands_run[:3]:  # Limit to 3 commands
                            # Truncate long commands
                            display_cmd = cmd if len(cmd) <= 60 else cmd[:57] + "..."
                            fallback.issues.append(f"  • {display_cmd}")
                        if len(commands_run) > 3:
                            fallback.issues.append(f"  • ... and {len(commands_run) - 3} more")

            # Add helpful next steps
            fallback.next_steps.append(
                "The task may be too complex - try breaking it into smaller steps"
            )
            fallback.next_steps.append("Check the output above for any errors or partial progress")
            if files_modified:
                fallback.next_steps.append("Review modified files to see what changes were made")

            # Create comprehensive output
            output_parts = [fallback.summary, ""]

            if fallback.progress:
                output_parts.append(f"Progress: {fallback.progress}")

            if fallback.issues:
                output_parts.append("\nWhat happened:")
                output_parts.extend(fallback.issues)

            if fallback.next_steps:
                output_parts.append("\nSuggested next steps:")
                for step in fallback.next_steps:
                    output_parts.append(f"  • {step}")

            comprehensive_output = "\n".join(output_parts)

            # Create a wrapper object that mimics AgentRun with the required attributes
            class AgentRunWrapper:
                def __init__(self, wrapped_run, fallback_result):
                    self._wrapped = wrapped_run
                    self._result = fallback_result
                    self.response_state = response_state

                def __getattribute__(self, name):
                    # Handle special attributes first to avoid conflicts
                    if name in ["_wrapped", "_result", "response_state"]:
                        return object.__getattribute__(self, name)

                    # Explicitly handle 'result' to return our fallback result
                    if name == "result":
                        return object.__getattribute__(self, "_result")

                    # Delegate all other attributes to the wrapped object
                    try:
                        return getattr(object.__getattribute__(self, "_wrapped"), name)
                    except AttributeError:
                        raise AttributeError(
                            f"'{type(self).__name__}' object has no attribute '{name}'"
                        )

            return AgentRunWrapper(agent_run, SimpleResult(comprehensive_output))

        # For non-fallback cases, we still need to handle the response_state
        # Create a minimal wrapper just to add response_state
        class AgentRunWithState:
            def __init__(self, wrapped_run):
                self._wrapped = wrapped_run
                self.response_state = response_state

            def __getattribute__(self, name):
                # Handle special attributes first
                if name in ["_wrapped", "response_state"]:
                    return object.__getattribute__(self, name)

                # Delegate all other attributes to the wrapped object
                try:
                    return getattr(object.__getattribute__(self, "_wrapped"), name)
                except AttributeError:
                    raise AttributeError(
                        f"'{type(self).__name__}' object has no attribute '{name}'"
                    )

        return AgentRunWithState(agent_run)
