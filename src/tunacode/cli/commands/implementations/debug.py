"""Debug and troubleshooting commands for TunaCode CLI."""

from typing import List

from ....types import CommandContext
from ....ui import console as ui
from ..base import CommandCategory, CommandSpec, SimpleCommand


class YoloCommand(SimpleCommand):
    """Toggle YOLO mode (skip confirmations)."""

    spec = CommandSpec(
        name="yolo",
        aliases=["/yolo"],
        description="Toggle YOLO mode (skip tool confirmations)",
        category=CommandCategory.DEVELOPMENT,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        state = context.state_manager.session
        state.yolo = not state.yolo
        if state.yolo:
            await ui.success("All tools are now active ⚡ Please proceed with caution.\n")
        else:
            await ui.info("Tool confirmations re-enabled for safety.\n")


class DumpCommand(SimpleCommand):
    """Dump message history."""

    spec = CommandSpec(
        name="dump",
        aliases=["/dump"],
        description="Dump the current message history",
        category=CommandCategory.DEBUG,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        await ui.dump_messages(context.state_manager.session.messages)


class ThoughtsCommand(SimpleCommand):
    """Toggle display of agent thoughts."""

    spec = CommandSpec(
        name="thoughts",
        aliases=["/thoughts"],
        description="Show or hide agent thought messages",
        category=CommandCategory.DEBUG,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        state = context.state_manager.session

        # No args - toggle
        if not args:
            state.show_thoughts = not state.show_thoughts
            status = "ON" if state.show_thoughts else "OFF"
            await ui.success(f"Thought display {status}")
            return

        # Parse argument
        arg = args[0].lower()
        if arg in {"on", "1", "true"}:
            state.show_thoughts = True
        elif arg in {"off", "0", "false"}:
            state.show_thoughts = False
        else:
            await ui.error("Usage: /thoughts [on|off]")
            return

        status = "ON" if state.show_thoughts else "OFF"
        await ui.success(f"Thought display {status}")


class IterationsCommand(SimpleCommand):
    """Configure maximum agent iterations for ReAct reasoning."""

    spec = CommandSpec(
        name="iterations",
        aliases=["/iterations"],
        description="Set maximum agent iterations for complex reasoning",
        category=CommandCategory.DEBUG,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        state = context.state_manager.session

        # Guard clause - handle "no args" case first and return early
        if not args:
            current = state.user_config.get("settings", {}).get("max_iterations", 40)
            await ui.info(f"Current maximum iterations: {current}")
            await ui.muted("Usage: /iterations <number> (1-100)")
            return

        # update the logic to not be as nested messely, the above guars needing to get as messy
        try:
            new_limit = int(args[0])
            if new_limit < 1 or new_limit > 100:
                await ui.error("Iterations must be between 1 and 100")
                return

            # Update the user config
            if "settings" not in state.user_config:
                state.user_config["settings"] = {}
            state.user_config["settings"]["max_iterations"] = new_limit

            await ui.success(f"Maximum iterations set to {new_limit}")
        except ValueError:
            await ui.error("Please provide a valid number")


class FixCommand(SimpleCommand):
    """Fix orphaned tool calls that cause API errors."""

    spec = CommandSpec(
        name="fix",
        aliases=["/fix"],
        description="Fix orphaned tool calls causing API errors",
        category=CommandCategory.DEBUG,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        from tunacode.core.agents import patch_tool_messages

        # Count current messages
        before_count = len(context.state_manager.session.messages)

        # Patch orphaned tool calls
        patch_tool_messages("Tool call resolved by /fix command", context.state_manager)

        # Count after patching
        after_count = len(context.state_manager.session.messages)
        patched_count = after_count - before_count

        if patched_count > 0:
            await ui.success(f"Fixed {patched_count} orphaned tool call(s)")
            await ui.muted("You can now continue the conversation normally")
        else:
            await ui.info("No orphaned tool calls found")


class ParseToolsCommand(SimpleCommand):
    """Parse and execute JSON tool calls from the last response."""

    spec = CommandSpec(
        name="parsetools",
        aliases=["/parsetools"],
        description=("Parse JSON tool calls from last response when structured calling fails"),
        category=CommandCategory.DEBUG,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        from tunacode.core.agents import extract_and_execute_tool_calls

        # Find the last model response in messages
        messages = context.state_manager.session.messages
        if not messages:
            await ui.error("No message history found")
            return

        # Look for the most recent response with text content
        found_content = False
        for msg in reversed(messages):
            if hasattr(msg, "parts"):
                for part in msg.parts:
                    if hasattr(part, "content") and isinstance(part.content, str):
                        # Create tool callback
                        from tunacode.cli.repl import _tool_handler

                        def tool_callback_with_state(part, _node):
                            return _tool_handler(part, context.state_manager)

                        try:
                            await extract_and_execute_tool_calls(
                                part.content,
                                tool_callback_with_state,
                                context.state_manager,
                            )
                            await ui.success("JSON tool parsing completed")
                            found_content = True
                            return
                        except Exception as e:
                            await ui.error(f"Failed to parse tools: {str(e)}")
                            return

        if not found_content:
            await ui.error("No parseable content found in recent messages")
