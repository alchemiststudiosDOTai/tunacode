"""LF-delimited JSON transport for TunaCode RPC mode."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, TextIO


class JsonRpcTransport:
    """Read JSONL commands from stdin and write JSONL responses/events to stdout."""

    def __init__(
        self,
        *,
        input_stream: TextIO | None = None,
        output_stream: TextIO | None = None,
        error_stream: TextIO | None = None,
    ) -> None:
        self._input = sys.stdin if input_stream is None else input_stream
        self._output = sys.stdout if output_stream is None else output_stream
        self._error = sys.stderr if error_stream is None else error_stream
        self._write_lock = asyncio.Lock()

    async def read_payload(self) -> Any | None:
        """Read and decode one JSONL command payload."""
        line = await asyncio.to_thread(self._input.readline)
        if line == "":
            return None

        normalized_line = line.rstrip("\n")
        if normalized_line.endswith("\r"):
            normalized_line = normalized_line[:-1]
        if not normalized_line:
            return {}

        return json.loads(normalized_line)

    async def write(self, payload: dict[str, Any]) -> None:
        """Write one compact JSON object followed by LF."""
        serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        async with self._write_lock:
            self._output.write(serialized)
            self._output.write("\n")
            self._output.flush()

    def write_diagnostic(self, message: str) -> None:
        """Write non-protocol diagnostics to stderr."""
        self._error.write(message.rstrip("\n"))
        self._error.write("\n")
        self._error.flush()
