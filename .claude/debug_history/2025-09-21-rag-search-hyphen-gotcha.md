# Debug Log: RAG search hyphen gotcha

- Date: 2025-09-21
- Context: Running `./llm-agent-tools/rag_modules/rag-cli.sh search "models_registry OR plan-models"`
- Error: `sqlite3.OperationalError: no such column: models`
- Root Cause: FTS5 `MATCH` parser interprets hyphen (`-`) as an operator; the token `plan-models` is parsed as `plan - models`, leading SQLite to look for a `models` column/symbol.
- Resolution: Quote hyphenated terms: `"plan-models"`, or replace hyphens with spaces. Example: `./rag-cli.sh search 'models_registry OR "plan-models"' --format json`.
- Follow-ups: Added `.claude/docs_model_friendly/rag_modules_overview.md` with usage notes.
