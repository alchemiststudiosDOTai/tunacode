"""Streaming instrumentation and handling for agent model request nodes.

This module encapsulates verbose streaming logic used during
token-level streaming from the LLM provider. It updates session debug fields
and streams deltas to the provided callback while being resilient to errors.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from pydantic_ai.messages import PartDeltaEvent, TextPartDelta

from tunacode.core.logging import get_logger
from tunacode.core.state import StateManager


def _find_overlap_length(pre_text: str, delta_text: str) -> int:
    """Find length of longest pre_text suffix that equals delta_text prefix.

    This detects when delta_text starts with content already in pre_text,
    so we can avoid emitting duplicate text.

    Returns:
        Number of characters that overlap (0 if no overlap).
    """
    if not pre_text or not delta_text:
        return 0

    max_check = min(len(pre_text), len(delta_text))
    for overlap_len in range(max_check, 0, -1):
        if delta_text[:overlap_len] == pre_text[-overlap_len:]:
            return overlap_len
    return 0


async def stream_model_request_node(
    node,
    agent_run_ctx,
    state_manager: StateManager,
    streaming_callback: Callable[[str], Awaitable[None]] | None,
    request_id: str,
    iteration_index: int,
) -> None:
    """Stream token deltas for a model request node with detailed instrumentation.

    This function mirrors the prior inline logic in main.py but is extracted to
    keep main.py lean. On streaming failure, it degrades gracefully to allow
    non-streaming processing of the node.
    """
    if not streaming_callback:
        return

    logger = get_logger()
    stream_start = time.perf_counter()

    # Gracefully handle streaming errors from LLM provider
    try:
        async with node.stream(agent_run_ctx) as request_stream:
            # Initialize per-node debug accumulators
            state_manager.session._debug_raw_stream_accum = ""
            state_manager.session._debug_events = []
            first_delta_logged = False
            debug_event_count = 0
            first_delta_seen = False
            seeded_prefix_sent = False
            pre_first_delta_text: str | None = None

            # Helper to extract text from a possible final-result object
            def _extract_text(obj) -> str | None:
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
                    if isinstance(parts, list | tuple) and parts:
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
                                elif isinstance(r_parts, list | tuple) and r_parts:
                                    # render a compact preview of first textual part
                                    for _rp in r_parts:
                                        rc = getattr(_rp, "content", None)
                                        if isinstance(rc, str) and rc:
                                            rpreview = repr(rc[:20])
                                            rplen = len(rc)
                                            break
                        except Exception:
                            pass
                        event_info = (
                            f"[src] event[{debug_event_count}] etype={etype} d={dtype} "
                            f"clen={clen} cprev={cpreview} rtype={rtype} "
                            f"rprev={rpreview} rlen={rplen} ptype={ptype} "
                            f"pkind={pkind} pprev={ppreview} plen={pplen}"
                        )
                        state_manager.session._debug_events.append(event_info)
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
                if isinstance(event, PartDeltaEvent):
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
                                        # Find overlap: longest suffix of pre_first_delta_text
                                        # that matches a prefix of delta_text
                                        overlap_len = _find_overlap_length(
                                            pre_first_delta_text, delta_text
                                        )
                                        # Emit the non-overlapping prefix
                                        prefix_len = len(pre_first_delta_text) - overlap_len
                                        prefix_to_emit = pre_first_delta_text[:prefix_len]

                                        if prefix_to_emit.strip():
                                            await streaming_callback(prefix_to_emit)
                                            seeded_prefix_sent = True
                                            preview_msg = (
                                                f"[src] seeded_prefix overlap={overlap_len} "
                                                f"len={len(prefix_to_emit)} "
                                                f"preview={repr(prefix_to_emit[:20])}"
                                            )
                                            state_manager.session._debug_events.append(preview_msg)
                                        else:
                                            skip_msg = (
                                                f"[src] seed_skip overlap={overlap_len} "
                                                f"delta_len={len(delta_text)} "
                                                f"pre_len={len(pre_first_delta_text)}"
                                            )
                                            state_manager.session._debug_events.append(skip_msg)
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
                                chunk_preview = repr(
                                    event.delta.content_delta[:5]
                                    if event.delta.content_delta
                                    else ""
                                )
                                chunk_len = len(event.delta.content_delta or "")
                                delta_msg = (
                                    f"[src] first_delta_received ts_ns={ts_ns} "
                                    f"chunk_repr={chunk_preview} len={chunk_len}"
                                )
                                state_manager.session._debug_events.append(delta_msg)
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
                            final_msg = (
                                f"[src] final_text_preview len={len(final_text)} "
                                f"preview={repr(final_text[:20])}"
                            )
                            state_manager.session._debug_events.append(final_msg)
                    except Exception:
                        pass
            stream_elapsed_ms = (time.perf_counter() - stream_start) * 1000
            logger.lifecycle(f"Stream: {debug_event_count} events, {stream_elapsed_ms:.0f}ms")
    except Exception as e:
        # Reset node state to allow graceful degradation to non-streaming mode
        logger.warning(f"Stream failed, falling back to non-streaming: {e}")
        logger.lifecycle(f"Stream failed: {type(e).__name__}")
        try:
            if hasattr(node, "_did_stream"):
                node._did_stream = False
        except Exception:
            pass
