#!/usr/bin/env bash

# Run the unimport dead-imports check with graceful fallbacks for older uv builds.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly -a UNIMPORT_ARGS=(
    --check
    --diff
    --exclude 'venv/*'
    --exclude '.venv/*'
    --exclude '.uv-cache/*'
    --exclude '.uv_cache/*'
    --gitignore
)

supports_uv_command() {
    local subcommand="$1"

    if ! command -v uv >/dev/null 2>&1; then
        return 1
    fi

    if uv --help 2>/dev/null | grep -qE "^[[:space:]]+${subcommand}([[:space:]]|$)"; then
        return 0
    fi

    return 1
}

run_with_uv_run() {
    if ! supports_uv_command "run"; then
        return 1
    fi

    uv run unimport "${UNIMPORT_ARGS[@]}" "$@"
}

run_with_uv_tool() {
    if ! supports_uv_command "tool"; then
        return 1
    fi

    uv tool run unimport "${UNIMPORT_ARGS[@]}" "$@"
}

run_with_venv_python() {
    local python_bin="${ROOT_DIR}/.venv/bin/python"

    if [ ! -x "${python_bin}" ]; then
        return 1
    fi

    "${python_bin}" -m unimport "${UNIMPORT_ARGS[@]}" "$@"
}

main() {
    if [ "$#" -eq 0 ]; then
        return 0
    fi

    if run_with_uv_run "$@"; then
        return 0
    fi

    if run_with_uv_tool "$@"; then
        return 0
    fi

    if run_with_venv_python "$@"; then
        return 0
    fi

    cat <<'EOF' >&2
ERROR: Unable to execute the dead-imports check.
Ensure uv >= 0.4 with the `run` subcommand, or install unimport into .venv.
EOF
    return 1
}

main "$@"
