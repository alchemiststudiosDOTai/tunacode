# Research – Raw Code Rendering in Tool Output

**Date:** 2026-01-08
**Owner:** agent
**Phase:** Research

## Goal

Investigate why raw code output from tools displays poorly in the TUI and identify what's missing for proper code rendering.

## TL;DR FOR NEXT DEV

**Problem:** Only `update_file` has syntax highlighting. Everything else shows ugly plain text.

**Fix:** Add `rich.syntax.Syntax` with language detection to ALL tools below.

---

## ALL TOOLS THAT NEED PRETTY RENDERING

### MUST FIX - These Show Code/Files

| Tool | Renderer Location | What It Shows | Fix Needed |
|------|-------------------|---------------|------------|
| **`read_file`** | `ui/renderers/tools/read_file.py:157` | File contents | Syntax highlight by file extension |
| **`update_file`** | `ui/renderers/tools/update_file.py:139` | Diff output | **DONE** - already uses `Syntax("diff")` |
| **`write_file`** | NO RENDERER EXISTS | File contents written | Create renderer + syntax highlight |
| **`bash`** | `ui/renderers/tools/bash.py:127-138` | stdout/stderr | Syntax highlight if code-like output |
| **`grep`** | `ui/renderers/tools/grep.py:167` | Code matches with context | Syntax highlight by matched file ext |
| **`glob`** | `ui/renderers/tools/glob.py:160` | File paths list | Style paths nicely (dirs vs files) |
| **`list_dir`** | `ui/renderers/tools/list_dir.py:119` | Directory tree | Style tree (dirs bold, files normal) |
| **`web_fetch`** | `ui/renderers/tools/web_fetch.py:101` | Fetched content | Syntax highlight if code (detect from URL) |
| **`research`** | `ui/renderers/tools/research.py:221` | Code examples + findings | Syntax highlight `code_examples` field |

### Tools (Backend) - Where Output Originates

| Tool | Location | Output Type |
|------|----------|-------------|
| `read_file` | `src/tunacode/tools/read_file.py` | Raw file content in `<file>` tags |
| `write_file` | `src/tunacode/tools/write_file.py` | Confirmation message |
| `update_file` | `src/tunacode/tools/update_file.py` | Diff in `<diff>` tags |
| `bash` | `src/tunacode/tools/bash.py` | stdout + stderr |
| `grep` | `src/tunacode/tools/grep.py` | Matched lines with file:line prefix |
| `glob` | `src/tunacode/tools/glob.py` | File path list |
| `list_dir` | `src/tunacode/tools/list_dir.py` | Tree structure |
| `web_fetch` | `src/tunacode/tools/web_fetch.py` | HTML/text content |

### Renderers (Frontend) - Where Pretty Happens

| Renderer | Location | Current State |
|----------|----------|---------------|
| `ReadFileRenderer` | `ui/renderers/tools/read_file.py` | Plain `Text()` - **NEEDS FIX** |
| `UpdateFileRenderer` | `ui/renderers/tools/update_file.py` | `Syntax("diff")` - **DONE** |
| `BashRenderer` | `ui/renderers/tools/bash.py` | Plain `Text()` - **NEEDS FIX** |
| `GrepRenderer` | `ui/renderers/tools/grep.py` | Plain `Text()` - **NEEDS FIX** |
| `GlobRenderer` | `ui/renderers/tools/glob.py` | Plain `Text()` - **NEEDS FIX** |
| `ListDirRenderer` | `ui/renderers/tools/list_dir.py` | Plain `Text()` - **NEEDS FIX** |
| `WebFetchRenderer` | `ui/renderers/tools/web_fetch.py` | Plain `Text()` - **NEEDS FIX** |
| `ResearchRenderer` | `ui/renderers/tools/research.py` | Plain `Text()` - **NEEDS FIX** |
| `DiagnosticsRenderer` | `ui/renderers/tools/diagnostics.py` | Styled `Text()` - OK for now |
| **`WriteFileRenderer`** | **DOES NOT EXIST** | **NEEDS CREATION** |

---

## Findings

### Core Issue: Only Diffs Have Syntax Highlighting

The TUI uses a **BaseToolRenderer pattern** with a 4-zone layout (header, params, viewport, status). However, **only `update_file` applies syntax highlighting** to its output. All other tools display raw code as plain `Text` objects.

### Current Rendering Comparison

**read_file viewport (line 142-157):**
```python
# Plain text - no highlighting
padded = pad_lines(formatted_lines, MIN_VIEWPORT_LINES)
return Text("\n".join(padded))
```

