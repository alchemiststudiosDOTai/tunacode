# Contributing to tunacode

Thanks for your interest in contributing to tunacode! This document provides guidelines and instructions for contributing.

## Getting Help

- **Questions & Ideas**: Use [GitHub Discussions](https://github.com/alchemiststudiosDOTai/tunacode/discussions)
- **Bug Reports**: Open a [GitHub Issue](https://github.com/alchemiststudiosDOTai/tunacode/issues)
- **Discord**: [Discord invite link] <!-- Replace with actual Discord URL -->

## Development Setup

### Requirements

- Python 3.11+ (tested on 3.11, 3.12, 3.13)
- [uv](https://github.com/astral-sh/uv) package manager (not pip)

### Setup Steps

```bash
# Clone the repository
git clone https://github.com/alchemiststudiosDOTai/tunacode.git
cd tunacode

# Create virtual environment and install dependencies
uv sync

# Note: We do not use git hooks or pre-commit in this repo.
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

## Development Workflow

1. **Fork** the repository and create a feature branch
2. Make **small, focused changes** - one logical change per commit
3. **Commit frequently** with clear messages
4. Run checks locally before pushing:
   ```bash
   uv run ruff check . && uv run ruff format .   # Lint and format
   uv run mypy src/                               # Type checking
   uv run pytest                                  # Run tests
   ```

## Testing

### Running Tests

```bash
uv run pytest                    # Run all tests
uv run pytest tests/             # Run specific directory
uv run pytest --cov=src/tunacode # Run with coverage
```

### Test Expectations

- All existing tests must pass
- New features should include tests
- Golden/characterization tests are preferred for complex behavior

## AI-Assisted Contributions

Using AI tools to help write code or documentation is welcome. However:

- **Follow all project standards** - AI output must meet the same quality bar as human-written code
- **Review and refine** - Don't submit raw AI output without careful review
- **No low-effort submissions** - PRs that are clearly unreviewed AI-generated content will be closed

The maintainers can tell the difference. Put in the effort.

## Pull Request Process

1. **Fill out the PR template** completely
2. Ensure all checks pass:
   - Ruff lint and format checks
   - File length validation (600 lines max)
3. Self-review your changes
4. Update documentation if needed
5. **Address CodeRabbit feedback** - We use [CodeRabbit AI](https://coderabbit.ai) for automated code review. Please fix any issues it identifies.

### PR Checklist

- [ ] Code follows project style (type hints, no magic numbers, etc.)
- [ ] Tests pass locally
- [ ] No file exceeds 600 lines
- [ ] Documentation updated (if applicable)
- [ ] CodeRabbit feedback addressed

## Quick Command Reference

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
