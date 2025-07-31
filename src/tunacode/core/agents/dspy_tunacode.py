#!/usr/bin/env python3
"""
TunaCode DSPy Production Module

Optimizes tool selection and task planning for TunaCode using DSPy.
Includes 3-4 tool batching optimization for 3x performance gains.
"""

import json
import logging
import os
import re
from typing import Dict, List

import dspy
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Tool Categories for TunaCode
TOOL_CATEGORIES = {
    "read_only": ["read_file", "grep", "list_dir", "glob"],  # Parallel-executable
    "task_management": ["todo"],  # Fast, sequential
    "write_execute": [
        "write_file",
        "update_file",
        "run_command",
        "bash",
    ],  # Sequential, needs confirmation
}

ALL_TOOLS = [tool for category in TOOL_CATEGORIES.values() for tool in category]


class ToolSelectionSignature(dspy.Signature):
    """Select optimal tools with batching awareness."""

    user_request: str = dspy.InputField(desc="The user's request or task")
    current_directory: str = dspy.InputField(desc="Current working directory context")
    tools_json: str = dspy.OutputField(
        desc="JSON array of tool calls with batch grouping, e.g. [[tool1, tool2, tool3], [tool4]]"
    )
    requires_confirmation: bool = dspy.OutputField(
        desc="Whether any tools require user confirmation"
    )
    reasoning: str = dspy.OutputField(desc="Explanation of tool choice and batching strategy")


class TaskPlanningSignature(dspy.Signature):
    """Break down complex tasks with tool hints."""

    complex_request: str = dspy.InputField(desc="A complex task that needs breakdown")
    subtasks_with_tools: str = dspy.OutputField(
        desc="JSON array of {task, tools, priority} objects"
    )
    total_tool_calls: int = dspy.OutputField(desc="Estimated total number of tool calls")
    requires_todo: bool = dspy.OutputField(desc="Whether todo tool should be used")
    parallelization_opportunities: int = dspy.OutputField(
        desc="Number of parallel execution opportunities"
    )


class PathValidationSignature(dspy.Signature):
    """Validate and convert paths to relative format."""

    path: str = dspy.InputField(desc="Path to validate")
    current_directory: str = dspy.InputField(desc="Current working directory")
    is_valid: bool = dspy.OutputField(desc="Whether path is valid relative path")
    relative_path: str = dspy.OutputField(desc="Converted relative path")
    reason: str = dspy.OutputField(desc="Validation result explanation")


