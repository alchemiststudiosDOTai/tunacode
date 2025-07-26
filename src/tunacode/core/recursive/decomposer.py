"""Module: tunacode.core.recursive.decomposer

Task decomposition engine that uses the main agent for intelligent task analysis and breakdown.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from tunacode.core.state import StateManager

logger = logging.getLogger(__name__)


class SubtaskDefinition(BaseModel):
    """Definition of a single subtask."""

    title: str
    description: str
    dependencies: List[int] = Field(default_factory=list)
    estimated_complexity: float = Field(ge=0.0, le=1.0)
    estimated_iterations: int = Field(ge=1)


class DecompositionResult(BaseModel):
    """Result of task decomposition analysis."""

    should_decompose: bool
    reasoning: str
    subtasks: List[SubtaskDefinition] = Field(default_factory=list)
    total_complexity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class TaskDecomposer:
    """Intelligent task decomposition using the main agent."""

    def __init__(self, state_manager: StateManager):
        """Initialize the TaskDecomposer.

        Args:
            state_manager: StateManager instance for accessing the main agent
        """
        self.state_manager = state_manager
        self._decomposition_cache: Dict[str, DecompositionResult] = {}

    async def analyze_and_decompose(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
        max_subtasks: int = 5,
        min_subtasks: int = 2,
    ) -> DecompositionResult:
        """Analyze a task and decompose it if necessary.

        Args:
            task_description: Description of the task to analyze
            context: Optional context about the task
            max_subtasks: Maximum number of subtasks to generate
            min_subtasks: Minimum number of subtasks to generate

        Returns:
            DecompositionResult with analysis and potential subtasks
        """
        # Check cache first
        cache_key = f"{task_description}:{max_subtasks}:{min_subtasks}"
        if cache_key in self._decomposition_cache:
            logger.debug("Using cached decomposition result")
            return self._decomposition_cache[cache_key]

        # Get the main agent
        agent = self.state_manager.session.agents.get("main")
        if not agent:
            logger.warning("Main agent not available, using heuristic decomposition")
            return self._heuristic_decomposition(task_description)

        # Build context-aware prompt
        context_str = ""
        if context:
            context_str = f"\n\nAdditional context:\n{json.dumps(context, indent=2)}"

        decomposition_prompt = f"""Analyze this task and determine if it should be broken down into subtasks.

Task: {task_description}{context_str}

Consider:
1. Is this task complex enough to benefit from decomposition?
2. Can it be logically broken into {min_subtasks}-{max_subtasks} independent subtasks?
3. Would decomposition improve clarity and execution?

Provide a detailed analysis in the following JSON format:
{{
    "should_decompose": true/false,
    "reasoning": "Detailed explanation of your decision",
    "total_complexity": 0.0-1.0,
    "confidence": 0.0-1.0,
    "subtasks": [
        {{
            "title": "Short descriptive title",
            "description": "Detailed description of what this subtask accomplishes",
            "dependencies": [indices of other subtasks this depends on],
            "estimated_complexity": 0.0-1.0,
            "estimated_iterations": 1-20
        }}
    ]
}}

Guidelines for subtasks:
- Each subtask should be self-contained and testable
- Dependencies should form a valid DAG (no cycles)
- Complexity estimates: 0.0=trivial, 0.5=moderate, 1.0=very complex
- Iteration estimates: rough number of agent turns needed

