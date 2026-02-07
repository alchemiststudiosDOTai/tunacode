# Tunacode Development Makefile
# Provides convenient shortcuts for common development tasks

.PHONY: help dev-setup install run test lint clean docs docs-serve

# Default target shows help
help:
	@echo "Tunacode Development Commands:"
	@echo ""
	@echo "  make dev-setup  - Full setup for fresh clone (installs deps, hooks)"
	@echo "  make install    - Install/update dependencies"
	@echo "  make run        - Run the development server"
	@echo "  make test       - Run test suite"
	@echo "  make lint       - Run linters and formatters"
	@echo "  make docs       - Build documentation site"
	@echo "  make docs-serve - Serve documentation locally"
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

# Run linters
lint:
	uv run ruff check --fix .

# Build documentation site
docs:
	uv run mkdocs build

# Serve documentation locally
docs-serve:
	uv run mkdocs serve

# Clean build artifacts
clean:
	rm -rf build/ dist/ site/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
