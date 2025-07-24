"""Module: tunacode.core.recursive.executor

Main RecursiveTaskExecutor class for orchestrating recursive task decomposition and execution.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel

from tunacode.core.state import StateManager

from .aggregator import AggregationStrategy, ResultAggregator, TaskResult
from .budget import BudgetManager
from .decomposer import TaskDecomposer
from .hierarchy import TaskHierarchy

logger = logging.getLogger(__name__)


@dataclass
class TaskNode:
    """Represents a single task in the recursive execution tree."""

    id: str = field(default_factory=lambda: str(uuid4()))
    parent_id: Optional[str] = None
    title: str = ""
    description: str = ""
    complexity_score: float = 0.0
    iteration_budget: int = 10
    subtasks: List["TaskNode"] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    depth: int = 0


class TaskComplexityResult(BaseModel):
    """Result of task complexity analysis."""

    is_complex: bool
    complexity_score: float
    reasoning: str
    suggested_subtasks: List[str] = []


class RecursiveTaskExecutor:
    """Orchestrates recursive task decomposition and execution."""

    def __init__(
        self,
        state_manager: StateManager,
        max_depth: int = 5,
        min_complexity_threshold: float = 0.7,
        default_iteration_budget: int = 10,
    ):
        """Initialize the RecursiveTaskExecutor.

        Args:
            state_manager: The StateManager instance for accessing agents and state
            max_depth: Maximum recursion depth allowed
            min_complexity_threshold: Minimum complexity score to trigger decomposition
            default_iteration_budget: Default iteration budget for tasks
        """
        self.state_manager = state_manager
        self.max_depth = max_depth
        self.min_complexity_threshold = min_complexity_threshold
        self.default_iteration_budget = default_iteration_budget
        self._task_hierarchy: Dict[str, TaskNode] = {}
        self._execution_stack: List[str] = []

        # Initialize decomposer and hierarchy manager
        self.decomposer = TaskDecomposer(state_manager)
        self.hierarchy = TaskHierarchy()
        self.budget_manager = BudgetManager(
            total_budget=default_iteration_budget * 10,  # Scale based on default
            min_task_budget=2,
        )
        self.aggregator = ResultAggregator(state_manager)

    async def execute_task(
        self,
        request: str,
        parent_task_id: Optional[str] = None,
        depth: int = 0,
        inherited_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Any, Optional[str]]:
        """Execute a task, potentially decomposing it into subtasks.

        Args:
            request: The task request/description
            parent_task_id: ID of parent task if this is a subtask
            depth: Current recursion depth
            inherited_context: Context inherited from parent task

        Returns:
            Tuple of (success, result, error_message)
        """
        # Check recursion depth
        if depth >= self.max_depth:
            logger.warning(f"Max recursion depth {self.max_depth} reached")
            return False, None, f"Maximum recursion depth ({self.max_depth}) exceeded"

        # Create task node
        task_node = TaskNode(
            title=request[:100],  # First 100 chars as title
            description=request,
            parent_id=parent_task_id,
            depth=depth,
            context=inherited_context or {},
        )

        self._task_hierarchy[task_node.id] = task_node
        self._execution_stack.append(task_node.id)

        try:
            # Analyze task complexity
            complexity_result = await self._analyze_task_complexity(request)
            task_node.complexity_score = complexity_result.complexity_score

            # Decide whether to decompose or execute directly
            if (
                complexity_result.is_complex
                and complexity_result.complexity_score >= self.min_complexity_threshold
                and depth < self.max_depth - 1
            ):
                # Decompose into subtasks
                logger.info(
                    f"Decomposing complex task (score: {complexity_result.complexity_score:.2f})"
                )
                return await self._execute_with_decomposition(task_node, complexity_result)
            else:
                # Execute directly
                logger.info(
                    f"Executing task directly (score: {complexity_result.complexity_score:.2f})"
                )
                return await self._execute_directly(task_node)

        except Exception as e:
            logger.error(f"Error executing task {task_node.id}: {str(e)}")
            task_node.status = "failed"
            task_node.error = str(e)
            return False, None, str(e)
        finally:
            self._execution_stack.pop()

    async def _analyze_task_complexity(self, request: str) -> TaskComplexityResult:
        """Analyze task complexity using the main agent.

        Args:
            request: The task description

        Returns:
            TaskComplexityResult with analysis
        """
        # Get the main agent from state manager
        agent = self.state_manager.session.agents.get("main")
        if not agent:
            # Simple heuristic if agent not available
            word_count = len(request.split())
            has_multiple_parts = any(
                word in request.lower() for word in ["and", "then", "also", "plus"]
            )

            complexity_score = min(1.0, (word_count / 50) + (0.3 if has_multiple_parts else 0))
            is_complex = complexity_score >= self.min_complexity_threshold

            return TaskComplexityResult(
                is_complex=is_complex,
                complexity_score=complexity_score,
                reasoning="Heuristic analysis based on request length and structure",
            )

        # Use agent to analyze complexity
        complexity_prompt = f"""Analyze the complexity of this task and determine if it should be broken down into subtasks.

