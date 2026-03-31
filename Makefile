# Tunacode Development Makefile
# Provides convenient shortcuts for common development tasks

.PHONY: all help dev-setup install run test test-tmux lint check clean

# Default target shows help
help:
	@echo "Tunacode Development Commands:"
	@echo ""
	@echo "  make dev-setup  - Full setup for fresh clone (installs deps, hooks)"
	@echo "  make install    - Install/update dependencies"
	@echo "  make run        - Run the development server"
	@echo "  make test       - Run test suite"
	@echo "  make test-tmux  - Run the tmux system test suite"
	@echo "  make lint       - Run linters and formatters"
	@echo "  make check      - Run harness checks (hooks + CI enforcement parity checks)"
	@echo "  make clean      - Clean build artifacts"
	@echo ""

# Full setup for fresh clone
dev-setup:
	@bash scripts/dev-setup.sh

# Install/update dependencies
install:
	uv sync --extra dev

# Run the development server
run:
	uv run tunacode

# Run test suite
test:
	uv run pytest

# Run tmux system test suite
test-tmux:
	uv run pytest tests/system/cli/test_tmux_tools.py

# Run linters
lint:
	uv run ruff check --fix .

# Run full harness checks locally (hooks + CI enforcement parity checks)
check:
	uv run pre-commit run --all-files --hook-stage pre-commit
	uv run pre-commit run --all-files --hook-stage pre-push
	uv run unimport --check --gitignore --exclude 'venv/*' --exclude '.venv/*' --exclude '.uv-cache/*' --exclude '.uv_cache/*' src
	uv run vulture --min-confidence 80 scripts/utils/vulture_whitelist.py src
	uv run python scripts/check_unused_modules.py
	uv run deptry src/

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
