#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config_path="$repo_root/rules/ast-grep/sgconfig.yml"

cd "$repo_root"

npx --yes --package @ast-grep/cli ast-grep test --config "$config_path"
npx --yes --package @ast-grep/cli ast-grep scan --config "$config_path"