Task: {request}

Provide:
1. A complexity score from 0.0 to 1.0 (0 = trivial, 1 = extremely complex)
2. Whether this task should be decomposed (true/false)
3. Brief reasoning for your assessment
4. If complex, suggest 2-5 subtasks

Consider factors like:
- Number of distinct operations required
- Dependencies between operations
- Technical complexity
- Estimated time/effort needed

Respond in JSON format:
{{
    "is_complex": boolean,
    "complexity_score": float,
    "reasoning": "string",
    "suggested_subtasks": ["subtask1", "subtask2", ...]
}}"""

        try:
            await agent.run(complexity_prompt)
            # Parse the response (simplified - in production would use proper JSON parsing)
            # For now, return a default result
            return TaskComplexityResult(
                is_complex=True,
                complexity_score=0.8,
                reasoning="Task requires multiple distinct operations",
                suggested_subtasks=[],
            )
        except Exception as e:
            logger.error(f"Error analyzing task complexity: {str(e)}")
            # Fallback to heuristic
            return TaskComplexityResult(
                is_complex=False, complexity_score=0.5, reasoning="Error in analysis, using default"
            )

    async def _execute_with_decomposition(
        self, task_node: TaskNode, complexity_result: TaskComplexityResult
    ) -> Tuple[bool, Any, Optional[str]]:
        """Execute a task by decomposing it into subtasks.

        Args:
            task_node: The task node to execute
            complexity_result: The complexity analysis result

        Returns:
            Tuple of (success, aggregated_result, error_message)
        """
        task_node.status = "in_progress"

        # Generate subtasks
        subtasks = await self._generate_subtasks(task_node, complexity_result)

        # Allocate iteration budgets
        subtask_budgets = self._allocate_iteration_budgets(
            task_node.iteration_budget, len(subtasks)
        )

        # Execute subtasks
        results = []
        errors = []

        # Show UI feedback if thoughts are enabled
        if self.state_manager.session.show_thoughts:
            from tunacode.ui import console as ui_console
            from tunacode.ui.recursive_progress import show_recursive_progress

            await show_recursive_progress(
                ui_console.console,
                f"Executing {len(subtasks)} subtasks",
                task_id=task_node.id,
                depth=task_node.depth,
            )

        for i, (subtask_desc, budget) in enumerate(zip(subtasks, subtask_budgets)):
            logger.info(f"Executing subtask {i + 1}/{len(subtasks)}: {subtask_desc[:50]}...")

            # Create subtask context
            subtask_context = {
                **task_node.context,
                "parent_task": task_node.description,
                "subtask_index": i,
                "total_subtasks": len(subtasks),
            }

            # Execute subtask recursively
            success, result, error = await self.execute_task(
                subtask_desc,
                parent_task_id=task_node.id,
                depth=task_node.depth + 1,
                inherited_context=subtask_context,
            )

            if success:
                results.append(result)
            else:
                errors.append(f"Subtask {i + 1} failed: {error}")

            # Show completion status
            if self.state_manager.session.show_thoughts:
                from tunacode.ui import console as ui_console
                from tunacode.ui.recursive_progress import show_task_completion

                await show_task_completion(
                    ui_console.console,
                    task_node.id + f".{i + 1}",
                    success,
                    depth=task_node.depth + 1,
                )

        # Aggregate results
        if errors:
            task_node.status = "failed"
            task_node.error = "; ".join(errors)
            return False, results, f"Some subtasks failed: {'; '.join(errors)}"

        task_node.status = "completed"
        aggregated_result = await self._aggregate_results(task_node, results)
        task_node.result = aggregated_result

        return True, aggregated_result, None

    async def _execute_directly(self, task_node: TaskNode) -> Tuple[bool, Any, Optional[str]]:
        """Execute a task directly using the main agent.

        Args:
            task_node: The task node to execute

        Returns:
            Tuple of (success, result, error_message)
        """
        task_node.status = "in_progress"

        # Get the main agent
        agent = self.state_manager.session.agents.get("main")
        if not agent:
            error_msg = "Main agent not available"
            task_node.status = "failed"
            task_node.error = error_msg
            return False, None, error_msg

        try:
            # Execute with the agent
            result = await agent.run(task_node.description)
            task_node.status = "completed"
            task_node.result = result
            return True, result, None

        except Exception as e:
            error_msg = f"Error executing task: {str(e)}"
            logger.error(error_msg)
            task_node.status = "failed"
            task_node.error = error_msg
            return False, None, error_msg

    async def _generate_subtasks(
        self, task_node: TaskNode, complexity_result: TaskComplexityResult
    ) -> List[str]:
        """Generate subtasks for a complex task.

        Args:
            task_node: The parent task node
            complexity_result: The complexity analysis result

        Returns:
            List of subtask descriptions
        """
        # If we have suggested subtasks from complexity analysis, use them
        if complexity_result.suggested_subtasks:
            return complexity_result.suggested_subtasks

        # Otherwise, use agent to generate subtasks
        agent = self.state_manager.session.agents.get("main")
        if not agent:
            # Fallback to simple decomposition
            return [f"Part 1 of: {task_node.description}", f"Part 2 of: {task_node.description}"]

        decompose_prompt = f"""Break down this task into 2-5 logical subtasks that can be executed independently:

