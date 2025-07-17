"""Todo command implementation."""

from datetime import datetime

from rich.box import ROUNDED
from rich.table import Table

from tunacode.types import CommandArgs, CommandContext, CommandResult, TodoItem
from tunacode.ui import console as ui

from ..base import CommandCategory, CommandSpec, SimpleCommand


class TodoCommand(SimpleCommand):
    """Manage todo items."""

    spec = CommandSpec(
        name="todo",
        aliases=["/todo", "todos"],
        description="Manage todo items.",
        category=CommandCategory.DEVELOPMENT,
    )

    async def execute(self, args: CommandArgs, context: CommandContext) -> CommandResult:
        if not args:
            await self.list_todos(context)
            return

        subcommand = args[0].lower()
        subcommand_args = args[1:]

        if subcommand == "list":
            await self.list_todos(context)
        elif subcommand == "add":
            await self.add_todo(subcommand_args, context)
        elif subcommand == "done":
            await self.mark_done(subcommand_args, context)
        elif subcommand == "update":
            await self.update_todo(subcommand_args, context)
        elif subcommand == "priority":
            await self.set_priority(subcommand_args, context)
        elif subcommand == "remove":
            await self.remove_todo(subcommand_args, context)
        elif subcommand == "clear":
            await self.clear_todos(context)
        else:
            await ui.error(
                "Invalid todo subcommand. Available subcommands: list, add, done, update, priority, remove, clear"
            )

    async def list_todos(self, context: CommandContext) -> None:
        """Display the todo list with Rich formatting."""
        todos = context.state_manager.session.todos
        if not todos:
            await ui.info("No todos found.")
            return

        # Create Rich table
        table = Table(show_header=True, box=ROUNDED, padding=(0, 1))
        table.add_column("ID", style="bold cyan", width=4, justify="center")
        table.add_column("Status", width=12, justify="center")
        table.add_column("Task", style="white", min_width=20)
        table.add_column("Priority", width=10, justify="center")
        table.add_column("Created", style="dim", width=12)

        # Sort todos by status and priority
        pending = [t for t in todos if t.status == "pending"]
        in_progress = [t for t in todos if t.status == "in_progress"]
        completed = [t for t in todos if t.status == "completed"]

        # Sort each group by priority (high->medium->low)
        priority_order = {"high": 0, "medium": 1, "low": 2}

        for group in [in_progress, pending, completed]:
            group.sort(key=lambda x: priority_order.get(x.priority, 3))

        # Add rows to table
        for todo in in_progress + pending + completed:
            # Status with emoji
            if todo.status == "pending":
                status_display = "○ pending"
            elif todo.status == "in_progress":
                status_display = "○ in progress"
            else:
                status_display = "✓ completed"

            # Priority with color coding
            if todo.priority == "high":
                priority_display = "[red] high[/red]"
            elif todo.priority == "medium":
                priority_display = "[yellow] medium[/yellow]"
            else:
                priority_display = "[green] low[/green]"

            # Format created date
            created_display = todo.created_at.strftime("%m/%d %H:%M")

            table.add_row(todo.id, status_display, todo.content, priority_display, created_display)

        await ui.print(table)

    async def add_todo(self, args: CommandArgs, context: CommandContext) -> None:
        """Add a new todo and show updated list."""
        if not args:
            await ui.error("Please provide a task to add.")
            return

        content = " ".join(args)
        new_id = f"{int(datetime.now().timestamp() * 1000000)}"
        new_todo = TodoItem(
            id=new_id,
            content=content,
            status="pending",
            priority="medium",
            created_at=datetime.now(),
        )
        context.state_manager.add_todo(new_todo)

        await ui.success(f"Todo created: {content}")
        await self.list_todos(context)

    async def mark_done(self, args: CommandArgs, context: CommandContext) -> None:
        """Mark a todo as done and show updated list."""
        if not args:
            await ui.error("Please provide a todo ID to mark as done.")
            return

        todo_id = args[0]
        # Find the todo to get its content for feedback
        todo_content = None
        for todo in context.state_manager.session.todos:
            if todo.id == todo_id:
                todo_content = todo.content
                break

        if not todo_content:
            await ui.error(f"Todo with id {todo_id} not found.")
            return

        context.state_manager.update_todo(todo_id, "completed")
        await ui.success(f"Marked todo {todo_id} as done: {todo_content}")
        await self.list_todos(context)

    async def update_todo(self, args: CommandArgs, context: CommandContext) -> None:
        """Update a todo status and show updated list."""
        if len(args) < 2:
            await ui.error("Please provide a todo ID and a new status.")
            return

        todo_id = args[0]
        new_status = args[1].lower()
        if new_status not in ["pending", "in_progress", "completed"]:
            await ui.error("Invalid status. Must be one of: pending, in_progress, completed")
            return

        for todo in context.state_manager.session.todos:
            if todo.id == todo_id:
                todo.status = new_status
                await ui.success(f"Updated todo {todo_id} to status {new_status}: {todo.content}")
                await self.list_todos(context)
                return

        await ui.error(f"Todo with id {todo_id} not found.")

    async def set_priority(self, args: CommandArgs, context: CommandContext) -> None:
        """Set todo priority and show updated list."""
        if len(args) < 2:
            await ui.error("Please provide a todo ID and a new priority.")
            return

        todo_id = args[0]
        new_priority = args[1].lower()
        if new_priority not in ["high", "medium", "low"]:
            await ui.error("Invalid priority. Must be one of: high, medium, low")
            return

        for todo in context.state_manager.session.todos:
            if todo.id == todo_id:
                todo.priority = new_priority
                await ui.success(f"Set todo {todo_id} to priority {new_priority}: {todo.content}")
                await self.list_todos(context)
                return

        await ui.error(f"Todo with id {todo_id} not found.")

    async def remove_todo(self, args: CommandArgs, context: CommandContext) -> None:
        """Remove a todo and show updated list."""
        if not args:
            await ui.error("Please provide a todo ID to remove.")
            return

        todo_id = args[0]
        # Find the todo to get its content for feedback
        todo_content = None
        for todo in context.state_manager.session.todos:
            if todo.id == todo_id:
                todo_content = todo.content
                break

        if not todo_content:
            await ui.error(f"Todo with id {todo_id} not found.")
            return

        context.state_manager.remove_todo(todo_id)
        await ui.success(f"Removed todo {todo_id}: {todo_content}")
        await self.list_todos(context)

    async def clear_todos(self, context: CommandContext) -> None:
        """Clear all todos and show confirmation."""
        todo_count = len(context.state_manager.session.todos)
        if todo_count == 0:
            await ui.info("No todos to clear.")
            return

        context.state_manager.clear_todos()
        await ui.success(f"Cleared all {todo_count} todos.")
        await self.list_todos(context)
