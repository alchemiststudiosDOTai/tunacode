"""Rubrics for scoring model outputs on code search tasks.

Each rubric evaluates a specific aspect of the model's performance:
- ToolSequenceRubric: Correct tool selection order (GLOB -> GREP -> READ)
- ToolArgsRubric: Valid JSON tool arguments
- TaskCompletionRubric: Finding the expected files/content
- CompositeRubric: Weighted combination of all rubrics
"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from tunacode_search.schema import ModelResponse, SearchTask, ToolCall, ToolName

# Tool argument schemas for validation
TOOL_SCHEMAS: dict[str, dict[str, type | tuple[type, ...]]] = {
    "glob": {
        "pattern": str,  # Required
        "directory": str,
        "recursive": bool,
        "include_hidden": bool,
        "max_results": int,
        "case_sensitive": bool,
    },
    "grep": {
        "pattern": str,  # Required
        "directory": str,
        "case_sensitive": bool,
        "include_files": str,
        "exclude_files": str,
        "max_results": int,
        "context_lines": int,
        "output_mode": str,
    },
    "read_file": {
        "filepath": str,  # Required
        "offset": int,
        "limit": int,
    },
}

REQUIRED_ARGS: dict[str, list[str]] = {
    "glob": ["pattern"],
    "grep": ["pattern"],
    "read_file": ["filepath"],
}


@dataclass
class RubricScore:
    """Score result from a rubric evaluation."""

    score: float  # 0.0 to 1.0
    reasoning: str  # Explanation for the score
    details: dict[str, float | str | list[str]] | None = None


class Rubric(ABC):
    """Base class for scoring rubrics."""

    def __init__(self, weight: float = 1.0):
        self.weight = weight

    @abstractmethod
    def score(self, task: SearchTask, response: ModelResponse) -> RubricScore:
        """Score the model's response for a given task.

        Args:
            task: The search task being evaluated
            response: The model's parsed response

        Returns:
            RubricScore with score 0.0-1.0 and reasoning
        """
        pass


class ToolSequenceRubric(Rubric):
    """Scores whether the model used tools in the correct order.

    The ideal pattern is GLOB -> GREP -> READ (the search funnel).
    Partial credit is given for correct subsequences.
    """

    # Valid tool progressions (earlier -> later)
    VALID_TRANSITIONS: set[tuple[ToolName, ToolName]] = {
        (ToolName.GLOB, ToolName.GREP),
        (ToolName.GLOB, ToolName.READ_FILE),
        (ToolName.GREP, ToolName.READ_FILE),
    }

    def score(self, task: SearchTask, response: ModelResponse) -> RubricScore:
        """Score tool sequence correctness."""
        if not response.tool_calls:
            return RubricScore(
                score=0.0,
                reasoning="No tool calls in response",
            )

        actual_sequence = [tc.tool for tc in response.tool_calls]
        expected_sequence = task.expected_tool_sequence

        # Exact match
        if actual_sequence == expected_sequence:
            return RubricScore(
                score=1.0,
                reasoning="Tool sequence matches expected exactly",
                details={"actual": [t.value for t in actual_sequence]},
            )

        # Check for valid transitions (no backwards steps)
        invalid_transitions = []
        for i in range(len(actual_sequence) - 1):
            current = actual_sequence[i]
            next_tool = actual_sequence[i + 1]

            # Check if transition is valid (not going backwards)
            reverse_pair = (next_tool, current)
            if reverse_pair in self.VALID_TRANSITIONS:
                invalid_transitions.append((current.value, next_tool.value))

        if invalid_transitions:
            penalty = 0.2 * len(invalid_transitions)
            score = max(0.0, 0.5 - penalty)
            return RubricScore(
                score=score,
                reasoning=f"Invalid tool order: {invalid_transitions}",
                details={"invalid_transitions": invalid_transitions},
            )

        # Partial match - check overlap with expected
        actual_set = set(actual_sequence)
        expected_set = set(expected_sequence)
        overlap = len(actual_set & expected_set)
        total = len(expected_set)

        if total == 0:
            score = 0.5  # No expectation, give partial credit
        else:
            score = 0.5 + 0.5 * (overlap / total)

        return RubricScore(
            score=score,
            reasoning=f"Partial sequence match: {overlap}/{total} expected tools used",
            details={
                "actual": [t.value for t in actual_sequence],
                "expected": [t.value for t in expected_sequence],
                "overlap": overlap,
            },
        )


class ToolArgsRubric(Rubric):
    """Scores whether tool arguments are valid JSON and match schemas."""

    def score(self, task: SearchTask, response: ModelResponse) -> RubricScore:
        """Score tool argument validity."""
        if not response.tool_calls:
            return RubricScore(
                score=0.0,
                reasoning="No tool calls in response",
            )

        valid_count = 0
        invalid_args: list[str] = []

        for tc in response.tool_calls:
            tool_name = tc.tool.value
            args = tc.args

            if not self._validate_args(tool_name, args):
                invalid_args.append(f"{tool_name}: {args}")
            else:
                valid_count += 1

        total = len(response.tool_calls)
        score = valid_count / total if total > 0 else 0.0

        if score == 1.0:
            reasoning = "All tool arguments are valid"
        elif score > 0:
            reasoning = f"{valid_count}/{total} tool calls have valid arguments"
        else:
            reasoning = "No valid tool arguments"

        return RubricScore(
            score=score,
            reasoning=reasoning,
            details={
                "valid_count": valid_count,
                "total": total,
                "invalid": invalid_args,
            },
        )

    def _validate_args(self, tool_name: str, args: dict) -> bool:
        """Validate arguments against tool schema."""
        if tool_name not in TOOL_SCHEMAS:
            return False

        schema = TOOL_SCHEMAS[tool_name]
        required = REQUIRED_ARGS.get(tool_name, [])

        # Check required args present
        for req in required:
            if req not in args:
                return False

        # Check arg types
        for arg_name, arg_value in args.items():
            if arg_name not in schema:
                continue  # Allow extra args (forward compat)

            expected_type = schema[arg_name]
            if not isinstance(arg_value, expected_type):
                return False

        return True


class TaskCompletionRubric(Rubric):
    """Scores whether the model found the expected files/content."""

    def score(self, task: SearchTask, response: ModelResponse) -> RubricScore:
        """Score task completion based on expected files and content."""
        found_files: set[str] = set()
        found_content: set[str] = set()

        # Extract files mentioned in tool calls and results
        for tc in response.tool_calls:
            # Check for filepath in read_file calls
            if tc.tool == ToolName.READ_FILE:
                filepath = tc.args.get("filepath", "")
                if filepath:
                    found_files.add(filepath)

            # Check results for file paths and content
            if tc.result:
                self._extract_from_result(tc.result, found_files, found_content, task)

        # Also check final answer
        if response.final_answer:
            self._extract_from_result(response.final_answer, found_files, found_content, task)

        # Score files
        file_score = 0.0
        if task.expected_files:
            matched_files = sum(1 for ef in task.expected_files if self._file_matches(ef, found_files))
            file_score = matched_files / len(task.expected_files)

        # Score content
        content_score = 0.0
        if task.expected_content:
            matched_content = sum(1 for ec in task.expected_content if ec.lower() in str(found_content).lower())
            content_score = matched_content / len(task.expected_content)

        # Combined score (weighted by what's expected)
        if task.expected_files and task.expected_content:
            score = 0.5 * file_score + 0.5 * content_score
        elif task.expected_files:
            score = file_score
        elif task.expected_content:
            score = content_score
        else:
            # No expectations - check if any tools were used
            score = 1.0 if response.tool_calls else 0.0

        reasoning_parts = []
        if task.expected_files:
            reasoning_parts.append(f"Files: {file_score:.0%}")
        if task.expected_content:
            reasoning_parts.append(f"Content: {content_score:.0%}")

        return RubricScore(
            score=score,
            reasoning=" | ".join(reasoning_parts) if reasoning_parts else "Task complete",
            details={
                "file_score": file_score,
                "content_score": content_score,
                "found_files": list(found_files),
            },
        )

    def _file_matches(self, expected: str, found: set[str]) -> bool:
        """Check if expected file was found (supports partial paths)."""
        for f in found:
            if expected in f or f.endswith(expected):
                return True
        return False

    def _extract_from_result(
        self,
        result: str,
        found_files: set[str],
        found_content: set[str],
        task: SearchTask,
    ) -> None:
        """Extract file paths and content from a result string."""
        # Look for file paths (common patterns)
        path_patterns = [
            r"(/[\w/.-]+\.[\w]+)",  # Unix absolute paths
            r"([\w/.-]+\.py)",  # Python files
            r"([\w/.-]+\.ts)",  # TypeScript files
            r"([\w/.-]+\.js)",  # JavaScript files
        ]

        for pattern in path_patterns:
            matches = re.findall(pattern, result)
            found_files.update(matches)

        # Add result text as potential content match
        found_content.add(result)


class CompositeRubric(Rubric):
    """Combines multiple rubrics with configurable weights."""

    def __init__(
        self,
        rubrics: list[Rubric] | None = None,
        weights: dict[str, float] | None = None,
    ):
        """Initialize composite rubric.

        Args:
            rubrics: List of rubrics to combine. If None, uses defaults.
            weights: Optional dict mapping rubric class names to weights.
                     Overrides individual rubric weights.
        """
        super().__init__(weight=1.0)

        if rubrics is None:
            rubrics = [
                ToolSequenceRubric(weight=0.3),
                ToolArgsRubric(weight=0.3),
                TaskCompletionRubric(weight=0.4),
            ]

        self.rubrics = rubrics

        # Apply custom weights if provided
        if weights:
            for rubric in self.rubrics:
                class_name = rubric.__class__.__name__
                if class_name in weights:
                    rubric.weight = weights[class_name]

        # Normalize weights to sum to 1.0
        total_weight = sum(r.weight for r in self.rubrics)
        if total_weight > 0:
            for rubric in self.rubrics:
                rubric.weight /= total_weight

    def score(self, task: SearchTask, response: ModelResponse) -> RubricScore:
        """Compute weighted average of all rubric scores."""
        component_scores: dict[str, float] = {}
        reasoning_parts: list[str] = []
        weighted_sum = 0.0

        for rubric in self.rubrics:
            result = rubric.score(task, response)
            class_name = rubric.__class__.__name__

            component_scores[class_name] = result.score
            weighted_sum += result.score * rubric.weight
            reasoning_parts.append(f"{class_name}: {result.score:.2f}")

        return RubricScore(
            score=weighted_sum,
            reasoning=" | ".join(reasoning_parts),
            details={"components": component_scores},
        )


def parse_tool_calls(raw_text: str) -> list[ToolCall]:
    """Parse tool calls from model output text.

    Supports formats:
    - JSON: {"tool": "glob", "args": {...}}
    - XML-style: <tool_call>{"name": "glob", "arguments": {...}}</tool_call>
    - Function call: glob(pattern="*.py")
    """
    tool_calls: list[ToolCall] = []

    # Try XML-style tool_call tags
    xml_pattern = r"<tool_call>(.*?)</tool_call>"
    xml_matches = re.findall(xml_pattern, raw_text, re.DOTALL)

    for match in xml_matches:
        try:
            data = json.loads(match.strip())
            tool_name = data.get("name") or data.get("tool")
            args = data.get("arguments") or data.get("args", {})

            if tool_name:
                tool_calls.append(ToolCall(tool=ToolName(tool_name), args=args))
        except (json.JSONDecodeError, ValueError):
            continue

    # Try standalone JSON objects
    if not tool_calls:
        json_pattern = r'\{[^{}]*"(?:tool|name)"[^{}]*\}'
        json_matches = re.findall(json_pattern, raw_text)

        for match in json_matches:
            try:
                data = json.loads(match)
                tool_name = data.get("tool") or data.get("name")
                args = data.get("args") or data.get("arguments", {})

                if tool_name and tool_name in [t.value for t in ToolName]:
                    tool_calls.append(ToolCall(tool=ToolName(tool_name), args=args))
            except (json.JSONDecodeError, ValueError):
                continue

    return tool_calls


def create_model_response(raw_text: str) -> ModelResponse:
    """Create a ModelResponse from raw model output."""
    tool_calls = parse_tool_calls(raw_text)

    # Extract final answer (text after last tool call)
    final_answer = ""
    if tool_calls:
        last_tool_pattern = r"</tool_call>\s*(.*)$"
        match = re.search(last_tool_pattern, raw_text, re.DOTALL)
        if match:
            final_answer = match.group(1).strip()

    return ModelResponse(
        raw_text=raw_text,
        tool_calls=tool_calls,
        final_answer=final_answer,
    )
