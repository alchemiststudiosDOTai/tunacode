"""Training module for fine-tuning LLMs on tunacode tool-calling patterns.

This module provides:
- schema: Pydantic models for ShareGPT-format training data
- tool_extractor: Extract tool definitions to JSON Schema
- dataset_generator: Generate synthetic training conversations
- scenarios: Tool usage scenario library
- config: Training configuration
- train: Unsloth fine-tuning script
"""

from tunacode.training.schema import (
    FunctionCall,
    Message,
    ShareGPTConversation,
    ToolDefinition,
    ToolParameter,
    TrainingDataset,
)
from tunacode.training.tool_extractor import (
    extract_tool_definition,
    get_tools_for_training,
    get_tools_json_schema,
    get_tunacode_tool_registry,
)

__all__ = [
    "FunctionCall",
    "Message",
    "ShareGPTConversation",
    "ToolDefinition",
    "ToolParameter",
    "TrainingDataset",
    "extract_tool_definition",
    "get_tools_for_training",
    "get_tools_json_schema",
    "get_tunacode_tool_registry",
]
