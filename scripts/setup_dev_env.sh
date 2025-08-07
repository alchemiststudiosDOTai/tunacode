#!/usr/bin/env bash
# TunaCode Development Environment Setup - Enhanced Version
#
# This script sets up a clean development environment for TunaCode
# with robust dependency verification and error handling
#
# Features:
# - Explicit dependency verification
# - Installation logging
# - Rollback on failure
# - Import tests for critical packages

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="$PROJECT_ROOT/setup_dev_env.log"
VENV_DIR="$PROJECT_ROOT/venv"

# Initialize log file
echo "TunaCode Development Environment Setup - $(date)" > "$LOG_FILE"

# Function to log messages
log() {
    echo -e "$@"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $*" | sed 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE"
}

# Function to check if a Python package can be imported
check_python_import() {
    local package="$1"
    local import_name="${2:-$1}"

    if "$VENV_DIR/bin/python" -c "import $import_name" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to verify critical dependencies
verify_dependencies() {
    log "${BLUE}Verifying critical dependencies...${NC}"

    local failed=false
    local critical_deps=(
        "pydantic_ai:pydantic_ai"
        "typer:typer"
        "prompt_toolkit:prompt_toolkit"
        "pygments:pygments"
        "rich:rich"
        "tiktoken:tiktoken"
        "pytest:pytest"
        "pytest_asyncio:pytest_asyncio"
    )

    for dep_spec in "${critical_deps[@]}"; do
        IFS=':' read -r package import_name <<< "$dep_spec"
        if check_python_import "$package" "$import_name"; then
            log "${GREEN}✓${NC} $package imported successfully"
        else
            log "${RED}✗${NC} Failed to import $package"
            failed=true
        fi
    done

    if [ "$failed" = true ]; then
        return 1
    fi
    return 0
}

# Function to install with retry and detailed error logging
install_with_retry() {
    local package="$1"
    local max_attempts=3
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        log "${BLUE}Installing $package (attempt $attempt/$max_attempts)...${NC}"

        if pip install "$package" 2>&1 | tee -a "$LOG_FILE"; then
            log "${GREEN}✓${NC} Successfully installed $package"
            return 0
        else
            log "${YELLOW}⚠${NC} Installation of $package failed on attempt $attempt"
            ((attempt++))
            if [ $attempt -le $max_attempts ]; then
                log "Retrying in 3 seconds..."
                sleep 3
            fi
        fi
    done

    log "${RED}✗${NC} Failed to install $package after $max_attempts attempts"
    return 1
}

# Cleanup function for rollback
cleanup_on_failure() {
    log "${RED}Installation failed. Rolling back...${NC}"
    if [ -d "$VENV_DIR" ] && [ "$VENV_CREATED" = true ]; then
        log "Removing incomplete virtual environment..."
        rm -rf "$VENV_DIR"
    fi
    log "${RED}Setup failed. Please check $LOG_FILE for details.${NC}"
    exit 1
}

# Set trap for cleanup on failure
trap cleanup_on_failure ERR

log "${BLUE}TunaCode Development Environment Setup${NC}"
log "=========================================="

# Change to project root
cd "$PROJECT_ROOT"

# Check Python version
PYTHON=${PYTHON:-python3}
if ! command -v "$PYTHON" &> /dev/null; then
    log "${RED}Error: Python 3 not found!${NC}"
    log "Please install Python 3.10 or higher first."
    exit 1
fi

PYTHON_VERSION=$("$PYTHON" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if ! "$PYTHON" -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
    log "${RED}Error: Python 3.10 or higher required${NC}"
    log "Found Python $PYTHON_VERSION"
    exit 1
fi

log "${GREEN}✓${NC} Python $PYTHON_VERSION found"

# Track if we created a new venv for rollback purposes
VENV_CREATED=false

# Check if venv exists and offer to recreate
if [ -d "$VENV_DIR" ]; then
    log "${YELLOW}Virtual environment already exists.${NC}"
    echo -e "Do you want to recreate it? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log "${BLUE}Removing existing virtual environment...${NC}"
        rm -rf "$VENV_DIR"
        VENV_CREATED=true
    else
        log "${BLUE}Using existing virtual environment.${NC}"
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    log "\n${BLUE}Creating virtual environment...${NC}"
    "$PYTHON" -m venv "$VENV_DIR"
    VENV_CREATED=true
fi

# Activate virtual environment
log "${BLUE}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

# Verify virtual environment is activated
if [ "$VIRTUAL_ENV" != "$VENV_DIR" ]; then
    log "${RED}Error: Failed to activate virtual environment${NC}"
    exit 1
fi
log "${GREEN}✓${NC} Virtual environment activated"

# Upgrade pip, setuptools, and wheel
log "${BLUE}Upgrading pip, setuptools, and wheel...${NC}"
if ! pip install --upgrade pip setuptools wheel 2>&1 | tee -a "$LOG_FILE"; then
    log "${RED}Failed to upgrade pip, setuptools, and wheel${NC}"
    cleanup_on_failure
fi
log "${GREEN}✓${NC} Successfully upgraded pip, setuptools, and wheel"

# Install critical dependency pydantic-ai first
log "${BLUE}Installing critical dependency: pydantic-ai...${NC}"
if ! install_with_retry "pydantic-ai[logfire]==0.2.6"; then
    log "${RED}Failed to install pydantic-ai - this is a critical dependency${NC}"
    cleanup_on_failure
fi

# Verify pydantic-ai installed correctly
if ! check_python_import "pydantic_ai" "pydantic_ai"; then
    log "${RED}pydantic-ai installed but cannot be imported!${NC}"
    log "This may indicate a version compatibility issue."
    cleanup_on_failure
fi

# Install the package in editable mode with dev dependencies
log "${BLUE}Installing TunaCode in editable mode with dev dependencies...${NC}"
if ! pip install -e ".[dev]" 2>&1 | tee -a "$LOG_FILE"; then
    log "${RED}Failed to install TunaCode package${NC}"
    cleanup_on_failure
fi

# Install additional test dependencies explicitly
log "${BLUE}Installing additional test dependencies...${NC}"
if ! install_with_retry "pytest-asyncio"; then
    log "${YELLOW}Warning: Failed to install pytest-asyncio${NC}"
fi

# Verify all dependencies
if ! verify_dependencies; then
    log "${RED}Dependency verification failed!${NC}"
    log "Some packages could not be imported. Check the log for details."
    log "${YELLOW}Attempting to diagnose the issue...${NC}"

    # Show installed packages
    log "\nInstalled packages:"
    pip list | tee -a "$LOG_FILE"

    # Try to get more info about pydantic-ai
    log "\nPydantic-AI installation details:"
    pip show pydantic-ai | tee -a "$LOG_FILE" || log "Could not get pydantic-ai info"

    cleanup_on_failure
fi

# Install pre-commit hooks
log "${BLUE}Setting up pre-commit hooks...${NC}"
if command -v pre-commit &> /dev/null; then
    pre-commit install
    log "${GREEN}✓${NC} Pre-commit hooks installed"
else
    log "${YELLOW}Warning: pre-commit not found in PATH${NC}"
    log "Run 'pre-commit install' manually after activation"
fi

# Test that the tunacode command is available
log "${BLUE}Verifying tunacode CLI installation...${NC}"
if "$VENV_DIR/bin/python" -m tunacode --version &>/dev/null; then
    log "${GREEN}✓${NC} tunacode CLI is properly installed"
else
    log "${RED}✗${NC} tunacode CLI not working properly"
    cleanup_on_failure
fi

# Final verification - run a simple test
log "${BLUE}Running basic import test...${NC}"
if "$VENV_DIR/bin/python" -c "from tunacode.cli.main import app; print('TunaCode imports working')" 2>&1 | tee -a "$LOG_FILE"; then
    log "${GREEN}✓${NC} Basic import test passed"
else
    log "${RED}✗${NC} Basic import test failed"
    cleanup_on_failure
fi

# Success! Clear the trap
trap - ERR

# Display summary
log "\n${GREEN}✨ Development environment setup complete!${NC}"
log "\nInstalled packages:"
log "${BLUE}Python:${NC} $("$VENV_DIR/bin/python" --version)"
log "${BLUE}pip:${NC} $("$VENV_DIR/bin/pip" --version | cut -d' ' -f2)"
log "${BLUE}pydantic-ai:${NC} $("$VENV_DIR/bin/pip" show pydantic-ai | grep Version | cut -d' ' -f2)"

# Show available commands
log "\n${GREEN}Available hatch commands:${NC}"
log "  ${BLUE}hatch run lint${NC}      - Run linting and formatting (ruff)"
log "  ${BLUE}hatch run test${NC}      - Run test suite"
log "  ${BLUE}hatch run coverage${NC}  - Run tests with coverage"
log "  ${BLUE}hatch build${NC}         - Build distribution packages"
log "  ${BLUE}hatch run clean${NC}     - Clean build artifacts"
log "\n${GREEN}Legacy make commands still supported (deprecated):${NC}"
log "  ${BLUE}make lint/test/build${NC} - Use hatch equivalents instead"

log "\n${YELLOW}Note:${NC} Activate the virtual environment with: ${GREEN}source venv/bin/activate${NC}"
log "\n${GREEN}Setup log saved to:${NC} $LOG_FILE"

# Run a quick test to ensure everything works
log "\n${BLUE}Running quick test suite verification...${NC}"
if cd "$PROJECT_ROOT" && "$VENV_DIR/bin/python" -m pytest tests/test_import.py -v 2>&1 | tee -a "$LOG_FILE"; then
    log "${GREEN}✓${NC} Test framework is working correctly"
else
    log "${YELLOW}⚠${NC} Test framework encountered issues - check the log"
fi
