# RAG Modules

Retrieval-Augmented Generation modules for indexing and searching documentation using SQLite FTS5.

## Quick Start (CLI)

The included `rag-cli.sh` provides a simple interface for using the RAG tools:

```bash
# Index the default memory-bank directory
./rag-cli.sh index

# Search indexed content
./rag-cli.sh search "your query here"

# View index statistics
./rag-cli.sh stats

# Index a custom directory
./rag-cli.sh index --dir /path/to/your/docs
```

## Directory Structure

```
rag_modules/
├── rag-cli.sh          # Main CLI script
├── rag_knowledge.db    # SQLite database (created after first run)
├── indexer.py          # Documentation indexer
├── search.py           # Full-text search interface
├── stats.py            # Index statistics and health monitoring
├── README.md           # This file
└── default_directory_behavior.md  # Details on directory detection
```

## Customizing Path Pointing

The RAG system is flexible and can point to any directory you want to index:

### Via CLI (Recommended)
```bash
# Index any directory
./rag-cli.sh index --dir /path/to/your/project/docs

# Index multiple directories
./rag-cli.sh index --dir ./docs ./wiki ./notes

# Use a custom database location
./rag-cli.sh index --dir ./docs --db-path /custom/path/to/my.db
```

### Via Environment Variables
```bash
# Set custom database path
export RAG_DB_PATH="/custom/location/knowledge.db"

# Enable verbose output
export RAG_VERBOSE=1

# Then run commands normally
./rag-cli.sh index
```

### Direct Module Usage
```bash
# Index specific directories with full control
python3 indexer.py --directories ./src ./docs ./README.md --db-path ./my_docs.db

# Search with specific parameters
python3 search.py --db-path ./my_docs.db --query "API reference" --category src --format json
```

## Agent Usage Guide

For AI agents and programmatic use:

### 1. Index Documentation
```bash
# For agent knowledge bases
./rag-cli.sh index --dir /path/to/agent/knowledge
```

### 2. Search (JSON output recommended)
```bash
# Get search results in JSON format for parsing
./rag-cli.sh search "implementation details" --format json

# Search within specific categories
./rag-cli.sh search "API methods" --category api --format json
```

### 3. Check Index Health
```bash
# Get statistics in JSON format
./rag-cli.sh stats --json
```

## CLI Reference

### Index Command
```bash
./rag-cli.sh index [options]
  --full           # Full rebuild of index
  --dir DIR        # Directory to index (default: ../memory-bank)
  --db PATH        # Custom database path
```

### Search Command
```bash
./rag-cli.sh search <query> [options]
  --category CAT   # Search within specific category
  --format FMT     # Output: json|text|markdown (default: json)
  --limit N        # Maximum results (default: 10)
  --db PATH        # Custom database path
```

### Stats Command
```bash
./rag-cli.sh stats [options]
  --json           # Output in JSON format
  --db PATH        # Custom database path
```

## Default Directory Behavior

When no directories are specified, the system automatically searches for documentation:
1. First looks in the current directory for `docs/` or `documentation/` folders
2. If not found, checks the parent directory for the same folders

## Supported File Types

- Markdown files (.md, .markdown)
- Text files (.txt)

## Output Formats

- **JSON**: Compact JSONL format for agent consumption
- **Text**: Human-readable with highlighted search terms
- **Markdown**: Formatted output with proper formatting

## Examples

```bash
# Index project documentation
./rag-cli.sh index --dir ./docs

# Search for specific patterns
./rag-cli.sh search "authentication flow" --category guide --format markdown

# Check what's indexed
./rag-cli.sh stats

# Full reindex when files change significantly
./rag-cli.sh index --full --dir ./docs
```