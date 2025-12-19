"""Tunacode search environment for RL training.

This package provides:
- Task schemas for code search tasks
- Rubrics for scoring model outputs
- Environment class for integration with training frameworks
"""

from tunacode_search.environment import CodeSearchEnvironment
from tunacode_search.rubrics import (
    CompositeRubric,
    Rubric,
    TaskCompletionRubric,
    ToolArgsRubric,
    ToolSequenceRubric,
)
from tunacode_search.schema import (
    ModelResponse,
    SearchTask,
    TaskType,
    ToolCall,
    ToolName,
)

__all__ = [
    "CodeSearchEnvironment",
    "CompositeRubric",
    "ModelResponse",
    "Rubric",
    "SearchTask",
    "TaskCompletionRubric",
    "TaskType",
    "ToolArgsRubric",
    "ToolCall",
    "ToolName",
    "ToolSequenceRubric",
]

__version__ = "0.1.0"