**update_file viewport (line 128-139):**
```python
# Has syntax highlighting!
return Syntax(truncated_diff, "diff", theme="monokai", word_wrap=True)
```

### What's Missing

1. **No language detection** - No mapping from file extension → pygments lexer
2. **No Syntax component usage** - `read_file`, `bash`, `grep` don't import/use `Syntax`
3. **No fallback strategy** - Unknown extensions should gracefully fall back to plain text

### Rendering Flow

```
Tool execution → raw string result
    ↓
ToolResultDisplay message posted
    ↓
on_tool_result_display() handler
    ↓
tool_panel_smart() router
    ↓
Specific renderer (e.g., ReadFileRenderer)
    ↓
parse_result() → structured data
    ↓
build_viewport() → Text() or Syntax()  ← PROBLEM IS HERE
    ↓
Panel wrapper → RichLog widget
```

### Viewport Constraints

From `src/tunacode/constants.py`:
- `TOOL_VIEWPORT_LINES = 8` - Max lines displayed
- `MIN_VIEWPORT_LINES = 3` - Minimum for padding
- `MAX_PANEL_LINE_WIDTH = 50` - Truncation width

These constraints mean syntax highlighting must work within truncated content.

## Key Patterns / Solutions Found

### Pattern 1: Rich Syntax Component
Already used in `update_file.py` - just needs to be applied elsewhere:
```python
from rich.syntax import Syntax
Syntax(code, lexer_name, theme="monokai", word_wrap=True)
```

### Pattern 2: File Extension → Lexer Mapping
Need to add language detection:
```python
EXTENSION_LEXERS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".rs": "rust",
    ".go": "go",
    # ... etc
}

def get_lexer(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    return EXTENSION_LEXERS.get(ext, "text")
```

### Pattern 3: Graceful Fallback
Unknown extensions → plain text (current behavior as fallback)

## Knowledge Gaps

1. **Performance impact** - Syntax highlighting adds overhead; is it acceptable?
2. **Truncated code** - Does Syntax handle partial code gracefully?
3. **Theme consistency** - Should use "monokai" everywhere for NeXTSTEP uniformity

## Recommended Implementation

### Shared Utility: Language Detection

Create a shared utility in `base.py` or new `syntax_utils.py`:

```python
from pathlib import Path
from rich.syntax import Syntax

EXTENSION_LEXERS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
}

def get_lexer(filepath: str) -> str:
    """Map file extension to pygments lexer name."""
    ext = Path(filepath).suffix.lower()
    return EXTENSION_LEXERS.get(ext, "text")

def syntax_or_text(content: str, filepath: str | None = None, lexer: str | None = None) -> RenderableType:
    """Return Syntax if lexer known, else plain Text."""
    if lexer is None and filepath:
        lexer = get_lexer(filepath)
    if lexer and lexer != "text":
        return Syntax(content, lexer, theme="monokai", word_wrap=True, line_numbers=False)
    return Text(content)
```

### Priority 1: read_file (Most Visual Impact)

**File:** `src/tunacode/ui/renderers/tools/read_file.py:157`

```python
# Current
return Text("\n".join(padded)) if padded else Text("(empty file)")

# Fixed
content = "\n".join(formatted_lines[:shown])  # before padding
return syntax_or_text(content, filepath=self.parsed.filepath)
```

### Priority 2: grep (Code Context in Search Results)

**File:** `src/tunacode/ui/renderers/tools/grep.py:167`

Grep shows matches from files - can detect language from the matched filename:

```python
# Current
return Text("\n".join(padded)) if padded else Text("(no matches)")

# Fixed - highlight based on matched file's extension
# Note: grep matches contain filepath, need to extract for lexer detection
```

### Priority 3: bash (Conditional - Output Varies)

**File:** `src/tunacode/ui/renderers/tools/bash.py:127-138`

Bash output is varied. Options:
- Detect if command was `cat file.py` and highlight accordingly
- Leave as plain text (safest)
- Add heuristic: if output looks like code, try "python" or auto-detect

### Priority 4: research (code_examples field)

**File:** `src/tunacode/ui/renderers/tools/research.py`

The `code_examples` field contains `{"file": "path", "code": "..."}` - can highlight using file extension.

## References

- `src/tunacode/ui/renderers/tools/base.py` - BaseToolRenderer pattern
- `src/tunacode/ui/renderers/tools/update_file.py` - Working Syntax example
- `src/tunacode/ui/renderers/tools/read_file.py` - Primary fix location
- `src/tunacode/constants.py` - Viewport constraints
- `.claude/skills/neXTSTEP-ui/` - UI design guidelines (referenced but may need verification)