class OptimizedToolSelector(dspy.Module):
    """Tool selection with batching optimization"""

    def __init__(self):
        self.predict = dspy.ChainOfThought(ToolSelectionSignature)

    def forward(self, user_request: str, current_directory: str = "."):
        logger.debug(f"Tool Selection for: {user_request}")
        result = self.predict(user_request=user_request, current_directory=current_directory)

        # Parse and validate tool batches
        try:
            tool_batches = json.loads(result.tools_json)
            validated_batches = self._validate_batches(tool_batches)
            result.tool_batches = validated_batches
        except Exception as e:
            logger.error(f"Failed to parse tool batches: {e}")
            result.tool_batches = []

        return result

    def _validate_batches(self, batches: List[List[str]]) -> List[List[Dict]]:
        """Validate and optimize tool batches for 3-4 tool rule"""
        validated = []

        for batch in batches:
            # Check if batch contains only read-only tools
            all_read_only = all(
                any(tool_name in tool for tool_name in TOOL_CATEGORIES["read_only"])
                for tool in batch
            )

            # Optimize batch size (3-4 tools is optimal)
            if all_read_only and len(batch) > 4:
                # Split large batches
                for i in range(0, len(batch), 4):
                    sub_batch = batch[i : i + 4]
                    validated.append(self._parse_tools(sub_batch))
            else:
                validated_batch = self._parse_tools(batch)
                if validated_batch:
                    validated.append(validated_batch)

        return validated

    def _parse_tools(self, tools: List[str]) -> List[Dict]:
        """Parse tool strings into proper format"""
        parsed = []
        for tool_str in tools:
            # Extract tool name and args from string like "read_file('main.py')"
            match = re.match(r"(\w+)\((.*)\)", tool_str)
            if match:
                tool_name = match.group(1)
                args_str = match.group(2)

                tool_dict = {"tool": tool_name, "args": {}}
                if args_str:
                    # Handle simple cases like 'file.py' or "pattern", "dir"
                    args = [arg.strip().strip("\"'") for arg in args_str.split(",")]
                    if tool_name == "read_file":
                        tool_dict["args"]["filepath"] = args[0]
                    elif tool_name == "grep":
                        tool_dict["args"]["pattern"] = args[0]
                        if len(args) > 1:
                            tool_dict["args"]["directory"] = args[1]
                    elif tool_name == "list_dir":
                        tool_dict["args"]["directory"] = args[0] if args else "."
                    elif tool_name == "glob":
                        tool_dict["args"]["pattern"] = args[0]
                        if len(args) > 1:
                            tool_dict["args"]["directory"] = args[1]
                    elif tool_name == "todo":
                        tool_dict["args"]["action"] = args[0] if args else "list"
                    elif tool_name in ["write_file", "update_file"]:
                        if args:
                            tool_dict["args"]["filepath"] = args[0]
                    elif tool_name in ["run_command", "bash"]:
                        if args:
                            tool_dict["args"]["command"] = args[0]

                parsed.append(tool_dict)

        return parsed


class EnhancedTaskPlanner(dspy.Module):
    """Task planning with tool awareness"""

    def __init__(self):
        self.predict = dspy.ChainOfThought(TaskPlanningSignature)

    def forward(self, complex_request: str):
        logger.debug(f"Task Planning for: {complex_request}")
        result = self.predict(complex_request=complex_request)

        # Parse subtasks
        try:
            result.subtasks = json.loads(result.subtasks_with_tools)
        except Exception as e:
            logger.error(f"Failed to parse subtasks: {e}")
            result.subtasks = []

        return result


class PathValidator(dspy.Module):
    """Ensure all paths are relative"""

    def __init__(self):
        self.predict = dspy.Predict(PathValidationSignature)

    def forward(self, path: str, current_directory: str = "."):
        return self.predict(path=path, current_directory=current_directory)


class TunaCodeDSPy(dspy.Module):
    """Main TunaCode DSPy agent"""

    def __init__(self):
        self.tool_selector = OptimizedToolSelector()
        self.task_planner = EnhancedTaskPlanner()
        self.path_validator = PathValidator()

    def forward(self, user_request: str, current_directory: str = "."):
        """Process request with optimization"""

        # Detect request complexity
        is_complex = self._is_complex_task(user_request)

        result = {
            "request": user_request,
            "is_complex": is_complex,
            "current_directory": current_directory,
        }

        if is_complex:
            # Use task planner for complex tasks
            task_plan = self.task_planner(complex_request=user_request)
            result["subtasks"] = task_plan.subtasks
            result["total_tool_calls"] = task_plan.total_tool_calls
            result["requires_todo"] = task_plan.requires_todo
            result["parallelization_opportunities"] = task_plan.parallelization_opportunities

            if task_plan.requires_todo:
                result["initial_action"] = "Use todo tool to create task list"
        else:
            # Direct tool selection with batching
            tool_selection = self.tool_selector(
                user_request=user_request, current_directory=current_directory
            )
            result["tool_batches"] = tool_selection.tool_batches
            result["requires_confirmation"] = tool_selection.requires_confirmation
            result["reasoning"] = tool_selection.reasoning

        return result

    def _is_complex_task(self, request: str) -> bool:
        """Detect if task is complex based on keywords and patterns"""
        complex_indicators = [
            "implement",
            "create",
            "build",
            "refactor",
            "add feature",
            "fix all",
            "update multiple",
            "migrate",
            "integrate",
            "debug",
            "optimize performance",
            "add authentication",
            "setup",
            "configure",
            "test suite",
        ]

        request_lower = request.lower()

        # Check for multiple files mentioned
        file_pattern = r"\b\w+\.\w+\b"
        files_mentioned = len(re.findall(file_pattern, request)) > 2

        # Check for complex keywords
        has_complex_keyword = any(indicator in request_lower for indicator in complex_indicators)

        # Check for multiple operations
        operation_words = ["and", "then", "also", "after", "before", "plus"]
        has_multiple_ops = sum(1 for word in operation_words if word in request_lower) >= 2

        return files_mentioned or has_complex_keyword or has_multiple_ops

    def validate_path(self, path: str, current_directory: str = ".") -> Dict:
        """Validate a path is relative and safe"""
        return self.path_validator(path, current_directory)