Only include subtasks if should_decompose is true."""

        try:
            # Run the agent
            result = await agent.run(decomposition_prompt)

            # Parse the response
            decomposition = self._parse_agent_response(result, task_description)

            # Validate and cache
            decomposition = self._validate_decomposition(decomposition)
            self._decomposition_cache[cache_key] = decomposition

            return decomposition

        except Exception as e:
            logger.error(f"Error in task decomposition: {str(e)}")
            return self._heuristic_decomposition(task_description)

    def _parse_agent_response(self, response: Any, original_task: str) -> DecompositionResult:
        """Parse the agent's response into a DecompositionResult.

        Args:
            response: Raw response from the agent
            original_task: Original task description for fallback

        Returns:
            Parsed DecompositionResult
        """
        try:
            # Extract JSON from response
            response_text = str(response)

            # Find JSON in response (handle markdown code blocks)
            import re

            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(0)
                else:
                    raise ValueError("No JSON found in response")

            # Parse JSON
            data = json.loads(json_text)

            # Convert to DecompositionResult
            subtasks = []
            for subtask_data in data.get("subtasks", []):
                subtasks.append(
                    SubtaskDefinition(
                        title=subtask_data.get("title", "Untitled"),
                        description=subtask_data.get("description", ""),
                        dependencies=subtask_data.get("dependencies", []),
                        estimated_complexity=float(subtask_data.get("estimated_complexity", 0.5)),
                        estimated_iterations=int(subtask_data.get("estimated_iterations", 5)),
                    )
                )

            return DecompositionResult(
                should_decompose=bool(data.get("should_decompose", False)),
                reasoning=data.get("reasoning", "No reasoning provided"),
                subtasks=subtasks,
                total_complexity=float(data.get("total_complexity", 0.5)),
                confidence=float(data.get("confidence", 0.7)),
            )

        except Exception as e:
            logger.error(f"Error parsing agent response: {str(e)}")
            # Fallback to simple decomposition
            return DecompositionResult(
                should_decompose=True,
                reasoning="Failed to parse agent response, using default decomposition",
                subtasks=[
                    SubtaskDefinition(
                        title=f"Analyze requirements for: {original_task[:50]}",
                        description="Analyze and understand the requirements",
                        estimated_complexity=0.3,
                        estimated_iterations=3,
                    ),
                    SubtaskDefinition(
                        title=f"Implement: {original_task[:50]}",
                        description="Implement the core functionality",
                        dependencies=[0],
                        estimated_complexity=0.7,
                        estimated_iterations=10,
                    ),
                    SubtaskDefinition(
                        title=f"Test and validate: {original_task[:50]}",
                        description="Test and validate the implementation",
                        dependencies=[1],
                        estimated_complexity=0.4,
                        estimated_iterations=5,
                    ),
                ],
                total_complexity=0.7,
                confidence=0.3,
            )

    def _heuristic_decomposition(self, task_description: str) -> DecompositionResult:
        """Simple heuristic decomposition when agent is not available.

        Args:
            task_description: Task to decompose

        Returns:
            Simple DecompositionResult based on heuristics
        """
        # Simple heuristics
        word_count = len(task_description.split())
        has_multiple_verbs = (
            sum(
                1
                for word in ["and", "then", "also", "with", "plus"]
                if word in task_description.lower()
            )
            >= 2
        )

        complexity = min(1.0, (word_count / 30) * 0.5 + (0.3 if has_multiple_verbs else 0))
        should_decompose = complexity >= 0.6 and word_count > 20

        if should_decompose:
            return DecompositionResult(
                should_decompose=True,
                reasoning="Task appears complex based on length and structure",
                subtasks=[
                    SubtaskDefinition(
                        title="Prepare and analyze",
                        description=f"Prepare and analyze requirements for: {task_description[:100]}",
                        estimated_complexity=0.3,
                        estimated_iterations=3,
                    ),
                    SubtaskDefinition(
                        title="Core implementation",
                        description=f"Implement main functionality for: {task_description[:100]}",
                        dependencies=[0],
                        estimated_complexity=0.6,
                        estimated_iterations=8,
                    ),
                    SubtaskDefinition(
                        title="Finalize and verify",
                        description=f"Complete and verify: {task_description[:100]}",
                        dependencies=[1],
                        estimated_complexity=0.3,
                        estimated_iterations=4,
                    ),
                ],
                total_complexity=complexity,
                confidence=0.4,
            )
        else:
            return DecompositionResult(
                should_decompose=False,
                reasoning="Task is simple enough to execute directly",
                subtasks=[],
                total_complexity=complexity,
                confidence=0.6,
            )

    def _validate_decomposition(self, decomposition: DecompositionResult) -> DecompositionResult:
        """Validate and fix common issues in decomposition.

        Args:
            decomposition: Decomposition to validate

        Returns:
            Validated and potentially fixed decomposition
        """
        if not decomposition.should_decompose:
            # Clear subtasks if we shouldn't decompose
            decomposition.subtasks = []
            return decomposition

        # Validate dependencies form a DAG
        if decomposition.subtasks:
            n = len(decomposition.subtasks)

            # Fix out-of-range dependencies
            for i, subtask in enumerate(decomposition.subtasks):
                subtask.dependencies = [
                    dep for dep in subtask.dependencies if 0 <= dep < n and dep != i
                ]

            # Check for cycles using DFS
            def has_cycle(adj_list: Dict[int, List[int]]) -> bool:
                visited = [False] * n
                rec_stack = [False] * n

                def dfs(node: int) -> bool:
                    visited[node] = True
                    rec_stack[node] = True

                    for neighbor in adj_list.get(node, []):
                        if not visited[neighbor]:
                            if dfs(neighbor):
                                return True
                        elif rec_stack[neighbor]:
                            return True

                    rec_stack[node] = False
                    return False

                for i in range(n):
                    if not visited[i]:
                        if dfs(i):
                            return True
                return False

            # Build adjacency list
            adj_list = {}
            for i, subtask in enumerate(decomposition.subtasks):
                for dep in subtask.dependencies:
                    if dep not in adj_list:
                        adj_list[dep] = []
                    adj_list[dep].append(i)

            # Remove cycles if found
            if has_cycle(adj_list):
                logger.warning("Cycle detected in dependencies, removing all dependencies")
                for subtask in decomposition.subtasks:
                    subtask.dependencies = []
                decomposition.reasoning += " (Note: Circular dependencies were removed)"

        return decomposition

    def get_subtask_order(self, subtasks: List[SubtaskDefinition]) -> List[int]:
        """Get the execution order for subtasks based on dependencies.

        Args:
            subtasks: List of subtasks with dependencies

        Returns:
            List of indices in execution order
        """
        if not subtasks:
            return []

        n = len(subtasks)
        in_degree = [0] * n
        adj_list = {i: [] for i in range(n)}

        # Build graph
        for i, subtask in enumerate(subtasks):
            for dep in subtask.dependencies:
                adj_list[dep].append(i)
                in_degree[i] += 1

        # Topological sort using Kahn's algorithm
        queue = [i for i in range(n) if in_degree[i] == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)

            for neighbor in adj_list[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If we couldn't process all nodes, there's a cycle (shouldn't happen after validation)
        if len(order) != n:
            logger.error("Dependency cycle detected during ordering")
            # Return simple linear order as fallback
            return list(range(n))

        return order

    def estimate_total_iterations(self, subtasks: List[SubtaskDefinition]) -> int:
        """Estimate total iterations needed for all subtasks.

        Args:
            subtasks: List of subtasks

        Returns:
            Total estimated iterations
        """
        return sum(subtask.estimated_iterations for subtask in subtasks)
