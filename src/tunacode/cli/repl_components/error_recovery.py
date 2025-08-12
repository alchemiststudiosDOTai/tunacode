"""
Module: tunacode.cli.repl_components.error_recovery

Error recovery utilities for the REPL.
"""

import logging

from tunacode.types import StateManager
from tunacode.ui import console as ui

from .tool_executor import tool_handler

logger = logging.getLogger(__name__)

MSG_JSON_RECOVERY = "Recovered using JSON tool parsing"
MSG_JSON_ARGS_RECOVERY = "Recovered from malformed tool arguments"


async def attempt_json_args_recovery(e: Exception, state_manager: StateManager) -> bool:
    """
    Attempt to recover from JSON parsing errors in tool arguments.

    This handles cases where the model emits concatenated JSON objects
    or other malformed JSON in tool call arguments.

    Returns:
        bool: True if recovery was successful, False otherwise
    """
    error_str = str(e).lower()

    # Check if this is a JSON parsing error with tool arguments
    if not any(
        keyword in error_str for keyword in ["invalid json", "extra data", "jsondecodeerror"]
    ):
        return False

    if not state_manager.session.messages:
        return False

    last_msg = state_manager.session.messages[-1]
    if not hasattr(last_msg, "parts"):
        return False

    # Look for tool call parts with malformed args
    for part in last_msg.parts:
        if hasattr(part, "tool_name") and hasattr(part, "args"):
            # This is a structured tool call with potentially malformed args
            try:
                from tunacode.utils.json_utils import split_concatenated_json

                # Try to split concatenated JSON objects in the args
                if isinstance(part.args, str):
                    logger.info(f"Attempting to recover malformed args for tool {part.tool_name}")

                    try:
                        json_objects = split_concatenated_json(part.args)
                        if json_objects:
                            # Use the first object as the args
                            part.args = json_objects[0]

                            # Execute the recovered tool call
                            await tool_handler(part, state_manager)

                            await ui.warning(f"Warning: {MSG_JSON_ARGS_RECOVERY}")
                            logger.info(
                                f"Successfully recovered tool {part.tool_name} with split JSON args",
                                extra={
                                    "original_args": part.args,
                                    "recovered_args": json_objects[0],
                                },
                            )
                            return True

                    except Exception as split_exc:
                        logger.debug(f"Failed to split JSON args: {split_exc}")
                        continue

            except Exception as recovery_exc:
                logger.error(
                    f"Error during JSON args recovery for tool {getattr(part, 'tool_name', 'unknown')}",
                    exc_info=True,
                    extra={"recovery_exception": str(recovery_exc)},
                )
                continue

    return False


async def attempt_tool_recovery(e: Exception, state_manager: StateManager) -> bool:
    """
    Attempt to recover from tool calling failures by parsing raw JSON from the last message.

    Returns:
        bool: True if recovery was successful, False otherwise
    """
    error_str = str(e).lower()
    tool_keywords = ["tool", "function", "call", "schema"]
    json_keywords = ["json", "invalid json", "jsondecodeerror", "extra data", "validation"]
    recovery_keywords = tool_keywords + json_keywords

    if not any(keyword in error_str for keyword in recovery_keywords):
        return False

    # First, try JSON args recovery for structured tool calls with malformed args
    if await attempt_json_args_recovery(e, state_manager):
        return True

    if not state_manager.session.messages:
        return False

    last_msg = state_manager.session.messages[-1]
    if not hasattr(last_msg, "parts"):
        return False

    for part in last_msg.parts:
        content_to_parse = getattr(part, "content", None)
        if not isinstance(content_to_parse, str) or not content_to_parse.strip():
            continue

        logger.debug(
            "Attempting JSON tool recovery on content",
            extra={
                "content_preview": content_to_parse[:200],
                "original_error": str(e),
            },
        )
        await ui.muted(
            f"⚠️ Model response error. Attempting to recover by parsing tools from text: {str(e)[:100]}..."
        )

        try:
            from tunacode.core.agents.main import extract_and_execute_tool_calls

            def tool_callback_with_state(tool_part, _node):
                return tool_handler(tool_part, state_manager)

            # This function now returns the number of tools found
            tools_found = await extract_and_execute_tool_calls(
                content_to_parse, tool_callback_with_state, state_manager
            )

            # Treat any truthy return value as success – we don't depend on an exact count.
            if tools_found:
                await ui.warning(f" {MSG_JSON_RECOVERY}")
                logger.info(
                    "Successfully recovered from JSON tool parsing error.",
                    extra={"tools_executed": tools_found},
                )
                return True
            else:
                logger.debug("Recovery attempted, but no tools were found in content.")

        except Exception as recovery_exc:
            logger.error(
                "Exception during JSON tool recovery attempt",
                exc_info=True,
                extra={"recovery_exception": str(recovery_exc)},
            )
            continue  # Try next part if available

    # If we attempted recovery but could not execute any tools, simply
    # return False so that the caller can handle the original error. We avoid
    # emitting an additional error message here to prevent duplicate UI
    # notifications which would otherwise break expectations in unit tests.
    return False
