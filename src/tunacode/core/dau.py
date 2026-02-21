"""Lightweight Daily Active Usage tracker.

Stores per-day session counts in ``~/.tunacode/dau.json``.
Zero external dependencies beyond the stdlib.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tunacode.configuration.paths import get_tunacode_home

DAU_FILE_NAME = "dau.json"
DAU_WINDOW_DAYS = 14


def _dau_path() -> Path:
    return get_tunacode_home() / DAU_FILE_NAME


def _today_key() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _load_counts() -> dict[str, int]:
    path = _dau_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, int)}


def _save_counts(counts: dict[str, int]) -> None:
    path = _dau_path()
    path.write_text(json.dumps(counts, sort_keys=True), encoding="utf-8")


def record_session() -> None:
    """Increment today's session count."""
    counts = _load_counts()
    key = _today_key()
    counts[key] = counts.get(key, 0) + 1

    # Prune entries older than the display window to keep the file small.
    cutoff = (datetime.now(UTC) - timedelta(days=DAU_WINDOW_DAYS)).strftime("%Y-%m-%d")
    pruned = {k: v for k, v in counts.items() if k >= cutoff}

    _save_counts(pruned)


def recent_counts(days: int = DAU_WINDOW_DAYS) -> list[float]:
    """Return per-day session counts for the last *days* days, oldest first.

    Days with no sessions are represented as ``0``.
    """
    counts = _load_counts()
    today = datetime.now(UTC).date()
    return [
        float(counts.get((today - timedelta(days=offset)).strftime("%Y-%m-%d"), 0))
        for offset in range(days - 1, -1, -1)
    ]
