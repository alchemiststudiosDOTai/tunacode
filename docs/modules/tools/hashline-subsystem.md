---
title: Hashline Edit Subsystem
summary: Cryptographically-validated file editing with content-hash line tagging and in-memory cache validation
read_when:
  - You need to understand how file edits are validated
  - You're implementing a new file editing tool
  - Debugging hash mismatch errors in file edits
  - Working on the read_file → hashline_edit workflow
depends_on:
  - docs/modules/tools/tools.md
  - docs/modules/ui/ui.md
feeds_into:
  - docs/modules/core/core.md
  - README.md
when_to_read:
  - You need to understand how file edits are validated
  - You're implementing a new file editing tool
  - Debugging hash mismatch errors in file edits
  - Working on the read_file → hashline_edit workflow
last_updated: "2026-04-04"
---

# Hashline Edit Subsystem

## What

The hashline edit subsystem provides cryptographically-validated file editing for agent operations. It implements a **read-side annotation + write-side validation** pattern that prevents stale edits and ensures edits are always applied to the correct line content.

Each line read by the agent is tagged with a short MD5 content hash (2 hex characters = 256 buckets). When the agent requests an edit, the hash is validated against the cached file state. If the hash doesn't match, the edit is rejected with a clear error message instructing the model to re-read the file.

### Key Features

- **Content-hash validation**: Every line is validated before editing
- **Three edit operations**: `replace`, `replace_range`, `insert_after`
- **Side-by-side diff visualization**: NeXTSTEP-style panel with before/after view
- **Automatic cache updates**: Cache stays synchronized after every edit
- **Trailing newline preservation**: File newline state is retained after writes
- **Unified diff output**: Standard diff format for review and verification

### Workflow Flow Diagram

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│             │     │              │     │             │     │              │
│  read_file  │────▶│  hashline.py │────▶│ line_cache  │────▶│ hashline_edit│
│             │     │  (tag lines) │     │  (store)    │     │  (validate)  │
└─────────────┘     └──────────────┘     └─────────────┘     └──────┬───────┘
                                                                    │
                    ┌──────────────┐                               │
                    │              │◄──────────────────────────────┘
                    │    File      │       (write changes)
                    │              │
                    └──────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │    Diff      │────▶ UI Renderer
                    │   Output     │     (side-by-side)
                    └──────────────┘
```

## Key Files

### Core Components

| File | Purpose |
|------|---------|
| `src/tunacode/tools/hashline.py` | Content-hash line tagging and validation primitives |
| `src/tunacode/tools/line_cache.py` | In-memory cache for hashed lines keyed by file path |
| `src/tunacode/tools/hashline_edit.py` | Main edit tool with three operations (replace, replace_range, insert_after) |
| `src/tunacode/tools/read_file.py` | File reading that populates cache with hash-tagged output |
| `src/tunacode/ui/renderers/tools/hashline_edit.py` | Side-by-side diff display with NeXTSTEP panel styling |

### File Relationships

```
read_file.py
    │
    ├──▶ hashline.py
    │       ├── content_hash()
    │       ├── format_hashline()
    │       └── parse_line_ref()
    │
    └──▶ line_cache.py (store)
            │
            │    ▲
            │    │ (get / update / replace_range)
            ▼    │
    hashline_edit.py
            │
            ├── _validate_ref() ──▶ line_cache.py (get)
            ├── _apply_replace() ──▶ line_cache.py (update_lines)
            ├── _apply_replace_range() ──▶ line_cache.py (replace_range)
            ├── _apply_insert_after() ──▶ line_cache.py (replace_range)
            │
            └──▶ UI renderer ────▶ ui/renderers/tools/hashline_edit.py
```

## How

### 1. Content Hashing (`hashline.py`)

Each line is hashed using MD5 (2 hex characters = 256 buckets), giving enough entropy to detect stale references without bloating the context window.

```python
HASH_LENGTH = 2
LINE_HASH_SEPARATOR = ":"
HASH_SEPARATOR = "|"

# Example output format
# 1:a3|function hello() {
# 2:f1|    console.log("world");
# 3:0e|}
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `content_hash(line)` | Compute MD5 hash of line content (2 hex chars) |
| `tag_lines(content, offset)` | Split content and tag each line with hash |
| `format_hashline(HashedLine)` | Format as `line:hash|content` string |
| `format_hashlines(content)` | Tag all lines in content for display |
| `parse_line_ref(ref)` | Parse `line:hash` reference, e.g., `"2:f1"` |

### 2. Line Cache (`line_cache.py`)

Stores `{path: {line_number: HashedLine}}` as a module-level singleton. The cache is replaced (not merged) on each `read_file` call.

**Cache Operations:**

| Function | Purpose |
|----------|---------|
| `store(filepath, lines)` | Cache hashed lines for a file |
| `get(filepath)` | Return read-only view of cached lines |
| `get_line(filepath, line_number)` | Return single cached line or None |
| `validate_ref(filepath, line, expected_hash)` | Check if line hash matches cached state |
| `update_lines(filepath, updates)` | Update cached lines after an edit |
| `replace_range(filepath, start, end, new_lines)` | Replace a range and re-number subsequent lines |
| `invalidate(filepath)` | Remove cached state for a file |
| `clear()` | Clear entire cache (testing) |

### 3. Edit Tool (`hashline_edit.py`)

Three edit operations validate against the current cache window before applying changes.

**Validation Flow:**

