"""Module: tunacode.core.recursive.aggregator

Result aggregation and context management for recursive task execution.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from tunacode.core.state import StateManager

logger = logging.getLogger(__name__)


class AggregationStrategy(Enum):
    """Strategies for aggregating results."""

    CONCATENATE = "concatenate"  # Simple concatenation
    STRUCTURED = "structured"  # Preserve task structure
    SUMMARY = "summary"  # Generate summary
    INTELLIGENT = "intelligent"  # Use agent to merge


class ConflictResolution(Enum):
    """Strategies for resolving conflicts in results."""

    LATEST = "latest"  # Use most recent result
    PRIORITY = "priority"  # Use highest priority result
    MERGE = "merge"  # Attempt to merge
    AGENT = "agent"  # Use agent to resolve


@dataclass
class TaskResult:
    """Result from a single task execution."""

    task_id: str
    task_title: str
    result_data: Any
    status: str  # completed, failed, partial
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedResult:
    """Aggregated result from multiple tasks."""

    primary_result: Any
    task_results: List[TaskResult]
    strategy_used: AggregationStrategy
    conflicts_resolved: int = 0
    partial_failures: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    aggregation_time: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionContext:
    """Context information during execution."""

    task_id: str
    parent_context: Dict[str, Any]
    local_context: Dict[str, Any]
    files_accessed: Set[str] = field(default_factory=set)
    tools_used: List[str] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)


class ResultAggregator:
    """Aggregates results from distributed subtask executions."""

    def __init__(self, state_manager: StateManager):
        """Initialize the ResultAggregator.

        Args:
            state_manager: StateManager for accessing agents
        """
        self.state_manager = state_manager
        self._context_cache: Dict[str, ExecutionContext] = {}

    async def aggregate_results(
        self,
        task_results: List[TaskResult],
        parent_task: Optional[Dict[str, Any]] = None,
        strategy: AggregationStrategy = AggregationStrategy.INTELLIGENT,
    ) -> AggregatedResult:
        """Aggregate results from multiple subtasks.

        Args:
            task_results: List of results from subtasks
            parent_task: Optional parent task information
            strategy: Aggregation strategy to use

        Returns:
            AggregatedResult with merged data
        """
        if not task_results:
            return AggregatedResult(
                primary_result="No results to aggregate", task_results=[], strategy_used=strategy
            )

        # Separate successful and failed results
        successful_results = [r for r in task_results if r.status == "completed"]
        failed_results = [r for r in task_results if r.status == "failed"]
        partial_results = [r for r in task_results if r.status == "partial"]

        # Handle complete failure
        if not successful_results and not partial_results:
            return AggregatedResult(
                primary_result="All subtasks failed",
                task_results=task_results,
                strategy_used=strategy,
                partial_failures=[r.task_id for r in failed_results],
            )

        # Apply aggregation strategy
        if strategy == AggregationStrategy.CONCATENATE:
            result = await self._aggregate_concatenate(successful_results + partial_results)
        elif strategy == AggregationStrategy.STRUCTURED:
            result = await self._aggregate_structured(
                successful_results + partial_results, parent_task
            )
        elif strategy == AggregationStrategy.SUMMARY:
            result = await self._aggregate_summary(
                successful_results + partial_results, parent_task
            )
        elif strategy == AggregationStrategy.INTELLIGENT:
            result = await self._aggregate_intelligent(
                successful_results + partial_results, parent_task
            )
        else:
            result = await self._aggregate_concatenate(successful_results + partial_results)

        return AggregatedResult(
            primary_result=result,
            task_results=task_results,
            strategy_used=strategy,
            partial_failures=[r.task_id for r in failed_results],
        )

    async def _aggregate_concatenate(self, results: List[TaskResult]) -> str:
        """Simple concatenation of results.

        Args:
            results: List of successful results

        Returns:
            Concatenated string result
        """
        parts = []
        for i, result in enumerate(results):
            parts.append(f"=== Task {i + 1}: {result.task_title} ===")
            parts.append(str(result.result_data))
            parts.append("")

        return "\n".join(parts)

    async def _aggregate_structured(
        self, results: List[TaskResult], parent_task: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create structured aggregation preserving task relationships.

        Args:
            results: List of successful results
            parent_task: Parent task information

        Returns:
            Structured dictionary result
        """
        structured_result = {
            "parent_task": parent_task.get("title") if parent_task else "Unknown",
            "completed_subtasks": len([r for r in results if r.status == "completed"]),
            "partial_subtasks": len([r for r in results if r.status == "partial"]),
            "subtask_results": [],
        }

        for result in results:
            structured_result["subtask_results"].append(
                {
                    "task_id": result.task_id,
                    "title": result.task_title,
                    "status": result.status,
                    "result": result.result_data,
                    "timestamp": result.timestamp.isoformat(),
                }
            )

        return structured_result

    async def _aggregate_summary(
        self, results: List[TaskResult], parent_task: Optional[Dict[str, Any]]
    ) -> str:
        """Generate a summary of results.

        Args:
            results: List of successful results
            parent_task: Parent task information

        Returns:
            Summary string
        """
        summary_parts = []

        if parent_task:
            summary_parts.append(f"Summary for: {parent_task.get('title', 'Unknown Task')}")
            summary_parts.append("")

        summary_parts.append(f"Completed {len(results)} subtasks:")
        summary_parts.append("")

        for i, result in enumerate(results):
            # Extract key information from result
            result_str = str(result.result_data)
            preview = result_str[:200] + "..." if len(result_str) > 200 else result_str

            summary_parts.append(f"{i + 1}. {result.task_title}")
            summary_parts.append(f"   Status: {result.status}")
            summary_parts.append(f"   Result: {preview}")
            summary_parts.append("")

        return "\n".join(summary_parts)

    async def _aggregate_intelligent(
        self, results: List[TaskResult], parent_task: Optional[Dict[str, Any]]
    ) -> Any:
        """Use agent to intelligently merge results.

        Args:
            results: List of successful results
            parent_task: Parent task information

        Returns:
            Intelligently merged result
        """
        agent = self.state_manager.session.agents.get("main")
        if not agent:
            # Fallback to summary
            return await self._aggregate_summary(results, parent_task)

        # Prepare context for agent
        context = {
            "parent_task": parent_task.get("description") if parent_task else "Unknown",
            "subtask_count": len(results),
            "subtask_results": [],
        }

        for result in results:
            context["subtask_results"].append(
                {
                    "title": result.task_title,
                    "result": str(result.result_data)[:500],  # Limit size
                }
            )

        merge_prompt = f"""Intelligently merge and synthesize these subtask results into a coherent response.

Parent Task: {context["parent_task"]}

Subtask Results:
{json.dumps(context["subtask_results"], indent=2)}

Instructions:
1. Identify the key achievements from each subtask
2. Synthesize findings into a unified response
3. Highlight any important patterns or insights
4. Present the result in a clear, actionable format

Provide a comprehensive but concise synthesis that addresses the original task."""

        try:
            result = await agent.run(merge_prompt)
            return result
        except Exception as e:
            logger.error(f"Agent-based aggregation failed: {str(e)}")
            # Fallback to summary
            return await self._aggregate_summary(results, parent_task)

    def create_context(
        self, task_id: str, parent_context: Optional[Dict[str, Any]] = None
    ) -> ExecutionContext:
        """Create an execution context for a task.

        Args:
            task_id: Task identifier
            parent_context: Optional parent context to inherit

        Returns:
            New execution context
        """
        context = ExecutionContext(
            task_id=task_id, parent_context=parent_context or {}, local_context={}
        )

        self._context_cache[task_id] = context
        return context

    def get_context(self, task_id: str) -> Optional[ExecutionContext]:
        """Get execution context for a task.

        Args:
            task_id: Task identifier

        Returns:
            Execution context or None
        """
        return self._context_cache.get(task_id)

    def update_context(
        self,
        task_id: str,
        updates: Dict[str, Any],
        files: Optional[Set[str]] = None,
        tools: Optional[List[str]] = None,
        findings: Optional[List[str]] = None,
    ) -> None:
        """Update execution context for a task.

        Args:
            task_id: Task identifier
            updates: Context updates
            files: Files accessed
            tools: Tools used
            findings: Key findings
        """
        context = self._context_cache.get(task_id)
        if not context:
            logger.warning(f"No context found for task {task_id}")
            return

        context.local_context.update(updates)

        if files:
            context.files_accessed.update(files)
        if tools:
            context.tools_used.extend(tools)
        if findings:
            context.key_findings.extend(findings)

    def synthesize_contexts(self, task_ids: List[str]) -> Dict[str, Any]:
        """Synthesize contexts from multiple tasks.

        Args:
            task_ids: List of task IDs

        Returns:
            Synthesized context dictionary
        """
        synthesized = {
            "files_accessed": set(),
            "tools_used": [],
            "key_findings": [],
            "combined_context": {},
        }

        for task_id in task_ids:
            context = self._context_cache.get(task_id)
            if context:
                synthesized["files_accessed"].update(context.files_accessed)
                synthesized["tools_used"].extend(context.tools_used)
                synthesized["key_findings"].extend(context.key_findings)
                synthesized["combined_context"].update(context.local_context)

        # Convert set to list for JSON serialization
        synthesized["files_accessed"] = list(synthesized["files_accessed"])

        # Remove duplicates from tools while preserving order
        seen = set()
        unique_tools = []
        for tool in synthesized["tools_used"]:
            if tool not in seen:
                seen.add(tool)
                unique_tools.append(tool)
        synthesized["tools_used"] = unique_tools

        return synthesized

    async def resolve_conflicts(
        self,
        conflicting_results: List[TaskResult],
        strategy: ConflictResolution = ConflictResolution.AGENT,
    ) -> TaskResult:
        """Resolve conflicts between contradictory results.

        Args:
            conflicting_results: List of conflicting results
            strategy: Resolution strategy

        Returns:
            Single resolved result
        """
        if not conflicting_results:
            raise ValueError("No results to resolve conflicts for")

        if len(conflicting_results) == 1:
            return conflicting_results[0]

        if strategy == ConflictResolution.LATEST:
            # Return most recent result
            return max(conflicting_results, key=lambda r: r.timestamp)

        elif strategy == ConflictResolution.PRIORITY:
            # Use metadata priority if available
            def get_priority(result: TaskResult) -> int:
                return result.metadata.get("priority", 0)

            return max(conflicting_results, key=get_priority)

        elif strategy == ConflictResolution.MERGE:
            # Simple merge attempt
            merged_data = {}
            for result in conflicting_results:
                if isinstance(result.result_data, dict):
                    merged_data.update(result.result_data)
                else:
                    # Can't merge non-dict results
                    return conflicting_results[-1]

            return TaskResult(
                task_id="merged",
                task_title="Merged Result",
                result_data=merged_data,
                status="completed",
            )

        elif strategy == ConflictResolution.AGENT:
            # Use agent to resolve
            agent = self.state_manager.session.agents.get("main")
            if not agent:
                # Fallback to latest
                return max(conflicting_results, key=lambda r: r.timestamp)

            conflict_data = []
            for result in conflicting_results:
                conflict_data.append(
                    {
                        "task": result.task_title,
                        "result": str(result.result_data)[:300],
                        "timestamp": result.timestamp.isoformat(),
                    }
                )

            resolution_prompt = f"""Resolve conflicts between these task results:

{json.dumps(conflict_data, indent=2)}

Analyze the differences and provide a single, coherent result that best represents the correct outcome."""

            try:
                resolved = await agent.run(resolution_prompt)
                return TaskResult(
                    task_id="resolved",
                    task_title="Conflict Resolved",
                    result_data=resolved,
                    status="completed",
                )
            except Exception as e:
                logger.error(f"Agent conflict resolution failed: {str(e)}")
                # Fallback to latest
                return max(conflicting_results, key=lambda r: r.timestamp)

        # Default to latest
        return max(conflicting_results, key=lambda r: r.timestamp)