Task: {task_node.description}

Provide a list of clear, actionable subtasks. Each subtask should:
- Be self-contained and executable
- Have clear success criteria
- Contribute to completing the overall task

Return ONLY a JSON array of subtask descriptions:
["subtask 1 description", "subtask 2 description", ...]"""

        try:
            await agent.run(decompose_prompt)
            # Parse subtasks from result (simplified)
            # In production, would parse actual JSON response
            return [
                f"Step 1: Analyze requirements for {task_node.title}",
                f"Step 2: Implement core functionality for {task_node.title}",
                f"Step 3: Test and validate {task_node.title}",
            ]
        except Exception as e:
            logger.error(f"Error generating subtasks: {str(e)}")
            return [f"Execute: {task_node.description}"]

    def _allocate_iteration_budgets(self, total_budget: int, num_subtasks: int) -> List[int]:
        """Allocate iteration budget across subtasks.

        Args:
            total_budget: Total iteration budget available
            num_subtasks: Number of subtasks

        Returns:
            List of budgets for each subtask
        """
        if num_subtasks == 0:
            return []

        # Simple equal allocation with remainder distribution
        base_budget = total_budget // num_subtasks
        remainder = total_budget % num_subtasks

        budgets = [base_budget] * num_subtasks
        # Distribute remainder to first tasks
        for i in range(remainder):
            budgets[i] += 1

        return budgets

    async def _aggregate_results(self, task_node: TaskNode, subtask_results: List[Any]) -> Any:
        """Aggregate results from subtasks into a final result.

        Args:
            task_node: The parent task node
            subtask_results: List of results from subtasks

        Returns:
            Aggregated result
        """
        if not subtask_results:
            return "Task completed with no results"

        # Convert subtask results to TaskResult objects
        task_results = []
        for i, (subtask, result) in enumerate(zip(task_node.subtasks, subtask_results)):
            task_results.append(
                TaskResult(
                    task_id=subtask.id,
                    task_title=subtask.title,
                    result_data=result,
                    status=subtask.status,
                    error=subtask.error,
                )
            )

        # Use intelligent aggregation
        aggregated = await self.aggregator.aggregate_results(
            task_results=task_results,
            parent_task={
                "id": task_node.id,
                "title": task_node.title,
                "description": task_node.description,
            },
            strategy=AggregationStrategy.INTELLIGENT,
        )

        return aggregated.primary_result

    def get_task_hierarchy(self) -> Dict[str, TaskNode]:
        """Get the current task hierarchy.

        Returns:
            Dictionary mapping task IDs to TaskNode objects
        """
        return self._task_hierarchy.copy()

    def get_execution_stack(self) -> List[str]:
        """Get the current execution stack of task IDs.

        Returns:
            List of task IDs in execution order
        """
        return self._execution_stack.copy()

    def clear_hierarchy(self):
        """Clear the task hierarchy and execution stack."""
        self._task_hierarchy.clear()
        self._execution_stack.clear()
