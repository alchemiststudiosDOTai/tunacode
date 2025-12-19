"""Task schema for code search training tasks.

Defines the data structures for search tasks used in RL training.
"""

from dataclasses import dataclass, field
from enum import Enum


class TaskType(Enum):
    """Types of code search tasks."""

    FILE_SEARCH = "file_search"  # Find files by pattern
    CONTENT_SEARCH = "content_search"  # Search for content in files
    DEFINITION_SEARCH = "definition_search"  # Find class/function definitions
    USAGE_SEARCH = "usage_search"  # Find usages of a symbol


class ToolName(Enum):
    """Available search tools."""

    GLOB = "glob"
    GREP = "grep"
    READ_FILE = "read_file"


@dataclass
class ToolCall:
    """Represents a single tool call in a trajectory."""

    tool: ToolName
    args: dict[str, str | int | bool | list[str]]
    result: str | None = None


@dataclass
class SearchTask:
    """A code search task for training.

    Attributes:
        task_id: Unique identifier for the task
        task_type: Category of search task
        query: Natural language query from user
        codebase_root: Root directory of the codebase to search
        expected_tool_sequence: Correct sequence of tools to use
        expected_files: Files that should be found/read
        expected_content: Content patterns that should be found
        metadata: Additional task metadata
    """

    task_id: str
    task_type: TaskType
    query: str
    codebase_root: str
    expected_tool_sequence: list[ToolName]
    expected_files: list[str] = field(default_factory=list)
    expected_content: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert task to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "query": self.query,
            "codebase_root": self.codebase_root,
            "expected_tool_sequence": [t.value for t in self.expected_tool_sequence],
            "expected_files": self.expected_files,
            "expected_content": self.expected_content,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SearchTask":
        """Create task from dictionary."""
        return cls(
            task_id=data["task_id"],
            task_type=TaskType(data["task_type"]),
            query=data["query"],
            codebase_root=data["codebase_root"],
            expected_tool_sequence=[ToolName(t) for t in data["expected_tool_sequence"]],
            expected_files=data.get("expected_files", []),
            expected_content=data.get("expected_content", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ModelResponse:
    """Parsed model response containing tool calls.

    Attributes:
        raw_text: Original model output text
        tool_calls: Extracted tool calls from the response
        final_answer: Any final answer text after tool calls
    """

    raw_text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    final_answer: str = ""
