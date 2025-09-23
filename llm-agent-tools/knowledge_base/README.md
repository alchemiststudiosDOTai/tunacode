# Knowledge Base Tools

A suite of command-line tools designed for code agents and human-in-the-loop workflows to Create, Read, Update, and Delete (CRUD) knowledge base anchors in code repositories.

## Overview

These tools help maintain persistent memory anchors within codebases, enabling:
- Code agents to remember important context across sessions
- Human developers to mark and annotate significant code locations
- Collaborative annotation of code with contextual information
- Persistent knowledge storage that survives code changes

## Tools

### anchor_drop.py

The first tool in the suite. Drops memory anchors at specific locations in code files.

**Features:**
- Inserts `CLAUDE_ANCHOR[key=UUID]` comments in code
- Supports multiple programming languages with appropriate comment syntax
- Maintains anchor metadata in `.claude/memory_anchors/anchors.json`
- Generates unique UUID keys for each anchor

**Usage:**
```bash
python3 anchor_drop.py <file_path> <line_number> <description> [kind]
```

**Examples:**
```bash
# Drop an anchor at line 42 in main.py
python3 anchor_drop.py main.py 42 "Critical authentication logic"

# Drop an anchor with specific kind
python3 anchor_drop.py utils.py 15 "Helper function" "function"
```

**Supported Languages:**
- Python (.py) - `#` comments
- JavaScript (.js) - `//` comments
- TypeScript (.ts) - `//` comments
- Go (.go) - `//` comments
- C/C++ (.c, .cpp) - `//` comments
- Java (.java) - `//` comments
- Rust (.rs) - `//` comments
- Zig (.zig) - `//` comments
- SQL (.sql) - `--` comments
- HTML (.html, .htm) - `<!-- -->` comments

## Anchor Data Structure

Anchors are stored in `.claude/memory_anchors/anchors.json` with the following structure:

```json
{
  "version": 1,
  "generated": "2025-09-23T11:35:02Z",
  "anchors": [
    {
      "key": "affbd046",
      "path": "test_file.py",
      "line": 12,
      "kind": "line",
      "description": "Important calculation function",
      "status": "active",
      "created": "2025-09-23T11:35:00Z"
    }
  ]
}
```

## Use Cases

1. **Code Agent Memory**: Allow agents to remember important code locations and context
2. **Code Reviews**: Mark sections needing attention or explanation
3. **Documentation**: Embed documentation directly in code locations
4. **Debugging**: Anchor problematic code sections with notes
5. **Learning**: Annotate code examples with explanations

## Future Tools

Planned additions to the tool suite:
- `anchor_list.py` - List all anchors in the repository
- `anchor_update.py` - Update anchor descriptions and metadata
- `anchor_delete.py` - Remove anchors from code and registry
- `anchor_search.py` - Search anchors by description or metadata
- `anchor_export.py` - Export anchors in various formats