---
title: Tools Layer
summary: Native tinyagent tool implementations and the helper modules they depend on.
read_when: Adding a tool, changing native tinyagent tool contracts, or tracing helper modules used by the active tools.
depends_on: [types, infrastructure, configuration]
feeds_into: [core]
when_to_read:
  - Adding a tool
  - Changing native tinyagent tool contracts
  - Tracing helper modules used by the active tools
last_updated: "2026-04-04"
---

# Tools Layer

**Package:** `src/tunacode/tools/`

## What

This layer exposes TunaCode's active native tinyagent tool surface directly. The supported tools are `bash`, `discover`, `read_file`, `hashline_edit`, `web_fetch`, and `write_file`.

Each tool module exports a native `AgentTool` with inline JSON-schema parameters plus an `execute(tool_call_id, args, signal, on_update)` implementation. Legacy decorator-based wrapping, XML prompt loading, and compatibility-path tool aliasing are removed, so the runtime and UI preserve the same contract end to end.

## Current Modules

| File | Purpose |
|------|---------|
| `bash.py` | Native tinyagent shell execution tool. |
| `discover.py` | Native tinyagent repository discovery/search tool. |
| `read_file.py` | Native tinyagent file reader that returns hash-tagged lines. |
| `hashline_edit.py` | Native tinyagent edit tool for existing files with hash validation. |
| `web_fetch.py` | Native tinyagent public web fetch tool. |
| `write_file.py` | Native tinyagent file creation tool. |
| `hashline.py` | Hashline parsing and formatting helpers used by file tools. |
| `line_cache.py` | Line cache used to validate read-then-edit flows. |
| `ignore.py` | Ignore-rule access used by discovery and related helpers. |
| `ignore_manager.py` | Ignore stack implementation. |
| `utils/` | Shared discover, ripgrep, formatting, and file-error helpers used by active tools. |
| `cache_accessors/` | Typed cache accessors still used by active tool helpers. |

## Tool Contract Highlights

| Tool | Parameters | Runtime behavior |
|------|------------|------------------|
| `bash` | Required: `command`. Optional: `cwd`, `env`, `timeout`, `capture_output`. | Runs a shell command, validates `timeout` in the `1-600` second range, merges string-only env overrides, and returns formatted command/exit-code/stdout/stderr output with truncation when output exceeds the configured command limit. |
| `discover` | Required: `query`. Optional: `directory`. | Runs the semantic discovery pipeline and returns structured repository context from `DiscoveryReport.to_context()` instead of raw grep-style matches. |
| `read_file` | Required: `filepath`. Optional: `offset`, `limit`. | Reads up to `2000` lines by default, rejects files over `100KB`, truncates displayed lines at `2000` characters, wraps output in `<file>...</file>`, replaces the per-file hashline cache with only the returned window, and normalizes filesystem failures through `tools/utils/file_errors.py`. |
| `hashline_edit` | Required: `filepath`, `operation`. Operation-specific refs: `line`, `start` and `end`, or `after`. Optional: `new`. | Only edits lines present in the current `read_file` cache window, validates `<line>:<hash>` refs, preserves trailing newline state, updates the cache after writes, returns a unified diff, and uses the shared file-error translator for filesystem exceptions. |
| `web_fetch` | Required: `url`. Optional: `timeout`. | Fetches public `http` or `https` content only, blocks localhost/private/reserved targets, re-validates redirect destinations, converts HTML to readable text, caps fetched content at `5MB`, truncates returned text near `100KB`, and returns retryable messages for common HTTP failures. |
| `write_file` | Required: `filepath`, `content`. | Creates a new file only, auto-creates missing parent directories, refuses to overwrite existing files, and uses the shared file-error translator for filesystem exceptions. |

Deep dive: [`hashline-subsystem.md`](hashline-subsystem.md) covers the `read_file` to `hashline_edit` cache contract in detail.

## How

Tool registration is direct:
1. `agent_config.py::_build_tools()` imports native tool objects directly.
2. `agent_config.py::_apply_tool_concurrency_limit()` wraps those native tools with a shared semaphore before they are handed to tinyagent.
3. Each tool module validates its own arguments, checks the abort signal, and implements its own `execute(tool_call_id, args, signal, on_update)` behavior.
4. Tool implementations construct `AgentToolResult` directly and return structured `content` and JSON-serializable `details`.

The file-backed tools (`read_file`, `hashline_edit`, `write_file`) now share `translate_file_tool_errors()` so their retryable and non-retryable filesystem failures stay aligned instead of drifting in three separate `try/except` blocks.

## Why

The tool layer is intentionally direct so TunaCode can preserve native tinyagent tool contracts end to end instead of flattening them through wrappers or alias translation.

That matters most for the safe-edit path: `read_file` establishes the editable cache window, and `hashline_edit` enforces that the model only mutates lines it just read.
