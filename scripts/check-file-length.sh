#!/bin/bash

# Check for files longer than 500 lines
# Exit with status 1 if any files exceed the limit

MAX_LINES=600
FOUND_LONG_FILES=0
UV_CACHE_DIR_HYPHEN="./.uv-cache/*"
UV_CACHE_DIR_UNDERSCORE="./.uv_cache/*"

is_binary_file() {
    local filepath="$1"

    if ! command -v file >/dev/null 2>&1; then
        return 1
    fi

    local encoding=""
    encoding="$(file -b --mime-encoding "$filepath" 2>/dev/null || true)"
    [ "$encoding" = "binary" ]
}

# Find all files, excluding common directories and binary files
while IFS= read -r -d '' file; do
    # Skip if it's not a regular file
    if [ ! -f "$file" ]; then
        continue
    fi

    if is_binary_file "$file"; then
        continue
    fi

    # Skip glob.py and grep.py as they contain necessary prompt injection implementation
    # Skip main.py in agents dir as it was recently refactored
    # Skip prompt files as they can be lengthy for comprehensive system instructions
    # Skip app.tcss and code_index.py pending refactor (see issue #155)
    # Skip test_tool_call_lifecycle.py as it contains comprehensive integration tests (issue #259)
    # Skip sanitize.py as it contains complex session resume sanitization logic
    if [[ "$file" == *"/src/tunacode/tools/glob.py" ]] || \
       [[ "$file" == *"/src/tunacode/tools/grep.py" ]] || \
       [[ "$file" == *"/src/tunacode/core/agents/main.py" ]] || \
       [[ "$file" == *"/src/tunacode/core/agents/resume/sanitize.py" ]] || \
       [[ "$file" == *"/src/tunacode/prompts/"*".xml" ]] || \
       [[ "$file" == *"/src/tunacode/ui/app.tcss" ]] || \
       [[ "$file" == *"/src/tunacode/indexing/code_index.py" ]] || \
       [[ "$file" == *"/tests/test_tool_call_lifecycle.py" ]] || \
       [[ "$file" == *"/tests/integration/core/test_tool_call_lifecycle.py" ]]; then
        continue
    fi

    # Get line count
    lines=$(wc -l < "$file" 2>/dev/null || echo 0)

    # Check if file exceeds limit
    if [ "$lines" -gt "$MAX_LINES" ]; then
        echo "$file: $lines lines (exceeds $MAX_LINES line limit)"
        FOUND_LONG_FILES=1
    fi
done < <(find . -type f \
    -not -path "./venv/*" \
    -not -path "./.venv/*" \
    -not -path "./.deploy_venv/*" \
    -not -path "./.git/*" \
    -not -path "./build/*" \
    -not -path "./dist/*" \
    -not -path "./__pycache__/*" \
    -not -path "./*.egg-info/*" \
    -not -path "./.pytest_cache/*" \
    -not -path "./.mypy_cache/*" \
    -not -path "./.ruff_cache/*" \
    -not -path "$UV_CACHE_DIR_HYPHEN" \
    -not -path "$UV_CACHE_DIR_UNDERSCORE" \
    -not -path "./htmlcov/*" \
    -not -path "./reports/*" \
    -not -path "./node_modules/*" \
    -not -path "./llm-agent-tools/*" \
    -not -path "./.osgrep/*" \
    -not -path "./.pre-commit-cache/*" \
    -not -name "*.pyc" \
    -not -name "*.pyo" \
    -not -name "*.so" \
    -not -name "*.dylib" \
    -not -name "*.dll" \
    -not -name "*.log" \
    -not -name "*.sqlite" \
    -not -name "*.db" \
    -not -name "*.png" \
    -not -name "*.jpg" \
    -not -name "*.jpeg" \
    -not -name "*.gif" \
    -not -name "*.bmp" \
    -not -name "*.svg" \
    -not -name "*.ico" \
    -not -name "*.webp" \
    -not -name "*.md" \
    -not -name "*.lance" \
    -not -name ".coverage" \
    -not -name "uv.lock" \
    -not -name ".osgrepignore" \
    -not -name "models_registry.json" \
    -print0)

exit $FOUND_LONG_FILES
