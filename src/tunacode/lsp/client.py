"""Minimal LSP client for diagnostic feedback.

Implements just enough of the Language Server Protocol to:
1. Initialize a language server
2. Open a document
3. Receive publishDiagnostics notifications
"""

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tunacode.lsp.servers import get_language_id

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 5.0


@dataclass
class Diagnostic:
    """A single diagnostic from a language server."""

    line: int
    character: int
    message: str
    severity: str  # "error", "warning", "info", "hint"
    source: str | None = None


class LSPClient:
    """Minimal LSP client for diagnostic feedback.

    Communicates with language servers via JSON-RPC over stdin/stdout.
    Uses a single reader task to avoid concurrent stream access.
    """

    def __init__(self, command: list[str], root: Path):
        """Initialize the LSP client.

        Args:
            command: Server command to execute (e.g., ["pyright-langserver", "--stdio"])
            root: Project root directory
        """
        self.command = command
        self.root = root
        self.process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._diagnostics: dict[str, list[Diagnostic]] = {}
        self._initialized = False
        self._reader_task: asyncio.Task[None] | None = None
        self._pending_requests: dict[int, asyncio.Future[dict[str, Any] | None]] = {}
        self._shutdown_requested = False

    async def start(self) -> bool:
        """Start the language server process and initialize.

        Returns:
            True if server started successfully, False otherwise
        """
        try:
            self.process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=self.root,
            )
        except (FileNotFoundError, PermissionError) as e:
            logger.debug("Failed to start LSP server %s: %s", self.command[0], e)
            return False

        # Start the single reader task
        self._reader_task = asyncio.create_task(self._read_messages())

        try:
            await asyncio.wait_for(self._initialize(), timeout=DEFAULT_TIMEOUT)
            self._initialized = True
            return True
        except TimeoutError:
            logger.debug("LSP server %s initialization timed out", self.command[0])
            await self.shutdown()
            return False
        except Exception as e:
            logger.debug("LSP server %s initialization failed: %s", self.command[0], e)
            await self.shutdown()
            return False

    async def _initialize(self) -> None:
        """Send initialize request and wait for response."""
        response = await self._request(
            "initialize",
            {
                "processId": None,
                "rootUri": f"file://{self.root}",
                "capabilities": {
                    "textDocument": {
                        "publishDiagnostics": {
                            "relatedInformation": False,
                        }
                    }
                },
            },
        )

        if response is None:
            raise RuntimeError("No initialize response")

        # Send initialized notification
        await self._notify("initialized", {})

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Send a JSON-RPC request and wait for response.

        Args:
            method: LSP method name
            params: Method parameters

        Returns:
            Response result or None
        """
        self._request_id += 1
        request_id = self._request_id

        # Create a future to receive the response
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any] | None] = loop.create_future()
        self._pending_requests[request_id] = future

        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        try:
            await self._send(message)
            return await asyncio.wait_for(future, timeout=DEFAULT_TIMEOUT)
        except TimeoutError:
            return None
        finally:
            self._pending_requests.pop(request_id, None)

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected).

        Args:
            method: LSP method name
            params: Method parameters
        """
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        await self._send(message)

    async def _send(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC message to the server.

        Args:
            message: Message dictionary to send
        """
        if self.process is None or self.process.stdin is None:
            return

        body = json.dumps(message, ensure_ascii=False)
        body_bytes = body.encode("utf-8")
        header = f"Content-Length: {len(body_bytes)}\r\n\r\n".encode("ascii")
        data = header + body_bytes

        self.process.stdin.write(data)
        await self.process.stdin.drain()

    async def _read_messages(self) -> None:
        """Single reader task that processes all incoming messages."""
        while not self._shutdown_requested:
            if self.process is None or self.process.stdout is None:
                break
            if self.process.returncode is not None:
                break

            message = await self._receive_one()
            if message is None:
                continue

            # Check if this is a response to a pending request
            msg_id = message.get("id")
            if msg_id is not None and msg_id in self._pending_requests:
                future = self._pending_requests.get(msg_id)
                if future and not future.done():
                    future.set_result(message.get("result"))
                continue

            # Handle notifications
            method = message.get("method")
            if method == "textDocument/publishDiagnostics":
                self._handle_diagnostics(message.get("params", {}))

    async def _receive_one(self) -> dict[str, Any] | None:
        """Receive a single JSON-RPC message.

        Returns:
            Parsed message or None
        """
        if self.process is None or self.process.stdout is None:
            return None

        try:
            # Read Content-Length header
            header_line = await asyncio.wait_for(self.process.stdout.readline(), timeout=0.5)
            if not header_line:
                return None

            header = header_line.decode("utf-8").strip()
            if not header.startswith("Content-Length:"):
                return None

            content_length = int(header.split(":")[1].strip())

            # Read blank line
            await self.process.stdout.readline()

            # Read body
            body = await asyncio.wait_for(
                self.process.stdout.readexactly(content_length), timeout=5.0
            )
            return json.loads(body.decode("utf-8"))

        except (TimeoutError, asyncio.IncompleteReadError, json.JSONDecodeError):
            return None

    def _handle_diagnostics(self, params: dict[str, Any]) -> None:
        """Handle publishDiagnostics notification.

        Args:
            params: Notification parameters containing uri and diagnostics
        """
        uri = params.get("uri", "")
        raw_diagnostics = params.get("diagnostics", [])

        severity_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}

        diagnostics: list[Diagnostic] = []
        for raw in raw_diagnostics:
            range_data = raw.get("range", {})
            start = range_data.get("start", {})

            diagnostics.append(
                Diagnostic(
                    line=start.get("line", 0) + 1,  # LSP is 0-indexed
                    character=start.get("character", 0),
                    message=raw.get("message", ""),
                    severity=severity_map.get(raw.get("severity", 1), "error"),
                    source=raw.get("source"),
                )
            )

        self._diagnostics[uri] = diagnostics

    async def open_file(self, path: Path) -> None:
        """Open a file in the language server.

        Args:
            path: Path to the file to open
        """
        if not self._initialized:
            return

        content = path.read_text(encoding="utf-8")
        language_id = get_language_id(path) or "plaintext"

        await self._notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": f"file://{path}",
                    "languageId": language_id,
                    "version": 1,
                    "text": content,
                }
            },
        )

    async def get_diagnostics(
        self, path: Path, timeout: float = DEFAULT_TIMEOUT
    ) -> list[Diagnostic]:
        """Get diagnostics for a file.

        Opens the file and waits for diagnostics to be published.

        Args:
            path: Path to the file
            timeout: Maximum time to wait for diagnostics

        Returns:
            List of diagnostics
        """
        uri = f"file://{path}"

        # Clear any existing diagnostics for this file
        self._diagnostics.pop(uri, None)

        # Open the file
        await self.open_file(path)

        # Wait for diagnostics
        loop = asyncio.get_running_loop()
        start = loop.time()
        while (loop.time() - start) < timeout:
            if uri in self._diagnostics:
                return self._diagnostics[uri]
            await asyncio.sleep(0.1)

        return []

    async def shutdown(self) -> None:
        """Shutdown the language server."""
        self._shutdown_requested = True

        # Cancel any pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.set_result(None)
        self._pending_requests.clear()

        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task

        if self.process is not None:
            try:
                await self._notify("shutdown", {})
                await self._notify("exit", {})
            except Exception:
                pass

            if self.process.returncode is None:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                except TimeoutError:
                    self.process.kill()

        self.process = None
        self._initialized = False
