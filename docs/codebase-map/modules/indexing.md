---
title: Indexing Module
path: src/tunacode/indexing
type: directory
depth: 1
description: Fast in-memory codebase indexing
exports: [CodeIndex, index_files, search_files]
seams: [M]
---

# Indexing Module

## Purpose
Provides fast in-memory indexing for efficient file and symbol lookups across the codebase.

## Key Components

### code_index.py
**CodeIndex Class**
Main indexing engine:
- **index_files()** - Index files in directory
- **search_files()** - Fast file pattern matching
- **get_file_list()** - Retrieve all indexed files
- **invalidate()** - Clear and rebuild index

**Features:**
- In-memory file list caching
- Default exclude directory filtering (shared with tools)
- Fast pattern matching
- Lazy indexing (indexes on demand)
- Size-based thresholds

### constants.py
Indexing configuration constants:
- **IGNORE_DIRS** - Shared default exclude directories (from tools ignore manager)
- **QUICK_INDEX_THRESHOLD** - Files below this count use full indexing
- **INDEX_CACHE_SIZE** - Maximum cache size
- **INDEX_UPDATE_DELAY** - Debouncing for index updates

## Indexing Strategy

**When to Index:**
- On first file operation
- After significant file system changes
- When explicitly requested

**What to Index:**
- Source code files (based on extensions)
- Configuration files
- Documentation files
- Respect shared exclude directory list

**What to Skip:**
- Binary files
- Large files (> size threshold)
- Hidden files (unless requested)
- VCS directories (.git, .svn)

## Index Format

```python
{
  "files": List[FilePath],
  "last_updated": datetime,
  "root_path": Path,
  "ignore_patterns": List[str]
}
```

## Performance Optimizations

1. **Lazy Indexing** - Only index when needed
2. **Caching** - Keep index in memory
3. **Incremental Updates** - Update only changed files
4. **Threshold-based** - Use different strategies for different project sizes

## Integration Points

- **tools/glob.py** - File pattern matching
- **tools/grep.py** - Content search optimization
- **tools/list_dir.py** - Directory listing
- **ui/** - Index progress display

## Seams (M)

**Modification Points:**
- Adjust indexing thresholds
- Add new indexing strategies
- Extend file type detection
- Customize ignore patterns

**Extension Points:**
- Implement symbol indexing (functions, classes)
- Add content-based indexing
- Create incremental indexing
- Add index persistence
