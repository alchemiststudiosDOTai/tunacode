.PHONY: install clean lint format test coverage build remove-playwright-binaries restore-playwright-binaries

install:
	pip install -e ".[dev]"

run:
	env/bin/tunacode

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

lint:
	ruff check . && ruff format .

lint-check:
	ruff check .
	ruff format --check .

vulture:
	venv/bin/vulture --config pyproject.toml

vulture-check:
	venv/bin/vulture --config pyproject.toml --min-confidence 100

# Enhanced dead code detection
.PHONY: dead-code-check dead-code-clean dead-code-report

dead-code-check:
	@echo "Running comprehensive dead code analysis..."
	@echo "\n=== Vulture (unused code) ==="
	@venv/bin/vulture . --min-confidence 80 --exclude "*/test/*,*/tests/*,venv/*,build/*,dist/*" || true
	@echo "\n=== Unimport (unused imports) ==="
	@venv/bin/unimport --check . || true
	@echo "\n=== Dead (dead code detector) ==="
	@venv/bin/dead . || true
	@echo "\n=== Checking test coverage for dead code ==="
	@venv/bin/python -m pytest --cov=src/tunacode --cov-report=term-missing:skip-covered | grep -E "(TOTAL|src/)" || true

dead-code-clean:
	@echo "Removing dead code..."
	@venv/bin/unimport --remove-all .
	@venv/bin/autoflake --remove-all-unused-imports --remove-unused-variables -i -r src/
	@echo "Dead code cleanup complete!"

dead-code-report:
	@echo "Generating dead code reports..."
	@mkdir -p reports
	@venv/bin/vulture . --min-confidence 60 > reports/dead_code_vulture.txt || true
	@venv/bin/unimport --check . --diff > reports/unused_imports.txt || true
	@echo "Dead Code Metrics:" > reports/metrics.txt
	@echo "Unused functions: $$(grep -c "unused function" reports/dead_code_vulture.txt 2>/dev/null || echo 0)" >> reports/metrics.txt
	@echo "Unused imports: $$(grep -c "^-" reports/unused_imports.txt 2>/dev/null || echo 0)" >> reports/metrics.txt
	@echo "Reports generated in reports/ directory"

test:
	venv/bin/python -m pytest -q tests/characterization tests/test_security.py tests/test_agent_output_formatting.py tests/test_prompt_changes_validation.py


coverage:
	pytest --cov=src/tunacode --cov-report=term

build:
	python -m build

remove-playwright-binaries:
	@echo "Removing Playwright binaries for testing..."
	@MAC_CACHE="$(HOME)/Library/Caches/ms-playwright"; \
	LINUX_CACHE="$(HOME)/.cache/ms-playwright"; \
	if [ -d "$$MAC_CACHE" ]; then \
		mv "$$MAC_CACHE" "$$MAC_CACHE"_backup; \
		echo "Playwright binaries moved to $$MAC_CACHE"_backup; \
	elif [ -d "$$LINUX_CACHE" ]; then \
		mv "$$LINUX_CACHE" "$$LINUX_CACHE"_backup; \
		echo "Playwright binaries moved to $$LINUX_CACHE"_backup; \
	else \
		echo "No Playwright binaries found. Please run 'playwright install' first if you want to test the reinstall flow."; \
	fi

restore-playwright-binaries:
	@echo "Restoring Playwright binaries..."
	@MAC_CACHE="$(HOME)/Library/Caches/ms-playwright"; \
	LINUX_CACHE="$(HOME)/.cache/ms-playwright"; \
	if [ -d "$$MAC_CACHE"_backup ]; then \
		mv "$$MAC_CACHE"_backup "$$MAC_CACHE"; \
		echo "Playwright binaries restored from $$MAC_CACHE"_backup; \
	elif [ -d "$$LINUX_CACHE"_backup ]; then \
		mv "$$LINUX_CACHE"_backup "$$LINUX_CACHE"; \
		echo "Playwright binaries restored from $$LINUX_CACHE"_backup; \
	else \
		echo "No backed up Playwright binaries found. Nothing to restore."; \
	fi
