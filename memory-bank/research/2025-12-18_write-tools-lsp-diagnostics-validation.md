# Research - Write Tools and LSP Diagnostics Pipeline Validation

**Date:** 2025-12-18
**Owner:** Agent
**Phase:** Research
**Source Document:** `.claude/metadata/write-tools-lsp-diagnostics-analysis.md`

## Goal

Validate the claims made in the deep-dive analysis document regarding freeze/timeout risks in the write_file/update_file pipeline and LSP diagnostics failure points. All findings are confirmed with specific code evidence and line numbers.

## Summary of Validation Results

| Claim | Status | Severity | Evidence Location |
|-------|--------|----------|-------------------|
| `_truncate_diff` only truncates by line count (no width cap) | CONFIRMED | High | `update_file.py:102-113` |
| Confirmation preview computes full diff BEFORE truncation | CONFIRMED | Medium | `requests.py:94-104` |
| Fuzzy matching uses CPU-heavy Levenshtein algorithm | CONFIRMED | Medium | `text_match.py:24-51,216,248` |
| LSP `_receive_one` assumes single header line | CONFIRMED | High | `client.py:216-227` |
| `get_server_command` no subcommand validation | CONFIRMED | Medium | `servers.py:97-99` |
| `_get_lsp_diagnostics` silent timeout | CONFIRMED | Medium | `decorators.py:79-81` |
| LSP diagnostics vulnerable to truncation | CONFIRMED | High | `repl_support.py:136-142` |

---

## Findings

### 1. Write Tool Pipeline Vulnerabilities

#### 1.1 update_file Renderer Lacks Line Width Cap

