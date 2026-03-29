"""Unit tests for JSONL RPC transport framing."""

from __future__ import annotations

from io import StringIO

import pytest

from tunacode.ui.rpc.transport import JsonRpcTransport


@pytest.mark.asyncio
async def test_transport_reads_crlf_delimited_json() -> None:
    transport = JsonRpcTransport(input_stream=StringIO('{"command":"get_state"}\r\n'))

    payload = await transport.read_payload()

    assert payload == {"command": "get_state"}


@pytest.mark.asyncio
async def test_transport_writes_compact_jsonl() -> None:
    output = StringIO()
    transport = JsonRpcTransport(output_stream=output)

    await transport.write({"id": "1", "type": "response", "success": True})

    assert output.getvalue() == '{"id":"1","type":"response","success":true}\n'
