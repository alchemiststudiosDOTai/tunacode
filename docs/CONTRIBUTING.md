# Contributing to tunacode

Thanks for your interest in contributing to tunacode! This document provides guidelines and instructions for contributing.

## **AI-Assisted Contributions**

**AI-generated PRs are welcome, but keep them small and clean.** Large, unstacked PRs are hard to review; small diffs help CodeRabbit run cleanly and let maintainers review quickly.

Using AI tools to help write code or documentation is welcome. However:

- **Follow all project standards** - AI output must meet the same quality bar as human-written code
- **Review and refine** - Don't submit raw AI output without careful review
- **No low-effort submissions** - PRs that are clearly unreviewed AI-generated content will be closed

The maintainers can tell the difference. Put in the effort.

## Getting Help

- **Questions & Ideas**: Use [GitHub Discussions](https://github.com/alchemiststudiosDOTai/tunacode/discussions)
- **Bug Reports**: Open a [GitHub Issue](https://github.com/alchemiststudiosDOTai/tunacode/issues)
- **Discord**: [Discord](https://discord.gg/TN7Fpynv6H)

## Development Setup

### Requirements

- Python 3.11+ (tested on 3.11, 3.12, 3.13)
- [uv](https://github.com/astral-sh/uv) package manager (not pip)

### Quick Setup (Recommended)

```bash
git clone https://github.com/alchemiststudiosDOTai/tunacode.git
cd tunacode
make dev-setup
```

### Manual Setup

If you prefer not to use make:

```bash
# Clone the repository
git clone https://github.com/alchemiststudiosDOTai/tunacode.git
cd tunacode

# Create virtual environment and install dependencies
uv sync --extra dev

# Install pre-commit hooks
uv run pre-commit install
```

## Code Standards

### Formatting & Linting

- **Ruff** handles both linting and formatting (line length: 100)
- Run `uv run ruff check . && uv run ruff format .` before committing

### Type Hints

- Explicit type hints are required
- `cast()` and `assert` are acceptable
- `# type: ignore` only with strong justification

### File Length

- Maximum **600 lines** per Python file (enforced in CI)
- PRs will fail if any file exceeds this limit

### Code Style

- **No magic numbers** - use symbolic constants
- **Flatten conditionals** - return early, make pre-conditions explicit
- **Fail fast, fail loud** - no silent fallbacks or error swallowing
- **No dead code** - delete unused code entirely (never comment out or guard)
- **Keep it simple** - avoid over-engineering and unnecessary abstractions

### Error Handling

- Minimize branching - every `if`/`try` must be justified
- Never silently catch and ignore exceptions
- Fail explicitly with clear error messages

### Technical Debt Markers

When adding TODO, FIXME, HACK, or XXX markers to the code, follow this format:

```python
# TODO(scope): description [TUN-XXXX]
# FIXME(core): handle edge case [TUN-1234]
```

- **Scope**: Brief identifier for the affected area (e.g., `core`, `ui`, `tools`)
- **Description**: Clear explanation of the debt item
- **Ticket**: Optional GitHub issue reference in `TUN-XXXX` format

The CI runs a tech debt scanner on every PR. If you add new markers:

1. View current debt: `uv run python scripts/todo_scanner.py --format text`
2. Update baseline if the debt is intentional:
   ```bash
   uv run python scripts/todo_scanner.py --output scripts/todo_baseline.json
   ```

See [tech-debt-tracking.md](../agent-docs/tech-debt-tracking.md) for full details.

## Development Workflow

1. **Fork** the repository and create a feature branch
2. Make **small, focused changes** - one logical change per commit
3. **Commit frequently** with clear messages
4. Run checks locally before pushing:
   ```bash
   make lint          # Lint and format
   make test          # Run tests

   # Or manually:
   uv run ruff check . && uv run ruff format .   # Lint and format
   uv run mypy src/                               # Type checking
   uv run pytest                                  # Run tests
   ```

## Testing

### Running Tests

```bash
make test                        # Run all tests (recommended)

# Or manually:
uv run pytest                    # Run all tests
uv run pytest tests/             # Run specific directory
uv run pytest --cov=src/tunacode # Run with coverage
```

### Test Expectations

- All existing tests must pass
- New features should include tests
- Golden/characterization tests are preferred for complex behavior

## Pull Request Process

### Before Opening a PR

**Rebase onto master before opening your PR.** This project changes frequently (week to week), and stale branches cause merge conflicts and CI failures. Run:

```bash
git fetch origin
git rebase origin/master
```

If your PR is open and master moves ahead, that's fine - but the initial PR must be rebased.

**All pre-commit hooks must pass.** Run `uv run pre-commit run --all-files` before opening your PR. If hooks fail, fix the issues locally. You can open a draft PR anytime, but **when you mark it ready for review, all checks must pass or the PR will be closed.**

If the dev environment setup (`uv sync --extra dev && uv run pre-commit install`) is not working for you, please open an issue or PR to fix it - don't submit PRs that skip hooks.

### PR Requirements

1. **Fill out the PR template** completely
2. **Rebase onto master** (see above)
3. Ensure all checks pass:
   - Ruff lint and format checks
   - File length validation (600 lines max)
4. Self-review your changes
5. Update documentation if needed
6. **Address CodeRabbit feedback** - We use [CodeRabbit AI](https://coderabbit.ai) for automated code review. Please fix any issues it identifies.

### PR Checklist

- [ ] Code follows project style (type hints, no magic numbers, etc.)
- [ ] Tests pass locally
- [ ] No file exceeds 600 lines
- [ ] Documentation updated (if applicable)
- [ ] CodeRabbit feedback addressed

## Quick Command Reference

### Make Commands

| Command | Description |
|---------|-------------|
| `make dev-setup` | Full setup for fresh clone |
| `make install` | Install/update dependencies |
| `make run` | Run the development server |
| `make test` | Run test suite |
| `make lint` | Run linters and formatters |
| `make clean` | Clean build artifacts |

### Manual Commands

| Command | Description |
|---------|-------------|
| `uv sync` | Install dependencies |
| `uv run ruff check .` | Lint code |
| `uv run ruff format .` | Format code |
| `uv run ruff check . && uv run ruff format .` | Lint and format |
| `uv run mypy src/` | Run type checking |
| `uv run bandit -r src/ -ll` | Run security scan |
| `uv run pytest` | Run test suite |
| `uv run pytest --cov=src/tunacode` | Run tests with coverage |
| `uv run vulture .` | Check for dead code |

## Project Structure

```
tunacode/
├── src/tunacode/
│   ├── ui/           # TUI interface (Textual-based)
│   ├── core/         # Core agent logic
│   └── tools/        # Tool implementations
├── tests/            # Test suite
├── docs/             # Documentation
└── .github/          # CI/CD workflows
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
