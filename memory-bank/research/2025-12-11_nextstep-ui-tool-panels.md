# Research - NeXTSTEP UI Zoned Layout for Tool Panels (Issue #163)

**Date:** 2025-12-11
**Owner:** agent
**Phase:** Research
**Issue:** https://github.com/alchemiststudiosDOTai/tunacode/issues/163

## Goal

Map the current state of tool renderers against issue #163 deliverables to identify exactly what work is needed to close the issue.

## Findings

### Reference Implementation

`src/tunacode/ui/renderers/tools/list_dir.py` establishes the NeXTSTEP zoned pattern:

| Zone | Purpose | Implementation |
|------|---------|----------------|
| Header | Tool-specific context (directory path + counts) | Lines 124-127 |
| Parameters | Key args as `key: value` pairs | Lines 129-137 |
| Viewport | Primary content with tree connectors | Lines 141-145 |
| Status | Metrics, truncation, duration | Lines 147-156 |

Visual elements used:
- Box drawing separators: `BOX_HORIZONTAL = "─"` (width 52)
- Rich `Panel` with success-colored border
- `Group` to compose zones vertically
- Timestamp in subtitle

### Current Renderer State

| Tool | Renderer | Status | Gap |
|------|----------|--------|-----|
| `list_dir` | `tools/list_dir.py` | COMPLETE | Reference implementation |
| `grep` | `search.py` via `tool_panel_smart()` | PARTIAL | Needs NeXTSTEP zoning |
| `glob` | `search.py` via `tool_panel_smart()` | PARTIAL | Needs NeXTSTEP zoning |
| `update_file` | `render_diff_tool()` in `panels.py` | PARTIAL | Needs NeXTSTEP zoning |
| `read_file` | Default `render_tool()` | MISSING | Needs new renderer |
| `bash` | Default `render_tool()` | MISSING | Needs new renderer |
| `web_fetch` | Default `render_tool()` | MISSING | Needs new renderer |

### Relevant Files & Why They Matter

| File | Purpose |
|------|---------|
| `src/tunacode/ui/renderers/tools/list_dir.py` | Reference implementation for zoned layout |
| `src/tunacode/ui/renderers/tools/__init__.py` | Exports tool renderers (add new exports here) |
| `src/tunacode/ui/renderers/panels.py:476-519` | Dispatcher `tool_panel_smart()` - register new renderers here |
| `src/tunacode/ui/renderers/search.py` | Current grep/glob renderer (may be refactored) |
| `src/tunacode/constants.py` | `MAX_PANEL_LINES=30`, `MAX_PANEL_LINE_WIDTH=200`, `UI_COLORS` |
| `src/tunacode/tools/grep.py` | Grep output format with strategy header |
| `src/tunacode/tools/glob.py` | Glob output: source header + file list |
| `src/tunacode/tools/read_file.py` | Read output: `<file>` tags with line numbers |
| `src/tunacode/tools/update_file.py` | Update output: success message + unified diff |
| `src/tunacode/tools/bash.py` | Bash output: Command, Exit Code, CWD, STDOUT, STDERR |
| `src/tunacode/tools/web_fetch.py` | Web fetch output: plain text from HTML conversion |

### Tool Output Formats (for Parsing)

**grep:**
```
Strategy: ripgrep | Candidates: 123 files | Found 5 matches
file.py:
  10: matching line content
  25: another match
```

**glob:**
```
[source:index|filesystem]
Found N file(s) matching pattern: <pattern>

/path/to/file1.py
/path/to/file2.py
(truncated at N)
```

**read_file:**
```
<file>
1: first line
2: second line
...
(File has more lines. Use 'offset'...)
</file>
```

**update_file:**
```
File 'filepath' updated successfully.

--- a/filepath
+++ b/filepath
@@ -1,3 +1,4 @@
 context
-old line
+new line
```

**bash:**
```
Command: <command>
Exit Code: <code>
Working Directory: <cwd>

STDOUT:
<output>

STDERR:
<errors>
```

**web_fetch:**
Plain text content (converted from HTML via html2text), may include truncation marker.

## Key Patterns / Solutions Found

**Dispatcher Pattern:** `tool_panel_smart()` at `panels.py:476-519` uses if-chain to route tool names to renderers. New renderers add a conditional block here.

**Parser-Renderer Split:** Each renderer has `parse_result()` returning dataclass + `render_*()` returning `RenderableType | None`. Return `None` falls back to default.

**Zone Composition:** Use Rich `Group()` to stack zones: header, params, separator, viewport, separator, status.

**Truncation:** Apply `_truncate_line()` (200 char) and `_truncate_tree()` (30 lines) from constants.

## Deliverables Checklist

To close issue #163, create these files in `src/tunacode/ui/renderers/tools/`:

| File | Zones | Key Elements |
|------|-------|--------------|
| `grep.py` | Header: pattern + match count, Params: path/type/mode, Viewport: grouped results, Status: strategy + duration | File grouping with match context |
| `glob.py` | Header: pattern + count, Params: path/source, Viewport: file list, Status: truncation + duration | Pattern matched, count summary |
| `read_file.py` | Header: file path + line range, Params: offset/limit, Viewport: numbered content, Status: truncation + duration | Line numbers, path header |
| `update_file.py` | Header: file path, Params: operation, Viewport: diff with syntax, Status: lines changed + duration | Before/after context |
| `bash.py` | Header: command (truncated), Params: timeout/cwd, Viewport: stdout/stderr, Status: exit code + duration | Exit code prominent |
| `web_fetch.py` | Header: URL, Params: method/timeout, Viewport: content preview, Status: status code + duration | URL header, content preview |

Integration steps for each:
1. Create `tools/{name}.py` with `parse_result()` and `render_{name}()`
2. Add export to `tools/__init__.py`
3. Add conditional in `tool_panel_smart()` at `panels.py`

## Knowledge Gaps

- Should existing `search.py` renderer be refactored or replaced for grep/glob?
- Exact diff syntax highlighting approach for `update_file` (Rich `Syntax`?)
- How to handle very long bash commands in header zone
- Whether `web_fetch` should show HTTP status code (currently not in output)

## References

- Issue: https://github.com/alchemiststudiosDOTai/tunacode/issues/163
- Reference impl: `src/tunacode/ui/renderers/tools/list_dir.py`
- Dispatcher: `src/tunacode/ui/renderers/panels.py:476-519`
- Constants: `src/tunacode/constants.py:31-33`