```
┌─────────────────┐
│  hashline_edit  │
│   (operation)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  _validate_ref  │──── Parse "line:hash" reference
│                 │──── Check file is cached
│                 │──── Verify line exists in cache
│                 │──── Compare expected vs actual hash
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌──────┐  ┌──────┐
│ Pass │  │ Fail │
└──┬───┘  └──┬───┘
   │         │
   ▼         ▼
┌──────┐  ┌─────────────┐
│ Apply│  │ ToolRetryError│
│ Edit │  │ "hash mismatch│
└──┬───┘  │  Re-read..." │
   │      └─────────────┘
   ▼
┌──────────┐
│ Update   │
│ Cache    │
└──────────┘
```

**Three Operations:**

| Operation | Parameters | Description |
|-----------|------------|-------------|
| `replace` | `line`, `new` | Replace a single line identified by hash |
| `replace_range` | `start`, `end`, `new` | Replace contiguous range of lines |
| `insert_after` | `after`, `new` | Insert new lines after a referenced line |

**Post-write behavior:**

- Preserves the file's existing trailing newline state
- Uses `new.splitlines()` for multi-line replacements and insertions
- Updates the in-memory cache immediately after writing
- Returns a unified diff string for the renderer and review flow

**Error Messages:**

```python
STALE_REF_MESSAGE = (
    "File has changed since last read — line {line} hash mismatch "
    "(expected '{expected}', cached '{actual}'). Re-read the file first."
)

UNCACHED_FILE_MESSAGE = "File '{filepath}' has no cached state. Read the file first with read_file."

LINE_NOT_CACHED_MESSAGE = (
    "Line {line} is not in the cached state for '{filepath}'. "
    "The file may have been read with an offset that skipped this line. "
    "Re-read the file to include this line."
)
```

### 4. Read Integration (`read_file.py`)

`read_file` populates the line cache with every read, enabling `hashline_edit` to validate references.

```text
# Output shape:
<file>
1:a3|def main():
2:f1|    pass
3:0e|

(End of file - total 3 lines)
</file>
```

**Key Points:**

- Files over `100KB` are rejected
- `limit` defaults to `2000` lines, and `offset` is a 0-based line offset
- Displayed line text is truncated at `2000` characters, but cached hashes use the full line content
- Output is always wrapped in `<file>...</file>`
- Each `read_file` call **replaces** the cache for that file
- Paginated reads do not merge prior cache windows
- `hashline_edit` can only edit lines present in the current cache
- The footer is either a continuation hint (`Use 'offset' to read beyond line N`) or an end-of-file marker
- Missing lines cause `ToolRetryError` instructing the model to re-read the file to include that line

### 5. UI Renderer (`src/tunacode/ui/renderers/tools/hashline_edit.py`)

NeXTSTEP-style panel with four zones:

```
┌─────────────────────────────────────────────┐
│ filename.js   +3 -2          ← Zone 1: Header│
│                                             │
│ /path/to/filename.js         ← Zone 2: Path│
│ ─────────────────────────────              │
│   1│function old() {      │ 1│function new() {     ← Zone 3: Side-by-side
│ - 2│  return old;        │+2│  return new;       │     diff viewport
│   3│}                    │ 3│}                   │
│ ─────────────────────────────                │
│                                             │
│ 1 hunk  [45ms]               ← Zone 4: Status  │
└─────────────────────────────────────────────┘
```

**Rendering Pipeline:**

```
hashline_edit result (optional diagnostics + unified diff text)
         │
         ▼
    parse_result()
         │
         ├──▶ Extract optional diagnostics block
         ├──▶ Extract filepath
         ├──▶ Count additions (+)
         ├──▶ Count deletions (-)
         └──▶ Count hunks (@@)
         │
         ▼
   _parse_side_by_side_rows()
         │
         ├──▶ Parse hunk headers (@@ -1,3 +1,3 @@)
         ├──▶ Categorize lines: context, insert, delete, meta
         └──▶ Build DiffSideBySideLine objects
         │
         ▼
   _build_side_by_side_viewport()
         │
         ├──▶ Calculate column widths
         ├──▶ Apply syntax highlighting styles
         └──▶ Build Rich Table with gutters
```

## Why

### Prevents Stale Edits

Without hash validation, an agent might reference a line that was:

- Deleted by another process
- Modified by a previous edit
- Never actually existed at that line number

The hash acts as a **content-addressed pointer**. If the content changes, the hash changes, and the edit is rejected before touching the filesystem.

### Provides Clear Edit Visualization

Side-by-side diff makes changes explicit:

```
Before                    │ After
──────────────────────────┼──────────────────────────
  1│old_function() {       │  1│new_function() {
- 2│  return old_value;   │+ 2│  return new_value;
  3│}                     │  3│}
```

### Enables Safe Concurrent Editing

The cache is session-local and updated immediately after each edit. This allows:

1. Multiple edits to the same file in sequence
2. Cache stays synchronized with filesystem
3. Next edit validates against updated hashes

### Minimal Overhead

- 2 hex characters = 256 buckets (0.4% collision probability)
- Cache is in-memory only (no disk I/O)
- Unified diff output is standard and reviewable

## Usage Example

```python
# 1. Read file (populates cache)
result = await read_file("/path/to/file.py")
# Output: 1:a3|def main():
#         2:f1|    pass

# 2. Edit a line using hash reference
result = await hashline_edit(
    filepath="/path/to/file.py",
    operation="replace",
    line="2:f1",  # Line 2, hash f1
    new="    print('hello')"
)

# 3. If hash mismatches (file changed)
# Raises: ToolRetryError("File has changed since last read...")
```

## Related Documentation

- `docs/modules/tools/tools.md` - Active native tool surface and contract summary
- `docs/modules/core/core.md` - Agent assembly and tool registration flow
- `docs/modules/ui/ui.md` - Tool renderer inventory and rendering pipeline
- `README.md` - User-facing tool overview
