"""Utilities for flushing buffered read-only tool calls."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

from tunacode.core.logging.logger import get_logger
from tunacode.types import StateManager, ToolCallback
from tunacode.ui import console as ui
from tunacode.ui.tool_descriptions import get_batch_description

from .message_handler import get_model_messages
from .tool_buffer import ToolBuffer
from .tool_executor import execute_tools_parallel

logger = get_logger(__name__)

# ~48KB limit to keep model context healthy (tune as needed)
_MAX_RETURN_BYTES = 48_000


def _safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


def _truncate_bytes(s: str, limit: int) -> str:
    data = s.encode("utf-8", errors="replace")
    if len(data) <= limit:
        return s
    return data[:limit].decode("utf-8", errors="ignore") + "…[truncated]"


def _stringify_result(result: Any) -> str:
    """Prefer JSON for structured data; include error tags; mark no-output."""
    if isinstance(result, Exception):
        # Keep it compact; stack traces belong in logs, not prompts
        msg = getattr(result, "args", (None,))[0]
        text = f"[error] {str(msg) if msg else str(result)}"
        return _truncate_bytes(text, _MAX_RETURN_BYTES)
    if result is None:
        return "[no output]"
    # Preserve structure where possible
    if isinstance(result, (dict, list, tuple)):
        return _truncate_bytes(_safe_json_dumps(result), _MAX_RETURN_BYTES)
    return _truncate_bytes(str(result), _MAX_RETURN_BYTES)


async def flush_buffered_read_only_tools(
    tool_buffer: Optional[ToolBuffer],
    tool_callback: Optional[ToolCallback],
    state_manager: StateManager,
    *,
    origin: str = "buffered-tools",
    detailed: bool = False,
    banner: Optional[str] = None,
) -> bool:
    """Execute buffered read-only tools and report whether any work was performed."""
    if tool_buffer is None or tool_callback is None or not tool_buffer.has_tasks():
        return False

    buffered_tasks = tool_buffer.flush()
    if not buffered_tasks:
        return False

    batch_id = getattr(state_manager.session, "batch_counter", 0) + 1
    setattr(state_manager.session, "batch_counter", batch_id)

    tool_names = [getattr(part, "tool_name", "tool") for part, _ in buffered_tasks]

    # UI is best-effort; never fail the flush for UI issues
    try:
        batch_msg = get_batch_description(len(buffered_tasks), tool_names)
        await ui.update_spinner_message(
            f"[bold #00d7ff]{batch_msg}...[/bold #00d7ff]", state_manager
        )

        if detailed:
            header = banner or origin.upper()
            await ui.muted("\n" + "=" * 60)
            await ui.muted(
                f"🚀 {header}: Executing {len(buffered_tasks)} read-only tools concurrently"
            )
            await ui.muted("=" * 60)
            for idx, (part, _node) in enumerate(buffered_tasks, start=1):
                tool_desc = f"  [{idx}] {getattr(part, 'tool_name', 'tool')}"
                args = getattr(part, "args", {})
                if isinstance(args, dict):
                    if getattr(part, "tool_name", "") == "read_file" and "file_path" in args:
                        tool_desc += f" → {args['file_path']}"
                    elif getattr(part, "tool_name", "") == "grep" and "pattern" in args:
                        tool_desc += f" → pattern: '{args['pattern']}'"
                        if "include_files" in args:
                            tool_desc += f", files: '{args['include_files']}'"
                    elif getattr(part, "tool_name", "") == "list_dir" and "directory" in args:
                        tool_desc += f" → {args['directory']}"
                    elif getattr(part, "tool_name", "") == "glob" and "pattern" in args:
                        tool_desc += f" → pattern: '{args['pattern']}'"
                await ui.muted(tool_desc)
            await ui.muted("=" * 60)
        elif state_manager.session.show_thoughts:
            await ui.muted(f"⚡ {origin}: executing {len(buffered_tasks)} buffered read-only tools")
    except Exception:  # pragma: no cover
        logger.debug("Buffered tool flush UI failed (non-fatal)", exc_info=True)

    start = time.time()
    results = await execute_tools_parallel(buffered_tasks, tool_callback)
    elapsed_ms = (time.time() - start) * 1000.0

    # Nothing to append; still report metrics below
    if not results:
        if detailed:
            try:
                await ui.muted("No results produced by buffered tools.")
            except Exception:
                logger.debug("Buffered tool 'no results' UI failed", exc_info=True)
        return True

    # Gather existing tool returns to avoid duplicates across history
    existing_returns = {
        getattr(part, "tool_call_id")
        for message in getattr(state_manager.session, "messages", [])
        for part in getattr(message, "parts", [])
        if getattr(part, "part_kind", "") == "tool-return"
    }

    # Warn if cardinality differs; we still proceed defensively with zip
    if len(results) != len(buffered_tasks):
        logger.warning(
            "Buffered tool mismatch: tasks=%d results=%d", len(buffered_tasks), len(results)
        )

    ModelRequest, ToolReturnPart, _ = get_model_messages()
    new_returns = []
    seen_this_batch = set()

    # Attach by position but refuse duplicates/missing IDs; content is capped & tagged
    for (part, call_node), result in zip(buffered_tasks, results):
        tool_call_id = getattr(part, "tool_call_id", None)
        if not tool_call_id:
            # No ID → cannot synthesize a proper return for the model
            logger.debug(
                "Skipping buffered tool without tool_call_id: %r",
                getattr(part, "tool_name", "tool"),
            )
            continue
        if tool_call_id in existing_returns:
            # Already satisfied in history
            continue
        if tool_call_id in seen_this_batch:
            # Duplicate within this batch
            logger.warning("Duplicate tool_call_id within batch (skipped): %s", tool_call_id)
            continue

        content = _stringify_result(result)
        return_part = ToolReturnPart(
            tool_name=getattr(part, "tool_name", "tool"),
            content=content,
            tool_call_id=tool_call_id,
            timestamp=datetime.now(timezone.utc),
            part_kind="tool-return",
        )

        # Feed the provider-facing call graph first so retries reuse these returns immediately
        tool_responses = getattr(call_node, "_tool_responses", None)
        if isinstance(tool_responses, list):
            tool_responses.append(return_part)
        else:  # pragma: no cover - unexpected but safe guard
            logger.debug(
                "Call node missing _tool_responses list; synthetic return only logged locally",
            )

        new_returns.append(return_part)
        seen_this_batch.add(tool_call_id)

    if new_returns:
        state_manager.session.messages.append(ModelRequest(parts=new_returns, kind="request"))

    if detailed:
        try:
            # Cheap sequential estimate: ~100ms per tool if done serially (tune if you like)
            sequential_estimate = len(buffered_tasks) * 100.0
            speedup = (sequential_estimate / elapsed_ms) if elapsed_ms > 0 else 1.0
            await ui.muted(
                f"Batch completed in {elapsed_ms:.1f} ms (estimated speedup ×{speedup:.2f})"
            )
            await ui.muted("=" * 60)
        except Exception:  # pragma: no cover
            logger.debug("Buffered tool flush metrics display failed (non-fatal)", exc_info=True)

    return True
