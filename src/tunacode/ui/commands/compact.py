"""Compact command for TunaCode REPL."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp

from tunacode.core.limits import get_summary_threshold
from tunacode.ui.commands.base import Command

# Number of recent messages to retain after summary compaction
RETAINED_MESSAGES_COUNT = 3


class CompactCommand(Command):
    """Compress conversation history into a summary."""

    name = "compact"
    description = "Compress conversation history into a summary"
    usage = "/compact [status]"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        from tunacode.core.agents.resume import (
            create_summary_request_message,
            filter_compacted,
            generate_summary,
        )
        from tunacode.utils.messaging import estimate_tokens

        session = app.state_manager.session
        messages = session.messages
        model = session.current_model

        total_tokens = 0
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if isinstance(content, str):
                    total_tokens += estimate_tokens(content, model)
            elif hasattr(msg, "parts"):
                for part in msg.parts:
                    content = getattr(part, "content", None)
                    if isinstance(content, str):
                        total_tokens += estimate_tokens(content, model)

        subcommand = args.strip().lower() if args else ""

        # Get configured threshold
        configured_threshold = get_summary_threshold()

        if subcommand == "status":
            app.rich_log.write(f"Messages: {len(messages)}")
            app.rich_log.write(f"Tokens: ~{total_tokens:,}")
            app.rich_log.write(f"Threshold: {configured_threshold:,}")

            if total_tokens > configured_threshold:
                app.rich_log.write(
                    "[yellow]Above threshold - /compact will summarize[/yellow]"
                )
            else:
                app.rich_log.write("[dim]Below threshold[/dim]")
            return

        if len(messages) < 4:
            app.notify(
                "Not enough messages to compact (need at least 4)", severity="warning"
            )
            return

        filtered = filter_compacted(messages)
        if len(filtered) < len(messages) and len(filtered) <= 4:
            app.notify("Already compacted recently", severity="warning")
            return

        app.notify("Compacting conversation...")

        try:
            from tunacode.core.agents import agent_components as ac

            agent = ac.get_or_create_agent(model, app.state_manager)
            tail_start = max(0, len(messages) - RETAINED_MESSAGES_COUNT)

            # Save the tail before modifying
            tail_messages = messages[tail_start:]

            summary = await generate_summary(
                agent,
                messages,
                model,
                start_index=0,
                end_index=tail_start,
            )

            summary_message = create_summary_request_message(summary)

            # Store summary for ctrl+o viewing
            session.last_summary = summary

            # Replace messages: [summary] + [tail]
            messages[:] = [summary_message] + tail_messages
            session.update_token_count()

            app.rich_log.write(
                f"[green]Compacted[/green] {tail_start} messages "
                f"[dim](ctrl+o to see summary)[/dim]"
            )
            app.rich_log.write(f"[dim]Summary: {summary.token_count} tokens[/dim]")
            app.notify(f"Compacted! {summary.token_count} token summary")
            app.state_manager.save_session()

        except Exception as e:
            app.notify(f"Compact failed: {e}", severity="error")
