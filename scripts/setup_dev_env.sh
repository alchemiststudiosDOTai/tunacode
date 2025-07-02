#!/usr/bin/env bash
# TunaCode Development Environment Setup
# 
# This script sets up a clean development environment for TunaCode
# It creates a fresh virtual environment and installs all dependencies

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

echo -e "${BLUE}TunaCode Development Environment Setup${NC}"
echo "=========================================="

# Change to project root
cd "$PROJECT_ROOT"

# Check Python version
PYTHON=${PYTHON:-python3}
if ! command -v "$PYTHON" &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found!${NC}"
    echo "Please install Python 3.10 or higher first."
    exit 1
fi

PYTHON_VERSION=$("$PYTHON" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if ! "$PYTHON" -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo -e "${RED}Error: Python 3.10 or higher required${NC}"
    echo "Found Python $PYTHON_VERSION"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"

# Check if venv exists and offer to recreate
if [ -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment already exists.${NC}"
    echo -e "Do you want to recreate it? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Removing existing virtual environment...${NC}"
        rm -rf venv
    else
        echo -e "${BLUE}Using existing virtual environment.${NC}"
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "\n${BLUE}Creating virtual environment...${NC}"
    "$PYTHON" -m venv venv
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${BLUE}Upgrading pip...${NC}"
pip install --upgrade pip --quiet

# Install the package in editable mode with dev dependencies
echo -e "${BLUE}Installing TunaCode in editable mode with dev dependencies...${NC}"
pip install -e ".[dev]" --quiet

# Install additional test dependencies
echo -e "${BLUE}Installing additional test dependencies...${NC}"
pip install pytest-asyncio --quiet

# Install pre-commit hooks
echo -e "${BLUE}Setting up pre-commit hooks...${NC}"
if command -v pre-commit &> /dev/null; then
    pre-commit install
    echo -e "${GREEN}✓${NC} Pre-commit hooks installed"
else
    echo -e "${YELLOW}Warning: pre-commit not found in PATH${NC}"
    echo -e "Run 'pre-commit install' manually after activation"
fi

# Verify installation
echo -e "\n${GREEN}✨ Development environment setup complete!${NC}"
echo -e "\nInstalled packages:"
echo -e "${BLUE}Python:${NC} $(venv/bin/python --version)"
echo -e "${BLUE}Black:${NC} $(venv/bin/black --version 2>&1 | head -1)"
echo -e "${BLUE}isort:${NC} $(venv/bin/isort --version 2>&1 | grep VERSION | cut -d' ' -f2)"
echo -e "${BLUE}flake8:${NC} $(venv/bin/flake8 --version 2>&1 | head -1)"
echo -e "${BLUE}pytest:${NC} $(venv/bin/pytest --version 2>&1 | head -1)"

echo -e "\n${GREEN}Available make commands:${NC}"
echo -e "  ${BLUE}make lint${NC}     - Run linting (black, isort, flake8)"
echo -e "  ${BLUE}make test${NC}     - Run tests"
echo -e "  ${BLUE}make coverage${NC} - Run tests with coverage"
echo -e "  ${BLUE}make build${NC}    - Build distribution packages"
echo -e "  ${BLUE}make clean${NC}    - Clean build artifacts"

echo -e "\n${YELLOW}Note:${NC} Activate the virtual environment with: ${GREEN}source venv/bin/activate${NC}"