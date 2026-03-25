"""Opt-in logging helpers for active-request input-latency investigations."""

from __future__ import annotations

import os
import threading
import time
from typing import TYPE_CHECKING

from tunacode.core.logging import get_logger

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp

INPUT_LATENCY_DEBUG_ENV_VAR = "TUNACODE_INPUT_LATENCY_DEBUG"
FALSEY_ENV_VALUES = frozenset({"", "0", "false", "False", "no", "off", "OFF"})
INPUT_LATENCY_LOG_PREFIX = "[INPUT_LATENCY]"
INPUT_LATENCY_LOG_SOURCE = "ui.input_latency"


def input_latency_debug_enabled() -> bool:
    """Return True when opt-in input latency tracing is enabled."""
    return os.environ.get(INPUT_LATENCY_DEBUG_ENV_VAR, "") not in FALSEY_ENV_VALUES


def log_input_latency(
    event: str,
    *,
    app: TextualReplApp | None = None,
    **fields: object,
) -> None:
    """Emit a structured latency trace line when debugging is enabled."""
    if not input_latency_debug_enabled():
        return

    parts = [f"event={event}"]
    if app is not None:
        origin = getattr(app, "_input_latency_debug_origin", 0.0)
        if origin > 0.0:
            elapsed_ms = (time.monotonic() - origin) * 1000.0
            parts.append(f"t_ms={elapsed_ms:.1f}")
        parts.append(f"thread={threading.get_ident()}")
        parts.append(f"loading={int(getattr(app, '_loading_indicator_shown', False))}")
        parts.append(
            f"request_active={int(getattr(app, '_current_request_task', None) is not None)}"
        )
        editor = getattr(app, "editor", None)
        if editor is not None:
            parts.append(f"draft_len={len(getattr(editor, 'value', ''))}")

    for key, value in fields.items():
        parts.append(f"{key}={_format_field_value(value)}")

    get_logger().info(
        f"{INPUT_LATENCY_LOG_PREFIX} {' '.join(parts)}",
        source=INPUT_LATENCY_LOG_SOURCE,
    )


def _format_field_value(value: object) -> str:
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, float):
        return f"{value:.1f}"
    if value is None:
        return "none"

    normalized = str(value)
    return normalized if " " not in normalized else repr(normalized)
