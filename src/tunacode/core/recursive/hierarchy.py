"""Module: tunacode.core.recursive.hierarchy

Hierarchical task management system for maintaining parent-child relationships and execution state.
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class TaskExecutionContext:
    """Context information for task execution."""

    task_id: str
    parent_id: Optional[str] = None
    depth: int = 0
    inherited_context: Dict[str, Any] = field(default_factory=dict)
    local_context: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def get_full_context(self) -> Dict[str, Any]:
        """Get merged context (inherited + local)."""
        return {**self.inherited_context, **self.local_context}


@dataclass
class TaskRelationship:
    """Represents a relationship between tasks."""

    parent_id: str
    child_id: str
    relationship_type: str = "subtask"  # subtask, dependency, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskHierarchy:
    """Manages hierarchical task relationships and execution state."""

    def __init__(self):
        """Initialize the task hierarchy manager."""
        # Core data structures
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._parent_to_children: Dict[str, List[str]] = defaultdict(list)
        self._child_to_parent: Dict[str, str] = {}
        self._task_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self._execution_contexts: Dict[str, TaskExecutionContext] = {}
        self._execution_order: List[str] = []
        self._completed_tasks: Set[str] = set()
        self._failed_tasks: Set[str] = set()

    def add_task(
        self,
        task_id: str,
        task_data: Dict[str, Any],
        parent_id: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
    ) -> bool:
        """Add a task to the hierarchy.

        Args:
            task_id: Unique identifier for the task
            task_data: Task information (title, description, etc.)
            parent_id: Optional parent task ID
            dependencies: Optional list of task IDs this task depends on

        Returns:
            True if task was added successfully, False otherwise
        """
        if task_id in self._tasks:
            logger.warning(f"Task {task_id} already exists")
            return False

        # Store task data
        self._tasks[task_id] = {
            "id": task_id,
            "parent_id": parent_id,
            "created_at": datetime.now(),
            **task_data,
        }

        # Set up parent-child relationships
        if parent_id:
            if parent_id not in self._tasks:
                logger.error(f"Parent task {parent_id} does not exist")
                return False

            self._parent_to_children[parent_id].append(task_id)
            self._child_to_parent[task_id] = parent_id

        # Set up dependencies
        if dependencies:
            for dep_id in dependencies:
                if dep_id not in self._tasks:
                    logger.warning(f"Dependency {dep_id} does not exist yet")
                self.add_dependency(task_id, dep_id)

        logger.debug(f"Added task {task_id} to hierarchy")
        return True

    def add_dependency(self, task_id: str, depends_on: str) -> bool:
        """Add a dependency relationship between tasks.

        Args:
            task_id: Task that has the dependency
            depends_on: Task that must complete first

        Returns:
            True if dependency was added, False if it would create a cycle
        """
        # Check if adding this would create a cycle
        if self._would_create_cycle(task_id, depends_on):
            logger.error(f"Adding dependency {task_id} -> {depends_on} would create a cycle")
            return False

        self._task_dependencies[task_id].add(depends_on)
        self._reverse_dependencies[depends_on].add(task_id)
        return True

    def remove_dependency(self, task_id: str, depends_on: str) -> bool:
        """Remove a dependency relationship.

        Args:
            task_id: Task that has the dependency
            depends_on: Task to remove from dependencies

        Returns:
            True if dependency was removed
        """
        if depends_on in self._task_dependencies.get(task_id, set()):
            self._task_dependencies[task_id].remove(depends_on)
            self._reverse_dependencies[depends_on].discard(task_id)
            return True
        return False

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task information.

        Args:
            task_id: Task identifier

        Returns:
            Task data or None if not found
        """
        return self._tasks.get(task_id)

    def get_children(self, parent_id: str) -> List[str]:
        """Get all direct children of a task.

        Args:
            parent_id: Parent task ID

        Returns:
            List of child task IDs
        """
        return self._parent_to_children.get(parent_id, []).copy()

    def get_parent(self, task_id: str) -> Optional[str]:
        """Get the parent of a task.

        Args:
            task_id: Task ID

        Returns:
            Parent task ID or None
        """
        return self._child_to_parent.get(task_id)

    def get_ancestors(self, task_id: str) -> List[str]:
        """Get all ancestors of a task (parent, grandparent, etc.).

        Args:
            task_id: Task ID

        Returns:
            List of ancestor IDs from immediate parent to root
        """
        ancestors = []
        current = self._child_to_parent.get(task_id)

        while current:
            ancestors.append(current)
            current = self._child_to_parent.get(current)

        return ancestors

    def get_depth(self, task_id: str) -> int:
        """Get the depth of a task in the hierarchy.

        Args:
            task_id: Task ID

        Returns:
            Depth (0 for root tasks)
        """
        return len(self.get_ancestors(task_id))

    def get_dependencies(self, task_id: str) -> Set[str]:
        """Get tasks that must complete before this task.

        Args:
            task_id: Task ID

        Returns:
            Set of dependency task IDs
        """
        return self._task_dependencies.get(task_id, set()).copy()

    def get_dependents(self, task_id: str) -> Set[str]:
        """Get tasks that depend on this task.

        Args:
            task_id: Task ID

        Returns:
            Set of dependent task IDs
        """
        return self._reverse_dependencies.get(task_id, set()).copy()

    def can_execute(self, task_id: str) -> bool:
        """Check if a task can be executed (all dependencies met).

        Args:
            task_id: Task ID

        Returns:
            True if task can be executed
        """
        if task_id not in self._tasks:
            return False

        # Check if all dependencies are completed
        dependencies = self._task_dependencies.get(task_id, set())
        return all(dep in self._completed_tasks for dep in dependencies)

    def get_executable_tasks(self) -> List[str]:
        """Get all tasks that can currently be executed.

        Returns:
            List of task IDs that have all dependencies met
        """
        executable = []

        for task_id in self._tasks:
            if (
                task_id not in self._completed_tasks
                and task_id not in self._failed_tasks
                and self.can_execute(task_id)
            ):
                executable.append(task_id)

        return executable

    def mark_completed(self, task_id: str, result: Any = None) -> None:
        """Mark a task as completed.

        Args:
            task_id: Task ID
            result: Optional result data
        """
        if task_id in self._tasks:
            self._completed_tasks.add(task_id)
            self._tasks[task_id]["status"] = "completed"
            self._tasks[task_id]["result"] = result
            self._tasks[task_id]["completed_at"] = datetime.now()

            # Update execution context if exists
            if task_id in self._execution_contexts:
                self._execution_contexts[task_id].completed_at = datetime.now()

    def mark_failed(self, task_id: str, error: str) -> None:
        """Mark a task as failed.

        Args:
            task_id: Task ID
            error: Error message
        """
        if task_id in self._tasks:
            self._failed_tasks.add(task_id)
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["error"] = error
            self._tasks[task_id]["failed_at"] = datetime.now()

    def create_execution_context(
        self, task_id: str, parent_context: Optional[Dict[str, Any]] = None
    ) -> TaskExecutionContext:
        """Create an execution context for a task.

        Args:
            task_id: Task ID
            parent_context: Optional parent context to inherit

        Returns:
            New execution context
        """
        parent_id = self._child_to_parent.get(task_id)
        depth = self.get_depth(task_id)

        context = TaskExecutionContext(
            task_id=task_id,
            parent_id=parent_id,
            depth=depth,
            inherited_context=parent_context or {},
            started_at=datetime.now(),
        )

        self._execution_contexts[task_id] = context
        self._execution_order.append(task_id)

        return context

    def get_execution_context(self, task_id: str) -> Optional[TaskExecutionContext]:
        """Get the execution context for a task.

        Args:
            task_id: Task ID

        Returns:
            Execution context or None
        """
        return self._execution_contexts.get(task_id)

    def propagate_context(
        self, from_task: str, to_task: str, context_update: Dict[str, Any]
    ) -> None:
        """Propagate context from one task to another.

        Args:
            from_task: Source task ID
            to_task: Target task ID
            context_update: Context to propagate
        """
        if to_task in self._execution_contexts:
            self._execution_contexts[to_task].inherited_context.update(context_update)

    def aggregate_child_results(self, parent_id: str) -> Dict[str, Any]:
        """Aggregate results from all children of a task.

        Args:
            parent_id: Parent task ID

        Returns:
            Aggregated results dictionary
        """
        children = self._parent_to_children.get(parent_id, [])

        results = {"completed": [], "failed": [], "pending": [], "aggregated_data": {}}

        for child_id in children:
            child_task = self._tasks.get(child_id, {})
            status = child_task.get("status", "pending")

            if status == "completed":
                results["completed"].append({"id": child_id, "result": child_task.get("result")})
            elif status == "failed":
                results["failed"].append({"id": child_id, "error": child_task.get("error")})
            else:
                results["pending"].append(child_id)

        return results

    def get_execution_path(self, task_id: str) -> List[str]:
        """Get the full execution path from root to this task.

        Args:
            task_id: Task ID

        Returns:
            List of task IDs from root to this task
        """
        ancestors = self.get_ancestors(task_id)
        ancestors.reverse()  # Root to task order
        ancestors.append(task_id)
        return ancestors

    def _would_create_cycle(self, task_id: str, depends_on: str) -> bool:
        """Check if adding a dependency would create a cycle.

        Args:
            task_id: Task that would have the dependency
            depends_on: Task it would depend on

        Returns:
            True if this would create a cycle
        """
        # BFS to check if we can reach task_id from depends_on
        visited = set()
        queue = deque([depends_on])

        while queue:
            current = queue.popleft()
            if current == task_id:
                return True

            if current in visited:
                continue

            visited.add(current)

            # Add all tasks that depend on current
            for dependent in self._reverse_dependencies.get(current, []):
                if dependent not in visited:
                    queue.append(dependent)

        return False

    def get_topological_order(self) -> List[str]:
        """Get a valid execution order respecting all dependencies.

        Returns:
            List of task IDs in valid execution order
        """
        # Kahn's algorithm for topological sort
        in_degree = {}
        for task_id in self._tasks:
            in_degree[task_id] = len(self._task_dependencies.get(task_id, set()))

        queue = deque([task_id for task_id, degree in in_degree.items() if degree == 0])
        order = []

        while queue:
            current = queue.popleft()
            order.append(current)

            # Reduce in-degree for all dependents
            for dependent in self._reverse_dependencies.get(current, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # If we couldn't process all tasks, there's a cycle
        if len(order) != len(self._tasks):
            logger.error("Dependency cycle detected")
            # Return partial order
            remaining = [t for t in self._tasks if t not in order]
            order.extend(remaining)

        return order

    def visualize_hierarchy(self, show_dependencies: bool = True) -> str:
        """Generate a text visualization of the task hierarchy.

        Args:
            show_dependencies: Whether to show dependency relationships

        Returns:
            String representation of the hierarchy
        """
        lines = []

        # Find root tasks (no parent)
        roots = [task_id for task_id in self._tasks if task_id not in self._child_to_parent]

        def build_tree(task_id: str, prefix: str = "", is_last: bool = True):
            task = self._tasks[task_id]
            status = task.get("status", "pending")

            # Build current line
            connector = "└── " if is_last else "├── "
            status_icon = "✓" if status == "completed" else "✗" if status == "failed" else "○"
            line = f"{prefix}{connector}[{status_icon}] {task_id}: {task.get('title', 'Untitled')[:50]}"

            # Add dependencies if requested
            if show_dependencies:
                deps = self._task_dependencies.get(task_id, set())
                if deps:
                    line += f" (deps: {', '.join(deps)})"

            lines.append(line)

            # Process children
            children = self._parent_to_children.get(task_id, [])
            for i, child_id in enumerate(children):
                extension = "    " if is_last else "│   "
                build_tree(child_id, prefix + extension, i == len(children) - 1)

        # Build tree for each root
        for i, root_id in enumerate(roots):
            build_tree(root_id, "", i == len(roots) - 1)

        return "\n".join(lines) if lines else "Empty hierarchy"