**File:** [`src/tunacode/ui/renderers/tools/update_file.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/ui/renderers/tools/update_file.py#L102-L113)

```python
def _truncate_diff(diff: str) -> tuple[str, int, int]:
    """Truncate diff content, return (truncated, shown, total)."""
    lines = diff.splitlines()
    total = len(lines)
    max_content = TOOL_VIEWPORT_LINES  # 26 lines
    if total <= max_content:
        return diff, total, total
    truncated = lines[:max_content]
    return "\n".join(truncated), max_content, total
```

**Problem:** Uses `TOOL_VIEWPORT_LINES` (26) for line count but NO character limit per line. For minified/base64 content producing single massive lines, Rich Syntax receives the full line content.

**Risk:** UI freeze when rendering massive single-line diffs through Rich Syntax with `word_wrap=True`.

#### 1.2 Confirmation Preview: Full Diff Before Truncation

**File:** [`src/tunacode/tools/authorization/requests.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/tools/authorization/requests.py#L83-L107)

```python
# Lines 88-92: Reads ENTIRE file and computes full replacement
with open(filepath, encoding="utf-8") as f:
    original = f.read()
new_content = replace(original, target, patch, replace_all=False)

# Lines 94-100: Generates COMPLETE unified diff
diff_lines = list(
    difflib.unified_diff(
        original.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        ...
    )
)
# Line 104: THEN truncates
diff_preview_lines, truncated = _preview_lines(raw_diff)
```

**Problem:** Full file read + full replacement + full diff generation happens BEFORE any truncation is applied.

**Risk:** CPU stall on UI event loop for large files before preview even appears.

#### 1.3 Fuzzy Matching CPU Load

**File:** [`src/tunacode/tools/utils/text_match.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/tools/utils/text_match.py#L24-L51)

```python
def levenshtein(a: str, b: str) -> int:
    matrix = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]  # O(m*n) space
    for i in range(1, len(a) + 1):      # O(m) outer
        for j in range(1, len(b) + 1):  # O(n) inner
            ...
```

**Complexity:** O(m * n) time and space. Called per middle line per candidate block in `block_anchor_replacer` (lines 216, 248).

**Risk:** For large files with multiple fuzzy match candidates, this compounds with preview generation.

---

### 2. LSP Diagnostics Pipeline Vulnerabilities

#### 2.1 Single Header Line Assumption

**File:** [`src/tunacode/lsp/client.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/lsp/client.py#L205-L236)

```python
async def _receive_one(self) -> dict[str, Any] | None:
    # Line 216: Reads ONE header
    header_line = await asyncio.wait_for(self.process.stdout.readline(), timeout=0.5)
    ...
    if not header.startswith("Content-Length:"):
        return None  # Line 221: Rejects if not Content-Length
    ...
    # Line 227: Reads ONE blank line (assumes next line is separator)
    await self.process.stdout.readline()
```

**Problem:** If LSP server sends `Content-Type` header after `Content-Length`, the code reads `Content-Type` as the blank separator line, causing stream desync.

**Impact:** TypeScript servers commonly send multiple headers; diagnostics silently fail.

#### 2.2 No Subcommand Validation

**File:** [`src/tunacode/lsp/servers.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/lsp/servers.py#L77-L101)

```python
def get_server_command(path: Path) -> list[str] | None:
    for command in command_options:
        binary = command[0]
        if which(binary) is not None:  # Only checks binary exists
            return command  # Returns full command without validation
```

**Problem:** `which("ruff")` succeeds even if `ruff server --stdio` isn't supported. Stderr is redirected to DEVNULL in `LSPClient.start()`.

**Impact:** Old ruff versions fail silently, no diagnostics appear.

#### 2.3 Silent Timeout Behavior

**File:** [`src/tunacode/tools/decorators.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/tools/decorators.py#L57-L84)

```python
async def _get_lsp_diagnostics(filepath: str) -> str:
    try:
        timeout = config.get("timeout", 5.0)
        diagnostics = await asyncio.wait_for(
            get_diagnostics(Path(filepath), timeout=timeout),
            timeout=timeout + LSP_ORCHESTRATION_OVERHEAD_SECONDS,  # 6.0s total
        )
        return format_diagnostics(diagnostics)
    except TimeoutError:
        logger.debug("LSP diagnostics timed out for %s", filepath)  # Debug only
        return ""  # Silent empty return
```

**Problem:** Timeout returns empty string with only debug-level logging. User sees no indication diagnostics were attempted.

#### 2.4 Diagnostics Truncation Vulnerability (CRITICAL)

**Data Flow:**
```text
update_file() returns diff (potentially 55KB)
    ↓
@file_tool decorator appends diagnostics XML (57KB total)
    ↓
_truncate_for_safety() cuts at 50,000 chars
    ↓
Diagnostics XML block is LOST (appended at end)
```

**Files involved:**
- [`decorators.py:188`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/tools/decorators.py#L188): `result = f"{result}\n\n{diagnostics_output}"` (append at end)
- [`repl_support.py:142`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/ui/repl_support.py#L142): `return content[:MAX_CALLBACK_CONTENT]` (hard truncate)
- [`diagnostics.py:179`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/ui/renderers/tools/diagnostics.py#L179): Regex requires complete `</file_diagnostics>` tag

**Impact:** Large refactors lose all type error visibility. Agent continues without knowing about introduced errors.

---

### 3. Truncation Constants Reference

**File:** [`src/tunacode/constants.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/constants.py)

| Constant | Value | Location | Purpose |
|----------|-------|----------|---------|
| `MAX_CALLBACK_CONTENT` | 50,000 | Line 30 | Emergency safety truncation |
| `MAX_PANEL_LINES` | 30 | Line 31 | Tool result panel line limit |
| `MAX_PANEL_LINE_WIDTH` | 200 | Line 32 | Line width for preview panels |
| `TOOL_VIEWPORT_LINES` | 26 | Line 37 | Viewport sizing (30-4) |
| `MAX_PREVIEW_LINES` | 100 | requests.py:10 | Confirmation dialog limit |
| `MAX_DIAGNOSTICS_COUNT` | 10 | lsp/__init__.py:79 | Max diagnostics to format |

---

## Key Patterns / Solutions Found

- **Confirmation preview:** Multi-layer truncation (chars + lines + line width) in `_preview_lines()`
- **Result rendering:** Only line-count truncation in `_truncate_diff()` - missing width/char caps
- **LSP diagnostics:** Appended LAST to result string, making them first to be cut
- **Replacer strategy:** Ordered from exact to fuzzy (simple -> trimmed -> indent -> Levenshtein)

---

## Knowledge Gaps

1. **Actual freeze reproduction:** No profiling data to confirm which specific path causes the reported freeze
2. **TypeScript LSP testing:** Need verification that multi-header servers cause the described desync
3. **User config impact:** Unknown how many users have non-default LSP timeouts configured
4. **Renderer benchmark:** No timing data on Rich Syntax rendering of massive single-line content

---

## References

### Source Document
- [`.claude/metadata/write-tools-lsp-diagnostics-analysis.md`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/.claude/metadata/write-tools-lsp-diagnostics-analysis.md)

### Core Files Analyzed
- [`src/tunacode/tools/authorization/requests.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/tools/authorization/requests.py)
- [`src/tunacode/ui/repl_support.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/ui/repl_support.py)
- [`src/tunacode/ui/renderers/tools/update_file.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/ui/renderers/tools/update_file.py)
- [`src/tunacode/ui/renderers/tools/diagnostics.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/ui/renderers/tools/diagnostics.py)
- [`src/tunacode/tools/decorators.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/tools/decorators.py)
- [`src/tunacode/tools/utils/text_match.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/tools/utils/text_match.py)
- [`src/tunacode/lsp/client.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/lsp/client.py)
- [`src/tunacode/lsp/servers.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/lsp/servers.py)
- [`src/tunacode/lsp/__init__.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/lsp/__init__.py)
- [`src/tunacode/constants.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/291c385f8ac45ea6df8b76dbf86894f7da4be087/src/tunacode/constants.py)
