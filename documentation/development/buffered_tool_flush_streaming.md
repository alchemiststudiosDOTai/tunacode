# Buffered Tool Flush – Streaming Retry Investigation

## Summary (2025-09-18)
- Introduced `ToolFlushCoordinator` + `ToolExecutionValidator` to serialize buffer flushing and synthesize orphaned returns before every provider request.
- `_maybe_stream_node_tokens()` now invokes the coordinator for both streaming and non-streaming paths; `stream_model_request_node()` proactively validates before opening the stream.
- Characterization coverage updated: `tests/characterization/agent/test_streaming.py` asserts coordinator hooks fire for both pre-request validation and retry flushes; existing process-request tests target the coordinator as well.
- Prior fixes (direct calls to `flush_buffered_read_only_tools()`) are retained for backward compatibility but routed through the coordinator, eliminating the `tool_call_ids did not have response messages` failure.

## Resolution Notes
- Coordinator enforces an async lock so retries, streaming fallbacks, and end-of-run flushes cannot race each other.
- Validator backfills synthetic `tool-return` parts via `patch_tool_messages()` when orphaned calls are detected, guaranteeing API contract compliance even if a tool fails silently.
- Remaining work: monitor telemetry for the new coordinator (pending metrics wiring) and verify performance impact once end-to-end load tests are available.

_Last updated: 2025-09-18 (Codex)_
