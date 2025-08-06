"""Utilities for handling abortable streaming."""

import asyncio
import contextlib
from typing import Any, AsyncIterator, Protocol


class StreamProtocol(Protocol):
    """Protocol for stream-like objects."""

    def __aiter__(self) -> AsyncIterator[Any]: ...

    async def __anext__(self) -> Any: ...


class AbortableStream:
    """Wrapper that makes any async stream abortable by exposing transport close methods."""

    def __init__(self, inner: StreamProtocol):
        """Initialize with an inner stream to wrap.

        Args:
            inner: The stream to make abortable (e.g., pydantic-ai StreamedResponse)
        """
        self._inner = inner
        # Try to find abort/close methods on the stream
        self._abort = getattr(inner, "abort", None)
        self._aclose = getattr(inner, "aclose", None)
        # Try to find the underlying HTTP response
        self._resp = getattr(inner, "response", None) or getattr(inner, "_response", None)
        # Try to find the underlying client
        self._client = getattr(inner, "_client", None)

    def __aiter__(self) -> "AbortableStream":
        """Return self as the async iterator."""
        return self

    async def __anext__(self) -> Any:
        """Get next item from the inner stream."""
        return await self._inner.__anext__()

    async def aclose(self) -> None:
        """Close the stream and underlying transport if possible.

        Tries multiple approaches to close the stream:
        1. Call abort() if available
        2. Call aclose() if available
        3. Close underlying HTTP response if accessible
        4. Close underlying client if accessible
        """
        # Try abort method first (highest priority)
        if callable(self._abort):
            try:
                result = self._abort()
                if asyncio.iscoroutine(result):
                    await result
                return
            except Exception:
                pass

        # Try aclose method
        if callable(self._aclose):
            try:
                await self._aclose()
                return
            except Exception:
                pass

        # Try to close underlying HTTP response
        if self._resp is not None and hasattr(self._resp, "aclose"):
            try:
                await self._resp.aclose()
                return
            except Exception:
                pass

        # Try to close underlying client
        if self._client is not None and hasattr(self._client, "aclose"):
            try:
                await self._client.aclose()
                return
            except Exception:
                pass

        # If nothing worked, that's ok - we tried our best


async def stream_worker(
    gen_id: int, make_stream, write_callback, state_manager, logger=None
) -> None:
    """Worker task for streaming that can be cancelled cleanly.

    Args:
        gen_id: Generation ID for this streaming session
        make_stream: Async callable that creates the stream
        write_callback: Async callable to write chunks
        state_manager: State manager for checking generation
        logger: Optional logger
    """
    stream = None
    try:
        # Create the abortable stream
        inner_stream = await make_stream()
        stream = AbortableStream(inner_stream)

        # Stream until cancelled or generation invalidated
        async for event in stream:
            # Check generation before processing
            if not state_manager.is_current(gen_id):
                if logger:
                    logger.debug(f"Generation {gen_id} invalidated, stopping stream worker")
                break

            # Write the event
            await write_callback(event)

            # Check generation after processing
            if not state_manager.is_current(gen_id):
                if logger:
                    logger.debug(f"Generation {gen_id} invalidated after write, stopping")
                break

    except StopAsyncIteration:
        # Normal end of stream
        if logger:
            logger.debug("Stream ended normally")
    except asyncio.CancelledError:
        # Task was cancelled - this is expected
        if logger:
            logger.debug("Stream worker cancelled")
    except Exception as e:
        # Unexpected error
        if logger:
            logger.error(f"Stream worker error: {e}", exc_info=True)
        raise
    finally:
        # Always try to close the stream, even if cancelled
        if stream:
            with contextlib.suppress(Exception):
                # Use shield to ensure close completes even if cancelled
                await asyncio.shield(stream.aclose())
                if logger:
                    logger.debug("Stream closed in finally block")
