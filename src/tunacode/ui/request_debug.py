"""Low-noise UI/request latency tracing for /debug sessions."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tunacode.core.logging import get_logger

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


KEYPRESS_RENDER_WARN_MS = 125.0
DELTA_TIMER_DRIFT_WARN_MS = 125.0
BRIDGE_BACKLOG_WARN_MS = 200.0
BRIDGE_FLUSH_WARN_MS = 25.0
CALLBACK_WARN_MS = 20.0
POST_STREAM_CLEANUP_WARN_MS = 75.0
RESPONSE_PANEL_WARN_MS = 40.0
RESOURCE_BAR_UPDATE_WARN_MS = 25.0
SAVE_SESSION_WARN_MS = 50.0


@dataclass(frozen=True, slots=True)
class BridgeDrainBatch:
    """Aggregated queue-drain payload for a single UI flush tick."""

    text: str = ""
    chunk_count: int = 0
    char_count: int = 0
    oldest_age_ms: float = 0.0

    @property
    def has_data(self) -> bool:
        return self.chunk_count > 0


@dataclass(slots=True)
class SubmissionTrace:
    """Submit/queue timings for a single user request."""

    sequence_id: int
    submitted_at: float
    raw_char_count: int
    normalized_char_count: int
    enqueued_at: float = 0.0
    submit_to_queue_ms: float | None = None


@dataclass(slots=True)
class _PendingInputProbe:
    started_at: float
    first_key_label: str
    last_key_label: str
    merged_keypresses: int = 1


@dataclass(slots=True)
class _RequestMetrics:
    sequence_id: int
    submit_to_queue_ms: float | None
    queue_to_start_ms: float | None
    submit_to_start_ms: float | None
    keypress_sample_count: int = 0
    keypress_slow_count: int = 0
    max_keypress_to_refresh_ms: float = 0.0
    delta_timer_sample_count: int = 0
    delta_timer_drift_warn_count: int = 0
    max_delta_timer_drift_ms: float = 0.0
    bridge_flush_count: int = 0
    bridge_flush_warn_count: int = 0
    max_bridge_backlog_ms: float = 0.0
    max_bridge_flush_ms: float = 0.0
    max_stream_callback_ms: float = 0.0
    max_thinking_callback_ms: float = 0.0
    stream_batches: int = 0
    stream_chunks: int = 0
    stream_chars: int = 0
    thinking_batches: int = 0
    thinking_chunks: int = 0
    thinking_chars: int = 0
    worker_ms: float = 0.0
    final_flush_ms: float = 0.0
    response_panel_ms: float = 0.0
    response_chars: int = 0
    resource_bar_update_ms: float = 0.0
    save_session_ms: float = 0.0
    message_count: int = 0
    post_stream_cleanup_ms: float = 0.0


def build_request_debug_thresholds_message() -> str:
    """Describe the /debug warning thresholds shown to operators."""

    return (
        "UI: "
        "thresholds "
        f"keypress={KEYPRESS_RENDER_WARN_MS:.0f}ms "
        f"timer_drift={DELTA_TIMER_DRIFT_WARN_MS:.0f}ms "
        f"bridge_backlog={BRIDGE_BACKLOG_WARN_MS:.0f}ms "
        f"bridge_flush={BRIDGE_FLUSH_WARN_MS:.0f}ms "
        f"callbacks={CALLBACK_WARN_MS:.0f}ms "
        f"response_panel={RESPONSE_PANEL_WARN_MS:.0f}ms "
        f"resource_bar={RESOURCE_BAR_UPDATE_WARN_MS:.0f}ms "
        f"save_session={SAVE_SESSION_WARN_MS:.0f}ms "
        f"post_stream={POST_STREAM_CLEANUP_WARN_MS:.0f}ms"
    )


class RequestDebugTracer:
    """Track request/input timings and emit lifecycle traces only in debug mode."""

    def __init__(self, app: TextualReplApp) -> None:
        self._app = app
        self._next_submission_sequence = 1
        self._pending_submission_traces: deque[SubmissionTrace] = deque()
        self._pending_input_probe: _PendingInputProbe | None = None
        self._active_request_metrics: _RequestMetrics | None = None
        self._loading_visible_since: float = 0.0
        self._last_loading_visible_ms: float = 0.0
        self._next_delta_flush_due_at: float = 0.0

    def submit_received(self, *, raw_text: str, normalized_text: str) -> SubmissionTrace | None:
        if not self._enabled:
            return None

        trace = SubmissionTrace(
            sequence_id=self._next_submission_sequence,
            submitted_at=time.monotonic(),
            raw_char_count=len(raw_text),
            normalized_char_count=len(normalized_text),
        )
        self._next_submission_sequence += 1
        self._emit(
            "Input: "
            f"submit seq={trace.sequence_id} "
            f"raw_chars={trace.raw_char_count} "
            f"normalized_chars={trace.normalized_char_count} "
            f"queue={self._queue_size()}"
        )
        return trace

    def request_enqueued_after_refresh(self, trace: SubmissionTrace | None) -> None:
        if trace is None or not self._enabled:
            return

        trace.enqueued_at = time.monotonic()
        trace.submit_to_queue_ms = self._elapsed_ms(trace.submitted_at, trace.enqueued_at)
        self._pending_submission_traces.append(trace)
        self._emit(
            "Queue: "
            f"seq={trace.sequence_id} "
            f"submit_to_enqueue={trace.submit_to_queue_ms:.1f}ms "
            f"queue={self._queue_size()}"
        )

    def pop_next_submission_trace(self) -> SubmissionTrace | None:
        if not self._pending_submission_traces:
            return None
        return self._pending_submission_traces.popleft()

    def request_started(self, trace: SubmissionTrace | None) -> None:
        if not self._enabled:
            return

        now = time.monotonic()
        submit_to_start_ms = (
            self._elapsed_ms(trace.submitted_at, now) if trace is not None else None
        )
        queue_to_start_ms = (
            self._elapsed_ms(trace.enqueued_at, now)
            if trace is not None and trace.enqueued_at > 0.0
            else None
        )
        metrics = _RequestMetrics(
            sequence_id=trace.sequence_id if trace is not None else 0,
            submit_to_queue_ms=trace.submit_to_queue_ms if trace is not None else None,
            queue_to_start_ms=queue_to_start_ms,
            submit_to_start_ms=submit_to_start_ms,
        )
        self._active_request_metrics = metrics
        self._emit(
            "Queue: "
            f"seq={metrics.sequence_id} "
            f"enqueue_to_start={self._format_ms(queue_to_start_ms)} "
            f"submit_to_start={self._format_ms(submit_to_start_ms)} "
            f"queue={self._queue_size()}"
        )

    def request_finished(self, *, total_request_ms: float) -> None:
        metrics = self._active_request_metrics
        if metrics is None or not self._enabled:
            self._active_request_metrics = None
            return

        self._emit(
            "UI: "
            f"request_trace seq={metrics.sequence_id} "
            f"request={total_request_ms:.1f}ms "
            f"worker={metrics.worker_ms:.1f}ms "
            f"post_stream={metrics.post_stream_cleanup_ms:.1f}ms "
            f"loading={self._last_loading_visible_ms:.1f}ms "
            f"submit_to_queue={self._format_ms(metrics.submit_to_queue_ms)} "
            f"queue_to_start={self._format_ms(metrics.queue_to_start_ms)} "
            f"final_flush={metrics.final_flush_ms:.1f}ms "
            f"response_panel={metrics.response_panel_ms:.1f}ms "
            f"resource_bar={metrics.resource_bar_update_ms:.1f}ms "
            f"save_session={metrics.save_session_ms:.1f}ms "
            f"keypress_max={metrics.max_keypress_to_refresh_ms:.1f}ms "
            f"keypress_slow={metrics.keypress_slow_count}/{metrics.keypress_sample_count} "
            f"timer_drift_max={metrics.max_delta_timer_drift_ms:.1f}ms "
            f"bridge_backlog_max={metrics.max_bridge_backlog_ms:.1f}ms "
            f"bridge_flush_max={metrics.max_bridge_flush_ms:.1f}ms "
            f"stream_cb_max={metrics.max_stream_callback_ms:.1f}ms "
            f"thinking_cb_max={metrics.max_thinking_callback_ms:.1f}ms"
        )
        self._active_request_metrics = None

    def note_request_worker_completed(self, *, duration_ms: float) -> None:
        metrics = self._active_request_metrics
        if metrics is None or not self._enabled:
            return
        metrics.worker_ms = duration_ms

    def note_post_stream_cleanup(
        self,
        *,
        final_flush_ms: float,
        response_panel_ms: float,
        response_chars: int,
        resource_bar_update_ms: float,
        save_session_ms: float,
        message_count: int,
        total_cleanup_ms: float,
    ) -> None:
        metrics = self._active_request_metrics
        if metrics is None or not self._enabled:
            return

        metrics.final_flush_ms = final_flush_ms
        metrics.response_panel_ms = response_panel_ms
        metrics.response_chars = response_chars
        metrics.resource_bar_update_ms = resource_bar_update_ms
        metrics.save_session_ms = save_session_ms
        metrics.message_count = message_count
        metrics.post_stream_cleanup_ms = total_cleanup_ms

        if not self._should_log_post_stream_cleanup(
            response_panel_ms=response_panel_ms,
            resource_bar_update_ms=resource_bar_update_ms,
            save_session_ms=save_session_ms,
            total_cleanup_ms=total_cleanup_ms,
        ):
            return

        self._emit(
            "UI: "
            f"post_stream seq={metrics.sequence_id} "
            f"total={total_cleanup_ms:.1f}ms "
            f"final_flush={final_flush_ms:.1f}ms "
            f"response_panel={response_panel_ms:.1f}ms "
            f"response_chars={response_chars} "
            f"resource_bar={resource_bar_update_ms:.1f}ms "
            f"save_session={save_session_ms:.1f}ms "
            f"messages={message_count}"
        )

    def loading_shown(self, *, reason: str) -> None:
        if not self._enabled:
            return
        self._loading_visible_since = time.monotonic()
        self._emit(f"UI: loading show reason={reason} queue={self._queue_size()}")

    def loading_hidden(self, *, reason: str) -> None:
        if not self._enabled:
            self._loading_visible_since = 0.0
            self._last_loading_visible_ms = 0.0
            return

        if self._loading_visible_since <= 0.0:
            visible_ms = 0.0
        else:
            visible_ms = self._elapsed_ms(self._loading_visible_since, time.monotonic())
        self._loading_visible_since = 0.0
        self._last_loading_visible_ms = visible_ms
        self._emit(f"UI: loading hide reason={reason} visible={visible_ms:.1f}ms")

    def note_delta_timer_started(self) -> None:
        if not self._enabled:
            self._next_delta_flush_due_at = 0.0
            return
        interval_s = self._delta_flush_interval_s
        self._next_delta_flush_due_at = time.monotonic() + interval_s

    def note_delta_timer_stopped(self) -> None:
        self._next_delta_flush_due_at = 0.0

    def note_delta_timer_tick(self) -> None:
        metrics = self._active_request_metrics
        if metrics is None or not self._enabled:
            return

        expected_at = self._next_delta_flush_due_at
        now = time.monotonic()
        if expected_at > 0.0:
            drift_ms = max(0.0, self._elapsed_ms(expected_at, now))
            metrics.delta_timer_sample_count += 1
            metrics.max_delta_timer_drift_ms = max(metrics.max_delta_timer_drift_ms, drift_ms)
            if drift_ms >= DELTA_TIMER_DRIFT_WARN_MS:
                metrics.delta_timer_drift_warn_count += 1
                self._emit(
                    "UI: "
                    f"delta_timer_drift seq={metrics.sequence_id} "
                    f"drift={drift_ms:.1f}ms "
                    f"queue={self._queue_size()}"
                )
        self._next_delta_flush_due_at = now + self._delta_flush_interval_s

    def note_delta_flush(
        self,
        *,
        stream_batch: BridgeDrainBatch,
        thinking_batch: BridgeDrainBatch,
        flush_duration_ms: float,
        stream_callback_ms: float,
        thinking_callback_ms: float,
    ) -> None:
        metrics = self._active_request_metrics
        if metrics is None or not self._enabled:
            return

        backlog_ms = max(stream_batch.oldest_age_ms, thinking_batch.oldest_age_ms)
        metrics.bridge_flush_count += 1
        metrics.max_bridge_backlog_ms = max(metrics.max_bridge_backlog_ms, backlog_ms)
        metrics.max_bridge_flush_ms = max(metrics.max_bridge_flush_ms, flush_duration_ms)
        metrics.max_stream_callback_ms = max(metrics.max_stream_callback_ms, stream_callback_ms)
        metrics.max_thinking_callback_ms = max(
            metrics.max_thinking_callback_ms, thinking_callback_ms
        )

        if stream_batch.has_data:
            metrics.stream_batches += 1
            metrics.stream_chunks += stream_batch.chunk_count
            metrics.stream_chars += stream_batch.char_count
        if thinking_batch.has_data:
            metrics.thinking_batches += 1
            metrics.thinking_chunks += thinking_batch.chunk_count
            metrics.thinking_chars += thinking_batch.char_count

        if not self._should_log_bridge_flush(
            backlog_ms=backlog_ms,
            flush_duration_ms=flush_duration_ms,
            stream_callback_ms=stream_callback_ms,
            thinking_callback_ms=thinking_callback_ms,
        ):
            return

        metrics.bridge_flush_warn_count += 1
        self._emit(
            "Bridge: "
            f"seq={metrics.sequence_id} "
            f"stream={stream_batch.chunk_count}ch/{stream_batch.char_count}c "
            f"thinking={thinking_batch.chunk_count}ch/{thinking_batch.char_count}c "
            f"backlog={backlog_ms:.1f}ms "
            f"flush={flush_duration_ms:.1f}ms "
            f"stream_cb={stream_callback_ms:.1f}ms "
            f"thinking_cb={thinking_callback_ms:.1f}ms"
        )

    def note_editor_keypress(self, *, key_label: str) -> None:
        if not self._enabled or not self._request_activity_active():
            return

        pending_probe = self._pending_input_probe
        if pending_probe is not None:
            pending_probe.last_key_label = key_label
            pending_probe.merged_keypresses += 1
            return

        probe = _PendingInputProbe(
            started_at=time.monotonic(),
            first_key_label=key_label,
            last_key_label=key_label,
        )
        self._pending_input_probe = probe
        self._app.call_after_refresh(lambda probe=probe: self._complete_input_probe(probe))

    @property
    def _delta_flush_interval_s(self) -> float:
        return self._app.STREAM_THROTTLE_MS / self._app.MILLISECONDS_PER_SECOND

    @property
    def _enabled(self) -> bool:
        return self._app.state_manager.session.debug_mode

    def _complete_input_probe(self, probe: _PendingInputProbe) -> None:
        if self._pending_input_probe is not probe:
            return
        self._pending_input_probe = None

        metrics = self._active_request_metrics
        if metrics is None or not self._enabled:
            return

        elapsed_ms = self._elapsed_ms(probe.started_at, time.monotonic())
        metrics.keypress_sample_count += 1
        metrics.max_keypress_to_refresh_ms = max(metrics.max_keypress_to_refresh_ms, elapsed_ms)
        if elapsed_ms < KEYPRESS_RENDER_WARN_MS:
            return

        metrics.keypress_slow_count += 1
        self._emit(
            "Input: "
            f"keypress_to_refresh seq={metrics.sequence_id} "
            f"elapsed={elapsed_ms:.1f}ms "
            f"first_key={probe.first_key_label} "
            f"last_key={probe.last_key_label} "
            f"merged={probe.merged_keypresses}"
        )

    def _request_activity_active(self) -> bool:
        app = self._app
        return (
            app._loading_indicator_shown
            or app._current_request_task is not None
            or app._request_bridge is not None
            or self._queue_size() > 0
        )

    def _should_log_bridge_flush(
        self,
        *,
        backlog_ms: float,
        flush_duration_ms: float,
        stream_callback_ms: float,
        thinking_callback_ms: float,
    ) -> bool:
        return (
            backlog_ms >= BRIDGE_BACKLOG_WARN_MS
            or flush_duration_ms >= BRIDGE_FLUSH_WARN_MS
            or stream_callback_ms >= CALLBACK_WARN_MS
            or thinking_callback_ms >= CALLBACK_WARN_MS
        )

    def _should_log_post_stream_cleanup(
        self,
        *,
        response_panel_ms: float,
        resource_bar_update_ms: float,
        save_session_ms: float,
        total_cleanup_ms: float,
    ) -> bool:
        return (
            response_panel_ms >= RESPONSE_PANEL_WARN_MS
            or resource_bar_update_ms >= RESOURCE_BAR_UPDATE_WARN_MS
            or save_session_ms >= SAVE_SESSION_WARN_MS
            or total_cleanup_ms >= POST_STREAM_CLEANUP_WARN_MS
        )

    def _queue_size(self) -> int:
        size = self._app.request_queue.qsize()
        return max(0, size) if isinstance(size, int) else 0

    def _emit(self, message: str) -> None:
        get_logger().lifecycle(message)

    @staticmethod
    def _elapsed_ms(started_at: float, ended_at: float) -> float:
        return (ended_at - started_at) * 1000.0

    @staticmethod
    def _format_ms(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value:.1f}ms"
