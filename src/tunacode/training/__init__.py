"""Training module for fine-tuning LLMs on tunacode tool-calling patterns.

This module provides:
- schema: Pydantic models for ShareGPT-format training data
- tool_extractor: Extract tool definitions to JSON Schema
- dataset_generator: Generate synthetic training conversations
- scenarios: Tool usage scenario library
- config: Training configuration
- train: Unsloth fine-tuning script
"""

from tunacode.training.config import (
    LoraConfig,
    TrainingConfig,
    default_config,
    fast_iteration_config,
    small_gpu_config,
)
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
    # Config
    "LoraConfig",
    "TrainingConfig",
    "default_config",
    "fast_iteration_config",
    "small_gpu_config",
    # Schema
    "FunctionCall",
    "Message",
    "ShareGPTConversation",
    "ToolDefinition",
    "ToolParameter",
    "TrainingDataset",
    # Tool extraction
    "extract_tool_definition",
    "get_tools_for_training",
    "get_tools_json_schema",
    "get_tunacode_tool_registry",
]
