"""Tool buffer for managing parallel execution of read-only tools."""

from typing import Any


class ToolBuffer:
    """Buffer for collecting read-only tool calls to execute in parallel."""

    def __init__(self) -> None:
        self.read_only_tasks: list[tuple[Any, Any]] = []

    def add(self, part: Any, node: Any) -> None:
        """Add a read-only tool call to the buffer."""
        self.read_only_tasks.append((part, node))

    def flush(self) -> list[tuple[Any, Any]]:
        """Return buffered tasks and clear the buffer."""
        tasks = self.read_only_tasks
        self.read_only_tasks = []
        return tasks

    def has_tasks(self) -> bool:
        """Check if there are buffered tasks."""
        return len(self.read_only_tasks) > 0

    def size(self) -> int:
        """Return the number of buffered tasks."""
        return len(self.read_only_tasks)

    def peek(self) -> list[tuple[Any, Any]]:
        """Return buffered tasks without clearing the buffer."""
        return self.read_only_tasks.copy()

    def count_by_type(self) -> dict[str, int]:
        """Count buffered tools by type for metrics and debugging."""
        counts: dict[str, int] = {}
        for part, _ in self.read_only_tasks:
            tool_name = getattr(part, "tool_name", "unknown")
            counts[tool_name] = counts.get(tool_name, 0) + 1
        return counts

    def clear(self) -> None:
        """Clear all buffered tasks without executing them."""
        self.read_only_tasks.clear()
