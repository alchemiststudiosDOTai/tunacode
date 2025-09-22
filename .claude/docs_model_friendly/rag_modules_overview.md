# RAG Modules Overview

This repository ships a lightweight, stdlib-only RAG toolkit under `llm-agent-tools/rag_modules/` for indexing and searching the `.claude/` knowledge base.

Components
- `rag-cli.sh`: Thin CLI wrapper around Python modules. Defaults to indexing `.claude/` into `rag_knowledge.db`.
- `indexer.py`: Builds/updates an SQLite FTS5 index with:
  - Table `docs(id, path, category, title, content, file_hash, indexed_at, file_modified)`
  - Virtual table `docs_fts(title, content, category, content=docs, content_rowid=id)` with triggers to sync inserts/updates/deletes
  - Only `.md`, `.markdown`, and `.txt` files are indexed. `category` derives from the file’s immediate parent directory name.
  - Incremental reindex, deleted-file cleanup, and FTS optimize.
- `search.py`: Executes FTS5 `MATCH` queries and formats results as `json` (compact JSONL), `text`, or `markdown`. Supports optional `--category` filter and snippet extraction/highlighting.
- `stats.py`: Reports total docs, size, per-category counts, recent updates, avg doc size, and orphaned FTS rows.

Usage
- Index: `./llm-agent-tools/rag_modules/rag-cli.sh index` (use `--full` to rebuild)
- Search: `./llm-agent-tools/rag_modules/rag-cli.sh search "query" --format text`
- Stats: `./llm-agent-tools/rag_modules/rag-cli.sh stats`

Notes
- FTS5 query parsing treats `-` as an operator. For terms with hyphens (e.g., `plan-models`), wrap in quotes: `"plan-models"` or replace with a space: `plan models` to avoid `sqlite3.OperationalError: no such column: models`.
