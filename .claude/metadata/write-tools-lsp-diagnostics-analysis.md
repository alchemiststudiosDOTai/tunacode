---
title: Write tools and LSP diagnostics deep dive
link: write-tools-lsp-diagnostics-analysis
type: metadata
ontological_relations:
  - relates_to: [[confirmation-preview-hang-fix]]
  - relates_to: [[kb-claude-code-touchpoints]]
tags:
  - write-file
  - update-file
  - lsp
  - diagnostics
  - tui
  - performance
  - timeout
created_at: 2025-12-19T01:09:02Z
updated_at: 2025-12-19T01:09:02Z
uuid: df1d7bff-223e-4531-bf3f-fa3dc7b9f414
---
# Purpose
Deep dive into the write tool pipeline (write_file/update_file) and the LSP diagnostics flow, with a focus on the reported timeout + TUI freeze and LSP diagnostics appearing broken. This documents the end-to-end paths, the current safety guards, and the remaining risk points.

# Scope and entry points
- write_file tool: `src/tunacode/tools/write_file.py`
- update_file tool: `src/tunacode/tools/update_file.py`
- tool confirmation preview: `src/tunacode/tools/authorization/requests.py`
- tool output safety truncation: `src/tunacode/ui/repl_support.py`
- update_file renderer + diagnostics: `src/tunacode/ui/renderers/tools/update_file.py`, `src/tunacode/ui/renderers/tools/diagnostics.py`
- inline confirmation renderer: `src/tunacode/ui/app.py`
- LSP orchestration: `src/tunacode/tools/decorators.py`, `src/tunacode/lsp/__init__.py`, `src/tunacode/lsp/client.py`, `src/tunacode/lsp/servers.py`
- LSP indicator: `src/tunacode/ui/widgets/resource_bar.py`

# Write tool pipeline (behavioral map)
1) Tool call enters via agent tools list (write_file/update_file are registered with writes=True in `src/tunacode/core/agents/agent_components/agent_config.py`).
2) Pre-execution confirmation preview:
   - Tool handler builds a confirmation request using `ConfirmationRequestFactory` in `src/tunacode/tools/authorization/requests.py`.
   - update_file preview path reads the file, performs the replacement via `replace(...)`, computes a unified diff with `difflib.unified_diff`, then truncates the preview by lines/width in `_preview_lines`.
   - write_file preview path builds a creation diff from content and truncates via `_preview_lines`.
3) Inline confirmation UI renders the preview using Rich Syntax in `TextualReplApp._show_inline_confirmation` in `src/tunacode/ui/app.py`.
4) Tool execution:
   - write_file writes content and returns a short success string in `src/tunacode/tools/write_file.py`.
   - update_file reads, replaces, writes, then returns the full unified diff string in `src/tunacode/tools/update_file.py`.
5) LSP diagnostics (post-write): `file_tool` decorator appends LSP output to the tool result in `src/tunacode/tools/decorators.py`.
6) Tool result is truncated for safety (character cap) in `build_tool_result_callback` in `src/tunacode/ui/repl_support.py`, then sent to UI.
7) Rendering:
   - update_file uses a custom renderer in `src/tunacode/ui/renderers/tools/update_file.py` with a diff Syntax block.
   - write_file uses the generic tool renderer in `src/tunacode/ui/renderers/panels.py`.

# Current safety guards
- Confirmation preview truncation limits:
  - MAX_CALLBACK_CONTENT (chars), MAX_PREVIEW_LINES (lines), MAX_PANEL_LINE_WIDTH (line width) in `src/tunacode/tools/authorization/requests.py` and `src/tunacode/constants.py`.
- Tool result safety truncation:
  - Global cap at MAX_CALLBACK_CONTENT in `src/tunacode/ui/repl_support.py`.
- Generic tool panel truncation:
  - Line count + line width truncation in `_truncate_content` in `src/tunacode/ui/renderers/panels.py`.

# High-risk areas tied to the reported freeze
1) update_file result rendering still allows very long single-line diffs.
   - update_file renderer truncates only by line count in `_truncate_diff` and does not cap line width or total character length.
   - For minified or base64-like single-line edits, the diff remains one massive line (up to MAX_CALLBACK_CONTENT after safety truncation) and is rendered via Rich Syntax.
   - This is a plausible regression path: confirmation preview is now bounded, but the post-tool diff renderer is not.
   - Relevant code: `src/tunacode/ui/renderers/tools/update_file.py`.

2) Confirmation preview for update_file still computes full diff before truncation.
   - The UI safety now truncates the preview string, but the diff is computed over the full file contents first.
   - For large files, `difflib.unified_diff` can be expensive and runs inside the confirmation request creation on the UI event loop.
   - This can look like a timeout or UI stall even if the preview itself is safe.
   - Relevant code: `src/tunacode/tools/authorization/requests.py`.

3) update_file replacement strategy can be CPU-heavy on large files.
   - The `replace(...)` path uses multiple fuzzy match strategies and Levenshtein distance in `src/tunacode/tools/utils/text_match.py`.
   - Worst-case paths are expensive (large content + fuzzy anchors) and are hit twice (preview and actual update).
   - This can contribute to tool timeouts and perceived UI hangs.

