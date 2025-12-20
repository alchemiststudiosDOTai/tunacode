"""Pydantic models for ShareGPT-format training data with tool calling support.

This module defines the data structures for training LLMs on tool-calling
patterns using the ShareGPT conversation format.

ShareGPT Format with Tools:
{
    "conversations": [
        {"from": "human", "value": "user instruction"},
        {"from": "function_call", "value": "{\"name\": \"tool\", \"arguments\": {...}}"},
        {"from": "observation", "value": "tool result"},
        {"from": "gpt", "value": "model response"}
    ],
    "system": "system prompt (optional)",
    "tools": "[{\"name\": \"tool\", \"description\": \"...\", ...}]"
}
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Valid roles in ShareGPT conversation format."""

    HUMAN = "human"
    GPT = "gpt"
    FUNCTION_CALL = "function_call"
    OBSERVATION = "observation"
    SYSTEM = "system"


class Message(BaseModel):
    """A single message in a ShareGPT conversation.

    Attributes:
        from_: The role of the message sender (human, gpt, function_call, observation)
        value: The content of the message
    """

    from_: MessageRole = Field(alias="from")
    value: str

    model_config = {"populate_by_name": True}


class FunctionCall(BaseModel):
    """A function/tool call made by the model.

    Attributes:
        name: The name of the tool being called
        arguments: The arguments passed to the tool as a dict
    """

    name: str
    arguments: dict[str, Any]

    def to_json_str(self) -> str:
        """Serialize to JSON string for message value."""
        import json

        return json.dumps({"name": self.name, "arguments": self.arguments})


class ToolParameter(BaseModel):
    """A parameter in a tool's function signature.

    Attributes:
        name: Parameter name
        type: JSON Schema type (string, integer, boolean, etc.)
        description: Human-readable description
        required: Whether the parameter is required
        default: Default value if any
    """

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class ToolDefinition(BaseModel):
    """Definition of a tool for training data.

    This mirrors the JSON Schema format used by OpenAI and other providers
    for function/tool definitions.

    Attributes:
        name: Tool name (e.g., 'read_file')
        description: Human-readable description of what the tool does
        parameters: List of ToolParameter objects
    """

    name: str
    description: str
    parameters: list[ToolParameter]

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema format for training data."""
        properties: dict[str, Any] = {}
        required_params: list[str] = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop

            if param.required:
                required_params.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required_params,
                },
            },
        }


class ShareGPTConversation(BaseModel):
    """A complete ShareGPT-format conversation for training.

    This is the primary data structure for training data. Each conversation
    represents a complete interaction that may include:
    - User queries
    - Model reasoning
    - Tool calls
    - Tool results (observations)
    - Final model responses

    Attributes:
        conversations: List of messages in the conversation
        system: Optional system prompt
        tools: Optional JSON string of tool definitions
    """

    conversations: list[Message]
    system: str | None = None
    tools: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "conversations": [
                {"from": msg.from_.value, "value": msg.value}
                for msg in self.conversations
            ]
        }
        if self.system:
            result["system"] = self.system
        if self.tools:
            result["tools"] = self.tools
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ShareGPTConversation":
        """Create from dictionary (e.g., loaded from JSON)."""
        conversations = [
            Message(from_=MessageRole(msg["from"]), value=msg["value"])
            for msg in data["conversations"]
        ]
        return cls(
            conversations=conversations,
            system=data.get("system"),
            tools=data.get("tools"),
        )

    def add_human_message(self, content: str) -> None:
        """Add a human/user message to the conversation."""
        self.conversations.append(Message(from_=MessageRole.HUMAN, value=content))

    def add_gpt_message(self, content: str) -> None:
        """Add a GPT/assistant message to the conversation."""
        self.conversations.append(Message(from_=MessageRole.GPT, value=content))

    def add_function_call(self, call: FunctionCall) -> None:
        """Add a function call message to the conversation."""
        self.conversations.append(
            Message(from_=MessageRole.FUNCTION_CALL, value=call.to_json_str())
        )

    def add_observation(self, result: str) -> None:
        """Add a tool result/observation message to the conversation."""
        self.conversations.append(Message(from_=MessageRole.OBSERVATION, value=result))


class TrainingDataset(BaseModel):
    """A collection of training conversations.

    Attributes:
        conversations: List of ShareGPT conversations
        metadata: Optional metadata about the dataset
    """

    conversations: list[ShareGPTConversation]
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_jsonl(self) -> str:
        """Convert to JSONL format (one JSON object per line)."""
        import json

        lines = [json.dumps(conv.to_dict()) for conv in self.conversations]
        return "\n".join(lines)

    def save_jsonl(self, path: str) -> None:
        """Save dataset to JSONL file."""
        from pathlib import Path

        Path(path).write_text(self.to_jsonl(), encoding="utf-8")

    @classmethod
    def load_jsonl(cls, path: str) -> "TrainingDataset":
        """Load dataset from JSONL file."""
        import json
        from pathlib import Path

        text = Path(path).read_text(encoding="utf-8")
        conversations = [
            ShareGPTConversation.from_dict(json.loads(line))
            for line in text.strip().split("\n")
            if line.strip()
        ]
        return cls(conversations=conversations)
