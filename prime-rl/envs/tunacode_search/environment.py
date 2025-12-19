"""Code search environment for RL training.

This module provides the main environment class that integrates with
training frameworks like prime-rl/verifiers.
"""

import json
from pathlib import Path
from typing import Any

from tunacode_search.rubrics import (
    CompositeRubric,
    Rubric,
    RubricScore,
    create_model_response,
)
from tunacode_search.schema import SearchTask


class CodeSearchEnvironment:
    """Environment for training code search tool selection.

    This environment:
    1. Loads search tasks from a dataset
    2. Provides tasks to the model
    3. Scores model responses using rubrics

    Compatible with verifiers.Environment interface for prime-rl integration.
    """

    def __init__(
        self,
        dataset_path: str | Path | None = None,
        rubric: Rubric | None = None,
        max_turns: int = 5,
    ):
        """Initialize the environment.

        Args:
            dataset_path: Path to JSONL dataset file
            rubric: Rubric for scoring responses. Defaults to CompositeRubric.
            max_turns: Maximum tool calls per task
        """
        self._dataset_path = Path(dataset_path) if dataset_path else None
        self._rubric = rubric or CompositeRubric()
        self._max_turns = max_turns
        self._tasks: list[SearchTask] = []

        if self._dataset_path and self._dataset_path.exists():
            self._load_dataset()

    def _load_dataset(self) -> None:
        """Load tasks from JSONL file."""
        if not self._dataset_path:
            return

        with open(self._dataset_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                self._tasks.append(SearchTask.from_dict(data))

    def get_dataset(self) -> list[dict[str, Any]]:
        """Return dataset in format expected by training frameworks.

        Returns:
            List of task dictionaries with 'prompt' and 'ground_truth' keys.
        """
        return [self._task_to_prompt(task) for task in self._tasks]

    def _task_to_prompt(self, task: SearchTask) -> dict[str, Any]:
        """Convert a SearchTask to training prompt format."""
        system_prompt = self._build_system_prompt()
        user_message = task.query

        return {
            "prompt": f"<|system|>{system_prompt}<|user|>{user_message}",
            "ground_truth": {
                "task_id": task.task_id,
                "expected_tool_sequence": [t.value for t in task.expected_tool_sequence],
                "expected_files": task.expected_files,
                "expected_content": task.expected_content,
            },
            "task": task,
        }

    def _build_system_prompt(self) -> str:
        """Build the system prompt for code search tasks."""
        return """You are a code search assistant with access to the following tools:

1. glob - Find files matching patterns
   Arguments: pattern (required), directory, recursive, include_hidden, max_results
   Example: {"tool": "glob", "args": {"pattern": "**/*.py"}}

2. grep - Search file contents
   Arguments: pattern (required), directory, case_sensitive, include_files, max_results, context_lines
   Example: {"tool": "grep", "args": {"pattern": "def process_request", "include_files": "*.py"}}

3. read_file - Read file contents
   Arguments: filepath (required), offset, limit
   Example: {"tool": "read_file", "args": {"filepath": "/path/to/file.py"}}

Follow the search funnel pattern:
1. GLOB: First find candidate files by pattern
2. GREP: Then search content in those files
3. READ: Finally read specific files for details

Output tool calls in this format:
<tool_call>{"name": "tool_name", "arguments": {...}}</tool_call>"""

    @property
    def rubric(self) -> Rubric:
        """Return the scoring rubric."""
        return self._rubric

    def score(self, task: SearchTask, response_text: str) -> RubricScore:
        """Score a model's response for a given task.

        Args:
            task: The search task
            response_text: Raw model output text

        Returns:
            RubricScore with score and reasoning
        """
        response = create_model_response(response_text)
        return self._rubric.score(task, response)

    def score_response(self, task_dict: dict[str, Any], response_text: str) -> float:
        """Score a response given task dictionary (verifiers interface).

        Args:
            task_dict: Task dictionary from get_dataset()
            response_text: Raw model output

        Returns:
            Score from 0.0 to 1.0
        """
        task = task_dict.get("task")
        if task is None:
            # Reconstruct from ground_truth
            ground_truth = task_dict.get("ground_truth", {})
            task = SearchTask(
                task_id=ground_truth.get("task_id", "unknown"),
                task_type=ground_truth.get("task_type", "content_search"),
                query=task_dict.get("prompt", ""),
                codebase_root=".",
                expected_tool_sequence=ground_truth.get("expected_tool_sequence", []),
                expected_files=ground_truth.get("expected_files", []),
                expected_content=ground_truth.get("expected_content", []),
            )

        result = self.score(task, response_text)
        return result.score

    def add_task(self, task: SearchTask) -> None:
        """Add a task to the dataset."""
        self._tasks.append(task)

    def add_tasks(self, tasks: list[SearchTask]) -> None:
        """Add multiple tasks to the dataset."""
        self._tasks.extend(tasks)

    def save_dataset(self, path: str | Path) -> None:
        """Save current tasks to JSONL file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            for task in self._tasks:
                f.write(json.dumps(task.to_dict()) + "\n")

    def __len__(self) -> int:
        """Return number of tasks."""
        return len(self._tasks)

    def __iter__(self):
        """Iterate over tasks."""
        return iter(self._tasks)