# LSP diagnostics pipeline (behavioral map)
1) LSP runs only for write operations via `file_tool(writes=True)` in `src/tunacode/tools/decorators.py`.
2) LSP config resolution merges defaults with user config in `_get_lsp_config` (default enabled True).
3) Diagnostics fetch:
   - `_get_lsp_diagnostics` calls `get_diagnostics` with a timeout, then formats diagnostics into `<file_diagnostics>` XML via `format_diagnostics` in `src/tunacode/lsp/__init__.py`.
4) The formatted diagnostics are appended to the tool result string.
5) update_file renderer strips the `<file_diagnostics>` block and renders diagnostics in a dedicated zone via `parse_diagnostics_block` and `render_diagnostics_inline`.
6) write_file results are handled by the generic renderer and show raw XML text (no special parsing).

# LSP breakpoints that can explain "LSP debug appears broken"
1) Diagnostics block can be truncated out of the tool result.
   - The tool output is hard-truncated to MAX_CALLBACK_CONTENT before rendering.
   - When update_file diffs are large, the LSP block (appended at the end) is likely removed entirely, so no diagnostics appear.
   - Relevant code: `src/tunacode/ui/repl_support.py`, `src/tunacode/ui/renderers/tools/update_file.py`.

2) LSP server detection depends on PATH and version support.
   - `get_server_command` only checks for the binary in PATH; it does not validate that the specific subcommand is supported.
   - Example: `ruff server --stdio` will fail on older ruff versions even if `ruff` exists.
   - This yields silent "no diagnostics" behavior because failures are logged at debug level only.
   - Relevant code: `src/tunacode/lsp/servers.py`, `src/tunacode/lsp/client.py`.

3) LSP client header parsing assumes only one header line.
   - `_receive_one` reads a single header line and assumes the next line is blank.
   - Servers that send Content-Type headers (common in TypeScript servers) will desync parsing and drop messages.
   - This is a likely cause of diagnostics never appearing for some languages.
   - Relevant code: `src/tunacode/lsp/client.py`.

4) Diagnostics timeout may be too short for cold server startup.
   - Default 5s for initialization and diagnostics may be insufficient for large projects or slower servers.
   - When timeouts occur, `_get_lsp_diagnostics` returns empty string and the UI shows nothing.
   - Relevant code: `src/tunacode/tools/decorators.py`, `src/tunacode/lsp/client.py`.

5) LSP indicator can show enabled but no server.
   - Resource bar uses a test .py file to check server availability and may show "LSP: no server" even when LSP is enabled.
   - This is correct but can look like LSP is broken if the server is not installed or not on PATH.
   - Relevant code: `src/tunacode/ui/widgets/resource_bar.py`.

# Why the issues can look related
- update_file for large/minified edits generates huge diffs.
- The confirmation preview is now bounded, but the post-tool diff render is not.
- The result is truncated by character count, which drops the LSP block at the end.
- Net effect: update_file appears to "time out" or "freeze", and LSP diagnostics appear missing.

# Repro-oriented scenarios to validate the hypotheses
1) Large single-line update:
   - update_file a minified JSON or base64 file.
   - Expectation: confirmation preview should render; tool result panel may freeze or lag during diff render.
2) Large file with small target:
   - update_file a large source file with a small patch.
   - Expectation: UI may stall during diff generation in confirmation request.
3) LSP missing due to truncation:
   - update_file a file large enough to trigger MAX_CALLBACK_CONTENT truncation.
   - Expectation: diagnostics block disappears from tool result (no diagnostics rendered).
4) Non-Python LSP:
   - update_file a .ts file if `typescript-language-server` is installed and emits Content-Type headers.
   - Expectation: diagnostics never show due to header parsing assumptions.
5) Older ruff:
   - Run with ruff installed but without `ruff server` support.
   - Expectation: LSP init fails, diagnostics never appear, resource bar may still show LSP enabled.

# Suggested mitigation directions (no code changes made)
- Apply the same bounded preview logic used for confirmation to the update_file result renderer (line width + max chars) so Rich Syntax never sees massive single-line diffs.
- Avoid full diff generation during confirmation for large files; consider bounded diff generation or guardrails before `difflib.unified_diff`.
- Protect LSP diagnostics by reserving space in the truncation strategy or truncating the diff portion first, preserving the diagnostics block.
- Improve LSP client header parsing to handle multi-line headers and Content-Type.
- Surface LSP failures more visibly (current behavior silently returns empty diagnostics).

# Evidence links
- Confirmation preview truncation: `src/tunacode/tools/authorization/requests.py`
- Tool result truncation: `src/tunacode/ui/repl_support.py`
- update_file diff renderer: `src/tunacode/ui/renderers/tools/update_file.py`
- LSP fetch + formatting: `src/tunacode/tools/decorators.py`, `src/tunacode/lsp/__init__.py`
- LSP client parsing: `src/tunacode/lsp/client.py`
- LSP server selection: `src/tunacode/lsp/servers.py`
