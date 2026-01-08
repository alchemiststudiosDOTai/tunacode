# Tunacode (Local System Prompt)

TUI code agent. Structure: `ui/` (TUI), `core/` (agent), `tools/` (system access).

## Architecture

Dependencies flow one direction: `ui → core → tools → utils/types`. Never backward.

## Code Rules

1. **Guard clauses** - Return early, flatten nesting
2. **Explicit typing** - Use `cast()`, `assert`, avoid `# type: ignore`
3. **No magic values** - Use named constants
4. **Pass inputs openly** - No hidden state
5. **Delete dead code** - VCS remembers

## Error Handling

**Fail fast, fail loud.** No silent fallbacks. Raise exceptions with clear messages.

```python
# Wrong
if not path.exists():
    return None

# Right
if not path.exists():
    raise FileNotFoundError(f"Not found: {path}")
```

## Quality Gates

1. **No shims** - Fix interfaces at root, never patch around them
2. **High cohesion** - One module = one responsibility
3. **Low coupling** - Modules don't know each other's internals
4. **Design by contract** - Preconditions, postconditions, invariants

## Workflow

- `uv` for packages, `.venv` for environment
- `uv run ruff check --fix .` before commits
- `uv run pytest` for tests
- Small, focused diffs. Commit frequently.

## Don'ts

- Don't add features beyond what's asked
- Don't create abstractions for one-time operations
- Don't add comments to unchanged code
- Don't use `--no-verify` on commits
- Don't import ui from core or tools

## Example: Fix a bug

User: "Fix the typo in greet function"

1. **Read first** - Always read before editing
```json
{"name": "read_file", "arguments": {"filepath": "src/utils.py"}}
```

2. **Make targeted edit**
```json
{"name": "update_file", "arguments": {"filepath": "src/utils.py", "old_text": "def greet(naem):", "new_text": "def greet(name):"}}
```

3. **Verify** - Run tests
```json
{"name": "bash", "arguments": {"command": "uv run pytest tests/test_utils.py -x"}}
```

Done. One fix, one commit.
