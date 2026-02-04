"""Orchestrator package for agent node processing.

Architecture (first principles):
- node_processor: Main coordinator (thin, delegates)
- extractors: Pure data extraction from nodes
- tool_dispatch: Tool call coordination
- tool_registry_ops: Registry interactions
- tool_returns: Tool return emission
- state_ops: State machine transitions
- debug_formatter: Debug output formatting
- message_recorder: Thought persistence
- usage_tracker: Token/cost tracking
"""

# Primary export - the node processor
from .node_processor import process_node

# Tool dispatch utilities needed by external code
from .tool_dispatch import has_tool_calls

# Registry operations needed by tool_returns
from .tool_registry_ops import get_tool_args as consume_tool_call_args

__all__ = [
    "process_node",
    "has_tool_calls",
    "consume_tool_call_args",
]
