"""Streaming instrumentation and handling for agent model request nodes.

This module encapsulates verbose streaming + logging logic used during
token-level streaming from the LLM provider. It updates session debug fields
and streams deltas to the provided callback while being resilient to errors.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.types import ToolCallback

from .flush_coordinator import ToolFlushCoordinator
from .tool_buffer import ToolBuffer

# Import streaming types with fallback for older versions
try:  # pragma: no cover - import guard for pydantic_ai streaming types
    from pydantic_ai.messages import PartDeltaEvent, TextPartDelta  # type: ignore

    STREAMING_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when streaming types unavailable
    PartDeltaEvent = None  # type: ignore
    TextPartDelta = None  # type: ignore
    STREAMING_AVAILABLE = False


logger = get_logger(__name__)


async def stream_model_request_node(
    node,
    agent_run_ctx,
    state_manager: StateManager,
    streaming_callback: Optional[Callable[[str], Awaitable[None]]],
    request_id: str,
    iteration_index: int,
    tool_buffer: Optional[ToolBuffer] = None,
    tool_callback: Optional[ToolCallback] = None,
    flush_coordinator: Optional[ToolFlushCoordinator] = None,
) -> None:
    """Stream token deltas for a model request node with detailed instrumentation.

    This function mirrors the prior inline logic in main.py but is extracted to
    keep main.py lean. It performs up to one retry on streaming failure and then
    degrades to non-streaming for that node.
    """
    if not (STREAMING_AVAILABLE and streaming_callback):
        return

    # Gracefully handle streaming errors from LLM provider
    for attempt in range(2):  # simple retry once, then degrade gracefully
        try:
            if flush_coordinator is not None:
                await flush_coordinator.ensure_before_request("pre-request:streaming")

            async with node.stream(agent_run_ctx) as request_stream:
                # Initialize per-node debug accumulators
                state_manager.session._debug_raw_stream_accum = ""
                state_manager.session._debug_events = []
                first_delta_logged = False
                debug_event_count = 0
                first_delta_seen = False
                seeded_prefix_sent = False
                pre_first_delta_text: Optional[str] = None

                # Helper to extract text from a possible final-result object
                def _extract_text(obj) -> Optional[str]:
                    try:
                        if obj is None:
                            return None
                        if isinstance(obj, str):
                            return obj
                        # Common attributes that may hold text
                        for attr in ("output", "text", "content", "message"):
                            v = getattr(obj, attr, None)
                            if isinstance(v, str) and v:
                                return v
                        # Parts-based result
                        parts = getattr(obj, "parts", None)
                        if isinstance(parts, (list, tuple)) and parts:
                            texts: list[str] = []
                            for p in parts:
                                c = getattr(p, "content", None)
                                if isinstance(c, str) and c:
                                    texts.append(c)
                            if texts:
                                return "".join(texts)
                        # Nested .result or .response
                        for attr in ("result", "response", "final"):
                            v = getattr(obj, attr, None)
                            t = _extract_text(v)
                            if t:
                                return t
                    except Exception:
                        return None
                    return None

                # Mark stream open
                try:
                    import time as _t

                    state_manager.session._debug_events.append(
                        f"[src] stream_opened ts_ns={_t.perf_counter_ns()}"
                    )
                except Exception:
                    pass

                async for event in request_stream:
                    debug_event_count += 1
                    # Log first few raw event types for diagnosis
                    if debug_event_count <= 5:
                        try:
                            etype = type(event).__name__
                            d = getattr(event, "delta", None)
                            dtype = type(d).__name__ if d is not None else None
                            c = getattr(d, "content_delta", None) if d is not None else None
                            clen = len(c) if isinstance(c, str) else None
                            cpreview = repr(c[:5]) if isinstance(c, str) else None
                            # Probe common fields on non-delta events to see if they contain text
                            r = getattr(event, "result", None)
                            rtype = type(r).__name__ if r is not None else None
                            rpreview = None
                            rplen = None
                            # Also inspect event.part if present (e.g., PartStartEvent)
                            p = getattr(event, "part", None)
                            ptype = type(p).__name__ if p is not None else None
                            pkind = getattr(p, "part_kind", None)
                            pcontent = getattr(p, "content", None)
                            ppreview = repr(pcontent[:20]) if isinstance(pcontent, str) else None
                            pplen = len(pcontent) if isinstance(pcontent, str) else None
                            try:
                                if isinstance(r, str):
                                    rpreview = repr(r[:20])
                                    rplen = len(r)
                                elif r is not None:
                                    # Try a few common shapes: .output, .text, .parts
                                    r_output = getattr(r, "output", None)
                                    r_text = getattr(r, "text", None)
                                    r_parts = getattr(r, "parts", None)
                                    if isinstance(r_output, str):
                                        rpreview = repr(r_output[:20])
                                        rplen = len(r_output)
                                    elif isinstance(r_text, str):
                                        rpreview = repr(r_text[:20])
                                        rplen = len(r_text)
                                    elif isinstance(r_parts, (list, tuple)) and r_parts:
                                        # render a compact preview of first textual part
                                        for _rp in r_parts:
                                            rc = getattr(_rp, "content", None)
                                            if isinstance(rc, str) and rc:
                                                rpreview = repr(rc[:20])
                                                rplen = len(rc)
                                                break
                            except Exception:
                                pass
                            state_manager.session._debug_events.append(
                                f"[src] event[{debug_event_count}] etype={etype} d={dtype} clen={clen} cprev={cpreview} rtype={rtype} rprev={rpreview} rlen={rplen} ptype={ptype} pkind={pkind} pprev={ppreview} plen={pplen}"
                            )
                        except Exception:
                            pass

                    # Attempt to capture pre-first-delta text from non-delta events
                    if not first_delta_seen:
                        try:
                            # event might be a PartStartEvent with .part.content
                            if hasattr(event, "part") and hasattr(event.part, "content"):
                                pc = event.part.content
                                if isinstance(pc, str) and pc and not pc.lstrip().startswith("\n"):
                                    # capture a short potential prefix
                                    pre_first_delta_text = pc[:100] if len(pc) > 100 else pc
                        except Exception:
                            pass

                    # Handle delta events
                    if PartDeltaEvent and isinstance(event, PartDeltaEvent):
                        if isinstance(event.delta, TextPartDelta):
                            if event.delta.content_delta is not None and streaming_callback:
                                # Seed prefix logic before the first true delta
                                if not first_delta_seen:
                                    first_delta_seen = True
                                    try:
                                        delta_text = event.delta.content_delta or ""
                                        # Only seed when we have a short, safe candidate
                                        if (
                                            pre_first_delta_text
                                            and len(pre_first_delta_text) <= 100
                                            and not seeded_prefix_sent
                                        ):
                                            # If delta contains the candidate, emit the prefix up to that point
                                            probe = pre_first_delta_text[:20]
                                            idx = pre_first_delta_text.find(probe)
                                            if idx > 0:
                                                prefix = pre_first_delta_text[:idx]
                                                if prefix:
                                                    await streaming_callback(prefix)
                                                    seeded_prefix_sent = True
                                                    state_manager.session._debug_events.append(
                                                        f"[src] seeded_prefix idx={idx} len={len(prefix)} preview={repr(prefix)}"
                                                    )
                                            elif idx == -1:
                                                # Delta text does not appear in pre-text; emit the pre-text directly as a seed
                                                # Safe for short pre-text (e.g., first word) to avoid duplication
                                                if pre_first_delta_text.strip():
                                                    await streaming_callback(pre_first_delta_text)
                                                    seeded_prefix_sent = True
                                                    state_manager.session._debug_events.append(
                                                        f"[src] seeded_prefix_direct len={len(pre_first_delta_text)} preview={repr(pre_first_delta_text)}"
                                                    )
                                            else:
                                                # idx == 0 means pre-text is already the start of delta; skip
                                                state_manager.session._debug_events.append(
                                                    f"[src] seed_skip idx={idx} delta_len={len(delta_text)}"
                                                )
                                    except Exception:
                                        pass
                                    finally:
                                        pre_first_delta_text = None

                                # Record first-delta instrumentation
                                if not first_delta_logged:
                                    try:
                                        import time as _t

                                        ts_ns = _t.perf_counter_ns()
                                    except Exception:
                                        ts_ns = 0
                                    # Store debug event summary for later display
                                    state_manager.session._debug_events.append(
                                        f"[src] first_delta_received ts_ns={ts_ns} chunk_repr={repr(event.delta.content_delta[:5] if event.delta.content_delta else '')} len={len(event.delta.content_delta or '')}"
                                    )
                                    first_delta_logged = True

                                # Accumulate full raw stream for comparison and forward delta
                                delta_text = event.delta.content_delta or ""
                                state_manager.session._debug_raw_stream_accum += delta_text
                                await streaming_callback(delta_text)
                        else:
                            # Log empty or non-text deltas encountered
                            state_manager.session._debug_events.append(
                                "[src] empty_or_nontext_delta_skipped"
                            )
                    else:
                        # Capture any final result text for diagnostics
                        try:
                            final_text = _extract_text(getattr(event, "result", None))
                            if final_text:
                                state_manager.session._debug_events.append(
                                    f"[src] final_text_preview len={len(final_text)} preview={repr(final_text[:20])}"
                                )
                        except Exception:
                            pass
            # Successful streaming; exit retry loop
            break
        except Exception as stream_err:
            # Just flush buffered tools and let pydantic-ai handle the rest
            if tool_buffer is not None and tool_callback is not None:
                try:
                    if flush_coordinator is not None:
                        await flush_coordinator.flush(origin="stream-retry")
                    else:
                        from .buffer_flush import flush_buffered_read_only_tools

                        await flush_buffered_read_only_tools(
                            tool_buffer,
                            tool_callback,
                            state_manager,
                            origin="stream-retry",
                        )
                except Exception:
                    logger.debug(
                        "Buffered tool flush during streaming retry failed (non-fatal)",
                        exc_info=True,
                    )

            # Let pydantic-ai handle the retry naturally - don't interfere
            logger.warning(
                "Streaming error (attempt %s/2) req=%s iter=%s: %s",
                attempt + 1,
                request_id,
                iteration_index,
                stream_err,
                exc_info=True,
            )

            # On second failure, degrade gracefully (no streaming)
            if attempt == 1:
                if getattr(state_manager.session, "show_thoughts", False):
                    from tunacode.ui import console as ui

                    await ui.muted("Switching to non-streaming processing for this node")
                break
