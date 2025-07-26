"""Module: tunacode.core.recursive.budget

Budget management system for allocating and tracking computational resources across recursive executions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AllocationStrategy(Enum):
    """Budget allocation strategies."""

    EQUAL = "equal"  # Equal distribution
    WEIGHTED = "weighted"  # Based on complexity scores
    ADAPTIVE = "adaptive"  # Adjusts based on consumption
    PRIORITY = "priority"  # Based on task priority


@dataclass
class BudgetAllocation:
    """Represents a budget allocation for a task."""

    task_id: str
    allocated_budget: int
    consumed_budget: int = 0
    remaining_budget: int = field(init=False)
    allocation_time: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self.remaining_budget = self.allocated_budget - self.consumed_budget

    def consume(self, amount: int) -> bool:
        """Consume budget and return if successful.

        Args:
            amount: Amount to consume

        Returns:
            True if budget was available and consumed
        """
        if amount <= self.remaining_budget:
            self.consumed_budget += amount
            self.remaining_budget -= amount
            self.last_update = datetime.now()
            return True
        return False

    def get_utilization_rate(self) -> float:
        """Get the budget utilization rate (0.0 to 1.0)."""
        if self.allocated_budget == 0:
            return 0.0
        return self.consumed_budget / self.allocated_budget


@dataclass
class BudgetSnapshot:
    """Snapshot of budget state at a point in time."""

    timestamp: datetime
    total_allocated: int
    total_consumed: int
    active_tasks: int
    task_allocations: Dict[str, BudgetAllocation]


class BudgetManager:
    """Manages iteration budget allocation and tracking across tasks."""

    def __init__(
        self, total_budget: int = 100, min_task_budget: int = 2, reallocation_threshold: float = 0.2
    ):
        """Initialize the BudgetManager.

        Args:
            total_budget: Total iteration budget available
            min_task_budget: Minimum budget to allocate to any task
            reallocation_threshold: Utilization threshold for reallocation
        """
        self.total_budget = total_budget
        self.min_task_budget = min_task_budget
        self.reallocation_threshold = reallocation_threshold

        self._allocations: Dict[str, BudgetAllocation] = {}
        self._available_budget = total_budget
        self._allocation_history: List[BudgetSnapshot] = []
        self._reallocation_count = 0

    def allocate_budget(
        self,
        task_ids: List[str],
        complexity_scores: Optional[List[float]] = None,
        priorities: Optional[List[str]] = None,
        strategy: AllocationStrategy = AllocationStrategy.WEIGHTED,
    ) -> Dict[str, int]:
        """Allocate budget to multiple tasks based on strategy.

        Args:
            task_ids: List of task IDs to allocate budget to
            complexity_scores: Optional complexity scores (0.0-1.0) for each task
            priorities: Optional priority levels for each task
            strategy: Allocation strategy to use

        Returns:
            Dictionary mapping task IDs to allocated budgets
        """
        if not task_ids:
            return {}

        n_tasks = len(task_ids)

        # Determine allocation based on strategy
        if strategy == AllocationStrategy.EQUAL:
            allocations = self._allocate_equal(n_tasks)
        elif strategy == AllocationStrategy.WEIGHTED and complexity_scores:
            allocations = self._allocate_weighted(complexity_scores)
        elif strategy == AllocationStrategy.PRIORITY and priorities:
            allocations = self._allocate_by_priority(priorities)
        else:
            # Fallback to equal allocation
            allocations = self._allocate_equal(n_tasks)

        # Apply allocations
        result = {}
        for task_id, budget in zip(task_ids, allocations):
            if budget > 0:
                self._allocations[task_id] = BudgetAllocation(
                    task_id=task_id, allocated_budget=budget
                )
                self._available_budget -= budget
                result[task_id] = budget
                logger.debug(f"Allocated {budget} iterations to task {task_id}")

        # Take snapshot
        self._take_snapshot()

        return result

    def consume_budget(self, task_id: str, amount: int = 1) -> bool:
        """Consume budget for a task.

        Args:
            task_id: Task ID
            amount: Amount to consume (default: 1)

        Returns:
            True if budget was available and consumed
        """
        if task_id not in self._allocations:
            logger.warning(f"No budget allocation found for task {task_id}")
            return False

        allocation = self._allocations[task_id]
        success = allocation.consume(amount)

        if not success:
            logger.warning(
                f"Insufficient budget for task {task_id}: "
                f"requested {amount}, available {allocation.remaining_budget}"
            )

        return success

    def get_remaining_budget(self, task_id: str) -> int:
        """Get remaining budget for a task.

        Args:
            task_id: Task ID

        Returns:
            Remaining budget or 0 if not found
        """
        if task_id in self._allocations:
            return self._allocations[task_id].remaining_budget
        return 0

    def get_utilization(self, task_id: Optional[str] = None) -> float:
        """Get budget utilization rate.

        Args:
            task_id: Optional task ID for specific utilization

        Returns:
            Utilization rate (0.0-1.0)
        """
        if task_id:
            if task_id in self._allocations:
                return self._allocations[task_id].get_utilization_rate()
            return 0.0

        # Overall utilization
        total_allocated = sum(a.allocated_budget for a in self._allocations.values())
        total_consumed = sum(a.consumed_budget for a in self._allocations.values())

        if total_allocated == 0:
            return 0.0
        return total_consumed / total_allocated

    def reallocate_unused_budget(self, force: bool = False) -> Dict[str, int]:
        """Reallocate unused budget from completed/failed tasks.

        Args:
            force: Force reallocation regardless of threshold

        Returns:
            Dictionary of new allocations made
        """
        # Find tasks with low utilization or completed tasks
        unused_budget = 0
        tasks_to_reclaim = []

        for task_id, allocation in self._allocations.items():
            utilization = allocation.get_utilization_rate()

            # Reclaim from tasks with very low utilization
            if utilization < self.reallocation_threshold or force:
                unused = allocation.remaining_budget
                if unused > 0:
                    tasks_to_reclaim.append((task_id, unused))
                    unused_budget += unused

        if unused_budget == 0:
            return {}

        # Find tasks that need more budget (high utilization)
        high_utilization_tasks = []
        for task_id, allocation in self._allocations.items():
            if task_id not in [t[0] for t in tasks_to_reclaim]:
                utilization = allocation.get_utilization_rate()
                if utilization > 0.8:  # High utilization threshold
                    high_utilization_tasks.append(task_id)

        if not high_utilization_tasks:
            # Return budget to available pool
            self._available_budget += unused_budget
            for task_id, amount in tasks_to_reclaim:
                self._allocations[task_id].allocated_budget -= amount
                self._allocations[task_id].remaining_budget = 0
            return {}

        # Reallocate to high utilization tasks
        per_task_addition = unused_budget // len(high_utilization_tasks)
        remainder = unused_budget % len(high_utilization_tasks)

        reallocations = {}
        for i, task_id in enumerate(high_utilization_tasks):
            additional = per_task_addition + (1 if i < remainder else 0)
            if additional > 0:
                self._allocations[task_id].allocated_budget += additional
                self._allocations[task_id].remaining_budget += additional
                reallocations[task_id] = additional

        # Update reclaimed tasks
        for task_id, amount in tasks_to_reclaim:
            self._allocations[task_id].allocated_budget -= amount
            self._allocations[task_id].remaining_budget = 0

        self._reallocation_count += 1
        logger.info(f"Reallocated {unused_budget} budget units to {len(reallocations)} tasks")

        return reallocations

    def release_task_budget(self, task_id: str) -> int:
        """Release all remaining budget for a task.

        Args:
            task_id: Task ID

        Returns:
            Amount of budget released
        """
        if task_id not in self._allocations:
            return 0

        allocation = self._allocations[task_id]
        released = allocation.remaining_budget

        if released > 0:
            self._available_budget += released
            allocation.remaining_budget = 0
            logger.debug(f"Released {released} budget units from task {task_id}")

        return released

    def _allocate_equal(self, n_tasks: int) -> List[int]:
        """Allocate budget equally among tasks.

        Args:
            n_tasks: Number of tasks

        Returns:
            List of budget allocations
        """
        if n_tasks == 0:
            return []

        available = min(self._available_budget, self.total_budget)
        per_task = max(self.min_task_budget, available // n_tasks)

        # Ensure we don't exceed available budget
        if per_task * n_tasks > available:
            per_task = available // n_tasks

        allocations = [per_task] * n_tasks

        # Distribute remainder
        remainder = available - (per_task * n_tasks)
        for i in range(min(remainder, n_tasks)):
            allocations[i] += 1

        return allocations

    def _allocate_weighted(self, complexity_scores: List[float]) -> List[int]:
        """Allocate budget based on complexity scores.

        Args:
            complexity_scores: List of complexity scores (0.0-1.0)

        Returns:
            List of budget allocations
        """
        if not complexity_scores:
            return []

        # Normalize scores
        total_score = sum(complexity_scores)
        if total_score == 0:
            return self._allocate_equal(len(complexity_scores))

        available = min(self._available_budget, self.total_budget)
        allocations = []

        for score in complexity_scores:
            # Weighted allocation with minimum guarantee
            weight = score / total_score
            allocation = max(self.min_task_budget, int(available * weight))
            allocations.append(allocation)

        # Adjust if we exceeded budget
        total_allocated = sum(allocations)
        if total_allocated > available:
            # Scale down proportionally
            scale = available / total_allocated
            allocations = [max(self.min_task_budget, int(a * scale)) for a in allocations]

        return allocations

    def _allocate_by_priority(self, priorities: List[str]) -> List[int]:
        """Allocate budget based on priority levels.

        Args:
            priorities: List of priority levels (high, medium, low)

        Returns:
            List of budget allocations
        """
        # Priority weights
        weights = {"high": 3, "medium": 2, "low": 1}

        # Convert to scores
        scores = [weights.get(p.lower(), 1) for p in priorities]
        total_weight = sum(scores)

        if total_weight == 0:
            return self._allocate_equal(len(priorities))

        # Convert to normalized complexity scores
        complexity_scores = [s / total_weight for s in scores]

        return self._allocate_weighted(complexity_scores)

    def _take_snapshot(self):
        """Take a snapshot of current budget state."""
        snapshot = BudgetSnapshot(
            timestamp=datetime.now(),
            total_allocated=sum(a.allocated_budget for a in self._allocations.values()),
            total_consumed=sum(a.consumed_budget for a in self._allocations.values()),
            active_tasks=len(self._allocations),
            task_allocations=self._allocations.copy(),
        )
        self._allocation_history.append(snapshot)

    def get_budget_summary(self) -> Dict[str, any]:
        """Get a summary of budget state.

        Returns:
            Dictionary with budget statistics
        """
        total_allocated = sum(a.allocated_budget for a in self._allocations.values())
        total_consumed = sum(a.consumed_budget for a in self._allocations.values())

        return {
            "total_budget": self.total_budget,
            "available_budget": self._available_budget,
            "allocated_budget": total_allocated,
            "consumed_budget": total_consumed,
            "utilization_rate": total_consumed / total_allocated if total_allocated > 0 else 0.0,
            "active_tasks": len(self._allocations),
            "reallocation_count": self._reallocation_count,
            "task_details": {
                task_id: {
                    "allocated": alloc.allocated_budget,
                    "consumed": alloc.consumed_budget,
                    "remaining": alloc.remaining_budget,
                    "utilization": alloc.get_utilization_rate(),
                }
                for task_id, alloc in self._allocations.items()
            },
        }
