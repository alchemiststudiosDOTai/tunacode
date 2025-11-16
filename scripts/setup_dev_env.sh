#!/usr/bin/env bash
# TunaCode developer environment bootstrapper
# - Uses uv for Python/tool installation
# - Creates a Hatch-managed virtual environment rooted at ./.venv
# - Installs dev dependencies via Hatch scripts

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${PROJECT_ROOT}/setup_dev_env.log"
VENV_DIR="${PROJECT_ROOT}/.venv"
HATCH_ENV_NAME="${HATCH_ENV_NAME:-default}"

export PATH="$HOME/.local/bin:$PATH"

exec > >(tee -a "$LOG_FILE") 2>&1

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    printf "%b[INFO]%b %s\n" "$BLUE" "$NC" "$1"
}

log_success() {
    printf "%b[SUCCESS]%b %s\n" "$GREEN" "$NC" "$1"
}

log_warn() {
    printf "%b[WARN]%b %s\n" "$YELLOW" "$NC" "$1"
}

log_error() {
    printf "%b[ERROR]%b %s\n" "$RED" "$NC" "$1" >&2
}

on_error() {
    log_error "Development environment setup failed."
    exit 1
}
trap on_error ERR

ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        UV_VERSION="$(uv --version 2>/dev/null)"
        log_success "UV detected (${UV_VERSION})."
        return
    fi

    log_warn "UV not found. Installing to \$HOME/.local/bin via official installer..."

    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        log_error "Install curl or wget to allow automatic UV installation."
        exit 1
    fi

    export PATH="$HOME/.local/bin:$PATH"

    if ! command -v uv >/dev/null 2>&1; then
        log_error "UV installation failed. Install it manually and re-run this script."
        exit 1
    fi

    log_success "UV installed successfully."
}

ensure_hatch() {
    if command -v hatch >/dev/null 2>&1; then
        log_success "Hatch detected ($(hatch --version))."
        return
    fi

    log_info "Installing Hatch via 'uv tool install hatch'..."
    uv tool install --upgrade hatch

    if ! command -v hatch >/dev/null 2>&1; then
        log_error "Failed to install Hatch with uv. Install it manually and retry."
        exit 1
    fi

    log_success "Hatch installed successfully."
}

log_info "🐟 Starting TunaCode developer environment setup"
log_info "Project root: ${PROJECT_ROOT}"
log_info "Log file: ${LOG_FILE}"

ensure_uv
ensure_hatch

log_info "Ensuring Hatch environment '${HATCH_ENV_NAME}' lives at ${VENV_DIR}"
if [ -d "$VENV_DIR" ] && [ "${FORCE_REBUILD:-false}" = "true" ]; then
    log_warn "FORCE_REBUILD flag set. Removing existing ${VENV_DIR}"
    rm -rf "$VENV_DIR"
fi

log_info "Creating/updating Hatch environment via Hatch (installer: uv)"
hatch env create "$HATCH_ENV_NAME"

log_info "Installing editable project + dev extras with uv (editable mode)"
uv pip install --python "${VENV_DIR}/bin/python" -e ".[dev]"

log_info "Verifying CLI entry point via Hatch-managed environment"
"${VENV_DIR}/bin/tunacode" --version

log_success "Developer environment ready!"
log_info "Activate it with: source ${VENV_DIR}/bin/activate"
log_info "Or open a Hatch shell: hatch shell"
