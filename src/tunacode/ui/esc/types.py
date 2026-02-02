"""Protocols for ESC handler dependencies."""

from __future__ import annotations

import asyncio
from typing import Protocol, TypeAlias

RequestTask: TypeAlias = asyncio.Task[object]


class ShellRunnerProtocol(Protocol):
    """Protocol for shell cancellation dependencies."""

    def is_running(self) -> bool: ...

    def cancel(self) -> None: ...


class EditorProtocol(Protocol):
    """Protocol for editor input dependencies."""

    value: str
    has_paste_buffer: bool

    def clear_input(self) -> None: ...
