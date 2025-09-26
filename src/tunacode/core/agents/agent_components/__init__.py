"""Agent components package for modular agent functionality."""

from tunacode.ui.tool_descriptions import get_batch_description

from .agent_config import get_or_create_agent
from .agent_helpers import (
    create_empty_response_message,
    create_fallback_response,
    create_progress_summary,
    create_user_message,
    format_fallback_output,
    get_recent_tools_context,
    get_tool_description,
    get_tool_summary,
    get_user_prompt_part_class,
    handle_empty_response,
)
from .json_tool_parser import extract_and_execute_tool_calls, parse_json_tool_calls
from .message_handler import get_model_messages, patch_tool_messages
from .node_processor import _process_node
from .response_state import ResponseState
from .result_wrapper import AgentRunWithState, AgentRunWrapper, SimpleResult
from .streaming import stream_model_request_node
from .task_completion import check_task_completion
from .tool_buffer import ToolBuffer
from .tool_executor import execute_tools_parallel

__all__ = [
    "get_or_create_agent",
    "extract_and_execute_tool_calls",
    "parse_json_tool_calls",
    "get_model_messages",
    "patch_tool_messages",
    "_process_node",
    "ResponseState",
    "AgentRunWithState",
    "AgentRunWrapper",
    "SimpleResult",
    "check_task_completion",
    "ToolBuffer",
    "execute_tools_parallel",
    "create_empty_response_message",
    "create_fallback_response",
    "create_progress_summary",
    "create_user_message",
    "format_fallback_output",
    "get_recent_tools_context",
    "get_tool_description",
    "get_tool_summary",
    "get_user_prompt_part_class",
    "handle_empty_response",
    "stream_model_request_node",
    "get_batch_description",
]
