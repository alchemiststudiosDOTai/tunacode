"""Module: tunacode.ui.recursive_progress

Visual feedback and progress tracking UI for recursive task execution.
"""

from datetime import datetime
from typing import Dict, List, Optional

from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.tree import Tree

from tunacode.core.recursive.budget import BudgetManager
from tunacode.core.recursive.executor import TaskNode
from tunacode.core.recursive.hierarchy import TaskHierarchy


class RecursiveProgressUI:
    """UI components for visualizing recursive execution progress."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize the progress UI.

        Args:
            console: Rich console instance (creates new if not provided)
        """
        self.console = console or Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
        )
        self._task_progress_map: Dict[str, TaskID] = {}
        self._live: Optional[Live] = None

    def start_live_display(self) -> None:
        """Start live display for real-time updates."""
        if not self._live:
            self._live = Live(
                self.get_dashboard(),
                console=self.console,
                refresh_per_second=2,
                vertical_overflow="visible",
            )
            self._live.start()

    def stop_live_display(self) -> None:
        """Stop the live display."""
        if self._live:
            self._live.stop()
            self._live = None

    def update_task_progress(
        self, task_id: str, description: str, completed: int, total: int
    ) -> None:
        """Update progress for a specific task.

        Args:
            task_id: Task identifier
            description: Task description
            completed: Number of completed iterations
            total: Total iterations
        """
        if task_id not in self._task_progress_map:
            # Create new progress task
            progress_id = self.progress.add_task(description, total=total, completed=completed)
            self._task_progress_map[task_id] = progress_id
        else:
            # Update existing task
            progress_id = self._task_progress_map[task_id]
            self.progress.update(
                progress_id, description=description, completed=completed, total=total
            )

    def display_task_hierarchy(self, hierarchy: TaskHierarchy) -> Tree:
        """Create a tree visualization of task hierarchy.

        Args:
            hierarchy: TaskHierarchy instance

        Returns:
            Rich Tree object
        """
        tree = Tree("🎯 Task Hierarchy", guide_style="blue")

        # Find root tasks
        all_tasks = hierarchy._tasks
        root_tasks = [task_id for task_id in all_tasks if hierarchy.get_parent(task_id) is None]

        def build_tree_node(parent_node: Tree, task_id: str, depth: int = 0):
            """Recursively build tree nodes."""
            task = hierarchy.get_task(task_id)
            if not task:
                return

            # Determine status icon
            status = task.get("status", "pending")
            icon = {"completed": "✅", "failed": "❌", "in_progress": "🔄", "pending": "⏳"}.get(
                status, "❓"
            )

            # Create node label
            title = task.get("title", "Untitled")[:50]
            label = f"{icon} [{task_id}] {title}"

            # Add progress if in progress
            if status == "in_progress":
                label += " [yellow](running)[/yellow]"

            # Add node to tree
            node = parent_node.add(label)

            # Add children
            children = hierarchy.get_children(task_id)
            for child_id in children:
                build_tree_node(node, child_id, depth + 1)

        # Build tree from roots
        for root_id in root_tasks:
            build_tree_node(tree, root_id)

        return tree

    def display_budget_status(self, budget_manager: BudgetManager) -> Table:
        """Create a table showing budget allocation and usage.

        Args:
            budget_manager: BudgetManager instance

        Returns:
            Rich Table object
        """
        table = Table(title="💰 Budget Status", show_header=True, header_style="bold cyan")
        table.add_column("Task ID", style="dim", width=12)
        table.add_column("Allocated", justify="right")
        table.add_column("Used", justify="right")
        table.add_column("Remaining", justify="right")
        table.add_column("Utilization", justify="right")
        table.add_column("Status", justify="center")

        summary = budget_manager.get_budget_summary()

        for task_id, details in summary["task_details"].items():
            utilization = details["utilization"]

            # Color code utilization
            if utilization > 0.9:
                util_color = "red"
                status = "⚠️ High"
            elif utilization > 0.7:
                util_color = "yellow"
                status = "📊 Normal"
            else:
                util_color = "green"
                status = "✅ Good"

            table.add_row(
                task_id[:8] + "...",
                str(details["allocated"]),
                str(details["consumed"]),
                str(details["remaining"]),
                f"[{util_color}]{utilization:.1%}[/{util_color}]",
                status,
            )

        # Add summary row
        table.add_section()
        table.add_row(
            "TOTAL",
            str(summary["allocated_budget"]),
            str(summary["consumed_budget"]),
            str(summary["available_budget"]),
            f"{summary['utilization_rate']:.1%}",
            "📈",
        )

        return table

    def display_execution_stack(self, stack: List[str]) -> Panel:
        """Display current execution stack.

        Args:
            stack: List of task IDs in execution order

        Returns:
            Rich Panel object
        """
        if not stack:
            content = "[dim]No tasks in execution[/dim]"
        else:
            # Show stack with depth indicators
            lines = []
            for i, task_id in enumerate(stack):
                indent = "  " * i
                arrow = "└─" if i == len(stack) - 1 else "├─"
                lines.append(f"{indent}{arrow} {task_id}")
            content = "\n".join(lines)

        return Panel(content, title="📚 Execution Stack", border_style="green")

    def display_task_details(self, task_node: TaskNode) -> Panel:
        """Display detailed information about a task.

        Args:
            task_node: TaskNode instance

        Returns:
            Rich Panel object
        """
        details = Table(show_header=False, box=None, padding=0)
        details.add_column("Property", style="bold cyan")
        details.add_column("Value")

        details.add_row("Title", task_node.title or "Untitled")
        details.add_row("Status", f"[yellow]{task_node.status}[/yellow]")
        details.add_row("Complexity", f"{task_node.complexity_score:.2f}")
        details.add_row("Depth", str(task_node.depth))
        details.add_row("Budget", f"{task_node.iteration_budget} iterations")

        if task_node.subtasks:
            details.add_row("Subtasks", f"{len(task_node.subtasks)} tasks")

        if task_node.error:
            details.add_row("Error", f"[red]{task_node.error}[/red]")

        return Panel(details, title=f"🔍 Task Details: {task_node.id[:8]}...", border_style="blue")

    def get_dashboard(
        self,
        hierarchy: Optional[TaskHierarchy] = None,
        budget_manager: Optional[BudgetManager] = None,
        current_task: Optional[TaskNode] = None,
        execution_stack: Optional[List[str]] = None,
    ) -> Panel:
        """Create a comprehensive dashboard view.

        Args:
            hierarchy: Optional TaskHierarchy instance
            budget_manager: Optional BudgetManager instance
            current_task: Optional current TaskNode
            execution_stack: Optional execution stack

        Returns:
            Rich Panel containing the dashboard
        """
        components = []

        # Add progress bars
        components.append(Panel(self.progress, title="⏳ Task Progress", border_style="green"))

        # Add hierarchy tree if available
        if hierarchy:
            components.append(self.display_task_hierarchy(hierarchy))

        # Add budget status if available
        if budget_manager:
            components.append(self.display_budget_status(budget_manager))

        # Add execution stack if available
        if execution_stack is not None:
            components.append(self.display_execution_stack(execution_stack))

        # Add current task details if available
        if current_task:
            components.append(self.display_task_details(current_task))

        # Arrange components in columns
        if len(components) > 2:
            # Use columns for better layout
            left_col = components[: len(components) // 2]
            right_col = components[len(components) // 2 :]

            content = Columns(
                ["\n\n".join(str(c) for c in left_col), "\n\n".join(str(c) for c in right_col)],
                equal=True,
                expand=True,
            )
        else:
            content = "\n\n".join(str(c) for c in components)

        return Panel(
            content,
            title="🔄 Recursive Execution Dashboard",
            subtitle=f"Updated: {datetime.now().strftime('%H:%M:%S')}",
            border_style="bold blue",
        )

    async def show_completion_summary(
        self,
        total_tasks: int,
        completed_tasks: int,
        failed_tasks: int,
        total_time: float,
        total_iterations: int,
    ) -> None:
        """Display a summary when execution completes.

        Args:
            total_tasks: Total number of tasks
            completed_tasks: Number of completed tasks
            failed_tasks: Number of failed tasks
            total_time: Total execution time in seconds
            total_iterations: Total iterations used
        """
        summary = Table(title="📊 Execution Summary", show_header=True, header_style="bold green")
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", justify="right")

        summary.add_row("Total Tasks", str(total_tasks))
        summary.add_row("Completed", f"[green]{completed_tasks}[/green]")
        summary.add_row("Failed", f"[red]{failed_tasks}[/red]")
        summary.add_row("Success Rate", f"{(completed_tasks / total_tasks) * 100:.1f}%")
        summary.add_row("Total Time", f"{total_time:.2f}s")
        summary.add_row("Total Iterations", str(total_iterations))
        summary.add_row("Avg Time/Task", f"{total_time / total_tasks:.2f}s")

        self.console.print("\n")
        self.console.print(summary)
        self.console.print("\n")

        # Show completion message
        if failed_tasks == 0:
            self.console.print("[bold green]✅ All tasks completed successfully![/bold green]")
        else:
            self.console.print(
                f"[bold yellow]⚠️ Completed with {failed_tasks} failures[/bold yellow]"
            )


# Convenience functions for integration
async def show_recursive_progress(
    console: Console, message: str, task_id: Optional[str] = None, depth: int = 0
) -> None:
    """Show progress message for recursive execution.

    Args:
        console: Rich console instance
        message: Progress message
        task_id: Optional task ID
        depth: Recursion depth
    """
    indent = "  " * depth
    prefix = f"[dim][{task_id[:8]}...][/dim]" if task_id else ""

    console.print(f"{indent}🔄 {prefix} {message}")


async def show_task_completion(
    console: Console, task_id: str, success: bool, depth: int = 0
) -> None:
    """Show task completion status.

    Args:
        console: Rich console instance
        task_id: Task ID
        success: Whether task succeeded
        depth: Recursion depth
    """
    indent = "  " * depth
    icon = "✅" if success else "❌"
    status = "completed" if success else "failed"
    color = "green" if success else "red"

    console.print(f"{indent}{icon} Task [{task_id[:8]}...] [{color}]{status}[/{color}]")