def get_tool_selection_examples():
    """Training examples for tool selection"""
    return [
        dspy.Example(
            user_request="Show me the authentication system implementation",
            current_directory=".",
            tools_json='[["grep(\\"auth\\", \\"src/\\")", "list_dir(\\"src/auth/\\")", "glob(\\"**/*auth*.py\\")"]]',
            requires_confirmation=False,
            reasoning="Batch 3 read-only tools for parallel search - optimal performance",
        ).with_inputs("user_request", "current_directory"),
        dspy.Example(
            user_request="Read all config files and the main module",
            current_directory=".",
            tools_json='[["read_file(\\"config.json\\")", "read_file(\\"settings.py\\")", "read_file(\\".env\\")", "read_file(\\"main.py\\")"]]',
            requires_confirmation=False,
            reasoning="Batch 4 file reads together - maximum optimal batch size",
        ).with_inputs("user_request", "current_directory"),
        dspy.Example(
            user_request="Find the bug in validation and fix it",
            current_directory=".",
            tools_json='[["grep(\\"error\\", \\"logs/\\")", "grep(\\"validation\\", \\"src/\\")", "list_dir(\\"src/validators/\\")"], ["read_file(\\"src/validators/user.py\\")"], ["update_file(\\"src/validators/user.py\\", \\"old\\", \\"new\\")"]]',
            requires_confirmation=True,
            reasoning="Search tools batched, then read, then sequential write operation",
        ).with_inputs("user_request", "current_directory"),
    ]


def get_task_planning_examples():
    """Training examples for task planning"""
    return [
        dspy.Example(
            complex_request="Implement user authentication system with JWT tokens",
            subtasks_with_tools='[{"task": "Analyze current app structure", "tools": ["list_dir", "grep", "read_file"], "priority": "high"}, {"task": "Design user model", "tools": ["write_file"], "priority": "high"}, {"task": "Create auth endpoints", "tools": ["write_file", "update_file"], "priority": "high"}, {"task": "Add JWT tokens", "tools": ["write_file", "grep"], "priority": "high"}, {"task": "Write tests", "tools": ["write_file", "run_command"], "priority": "medium"}]',
            total_tool_calls=15,
            requires_todo=True,
            parallelization_opportunities=3,
        ).with_inputs("complex_request"),
    ]


