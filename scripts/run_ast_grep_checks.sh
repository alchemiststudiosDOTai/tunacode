#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config_path="$repo_root/rules/ast-grep/sgconfig.yml"
rules_dir="$repo_root/rules/ast-grep/rules"

if ! command -v npx >/dev/null 2>&1; then
    echo "npx is required to run ast-grep checks. Install Node.js and retry." >&2
    exit 1
fi

if [ ! -f "$config_path" ]; then
    echo "Missing ast-grep config: $config_path" >&2
    exit 1
fi

cd "$repo_root"

uv run python scripts/validate_ast_grep_rules.py "$rules_dir"/*.yml
npx --yes --package @ast-grep/cli ast-grep test --config "$config_path"
uv run python scripts/check_ast_grep_baseline.py
