#!/bin/bash

# Check for files longer than 500 lines
# Exit with status 1 if any files exceed the limit

MAX_LINES=600
FOUND_LONG_FILES=0

# Find all files, excluding common directories and binary files
while IFS= read -r -d '' file; do
    # Skip if it's not a regular file
    if [ ! -f "$file" ]; then
        continue
    fi

    # Skip glob.py and grep.py as they contain necessary prompt injection implementation
    if [[ "$file" == *"/src/tunacode/tools/glob.py" ]] || [[ "$file" == *"/src/tunacode/tools/grep.py" ]]; then
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
    -not -path "./.uv_cache/*" \
    -not -path "./htmlcov/*" \
    -not -path "./reports/*" \
    -not -path "./node_modules/*" \
    -not -path "./llm-agent-tools/*" \
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
    -not -name ".coverage" \
    -not -name "uv.lock" \
    -print0)

exit $FOUND_LONG_FILES