def tool_selection_metric(example, prediction):
    """Metric for tool selection evaluation"""
    score = 0.0

    # Tool accuracy (40%)
    if hasattr(prediction, "tool_batches") and hasattr(example, "tools_json"):
        try:
            expected = json.loads(example.tools_json)
            predicted = prediction.tool_batches

            # Check tool selection accuracy
            expected_tools = set()
            predicted_tools = set()

            for batch in expected:
                for tool in batch:
                    tool_name = re.match(r"(\w+)\(", tool)
                    if tool_name:
                        expected_tools.add(tool_name.group(1))

            for batch in predicted:
                for tool in batch:
                    if isinstance(tool, dict):
                        predicted_tools.add(tool.get("tool", ""))

            if expected_tools == predicted_tools:
                score += 0.4
            else:
                overlap = len(expected_tools & predicted_tools)
                total = len(expected_tools | predicted_tools)
                if total > 0:
                    score += 0.4 * (overlap / total)
        except Exception:
            pass

    # Batching optimization (30%)
    if hasattr(prediction, "tool_batches"):
        batches = prediction.tool_batches
        optimal_batching = True

        for batch in batches:
            if len(batch) > 0:
                batch_tools = [tool.get("tool", "") for tool in batch if isinstance(tool, dict)]
                if all(tool in TOOL_CATEGORIES["read_only"] for tool in batch_tools):
                    if len(batch) < 3 or len(batch) > 4:
                        optimal_batching = False
                        break

        if optimal_batching:
            score += 0.3

    # Confirmation accuracy (20%)
    if hasattr(prediction, "requires_confirmation") and hasattr(example, "requires_confirmation"):
        if prediction.requires_confirmation == example.requires_confirmation:
            score += 0.2

    # Reasoning quality (10%)
    if hasattr(prediction, "reasoning") and prediction.reasoning and len(prediction.reasoning) > 20:
        score += 0.1

    return score


def task_planning_metric(example, prediction):
    """Metric for task planning evaluation"""
    score = 0.0

    # Subtask quality (30%)
    if hasattr(prediction, "subtasks") and hasattr(example, "subtasks_with_tools"):
        try:
            expected = json.loads(example.subtasks_with_tools)
            predicted = prediction.subtasks

            if abs(len(expected) - len(predicted)) <= 1:
                score += 0.3
            elif abs(len(expected) - len(predicted)) <= 2:
                score += 0.15
        except Exception:
            pass

    # Tool estimation accuracy (30%)
    if hasattr(prediction, "total_tool_calls") and hasattr(example, "total_tool_calls"):
        if abs(prediction.total_tool_calls - example.total_tool_calls) <= 5:
            score += 0.3
        elif abs(prediction.total_tool_calls - example.total_tool_calls) <= 10:
            score += 0.15

    # Todo requirement (20%)
    if hasattr(prediction, "requires_todo") and hasattr(example, "requires_todo"):
        if prediction.requires_todo == example.requires_todo:
            score += 0.2

    # Parallelization awareness (20%)
    if hasattr(prediction, "parallelization_opportunities") and hasattr(
        example, "parallelization_opportunities"
    ):
        if (
            abs(prediction.parallelization_opportunities - example.parallelization_opportunities)
            <= 2
        ):
            score += 0.2

    return score


def create_optimized_agent(api_key: str = None, model: str = "openrouter/openai/gpt-4.1-mini"):
    """Create and optimize the TunaCode DSPy agent"""

    # Configure DSPy
    if not api_key:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("Please set OPENROUTER_API_KEY environment variable")

    lm = dspy.LM(
        model,
        api_base="https://openrouter.ai/api/v1",
        api_key=api_key,
        temperature=0.3,
    )
    dspy.configure(lm=lm)

    # Create agent
    agent = TunaCodeDSPy()

    # Optimize tool selector
    tool_examples = get_tool_selection_examples()
    tool_optimizer = dspy.BootstrapFewShot(
        metric=lambda ex, pred, _trace: tool_selection_metric(ex, pred),
        max_bootstrapped_demos=3,
    )
    agent.tool_selector = tool_optimizer.compile(agent.tool_selector, trainset=tool_examples)

    # Optimize task planner
    task_examples = get_task_planning_examples()
    task_optimizer = dspy.BootstrapFewShot(
        metric=lambda ex, pred, _trace: task_planning_metric(ex, pred),
        max_bootstrapped_demos=2,
    )
    agent.task_planner = task_optimizer.compile(agent.task_planner, trainset=task_examples)

    return agent


agent = create_optimized_agent()
result = agent("Show me the authentication implementation", ".")
