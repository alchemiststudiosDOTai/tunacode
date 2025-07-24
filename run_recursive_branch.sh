#!/bin/bash

# Script to run the recursive-task-execution branch version of TunaCode

echo "🚀 Setting up recursive-task-execution branch of TunaCode..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "src/tunacode" ]; then
    echo "❌ Error: This script must be run from the TunaCode project root directory"
    exit 1
fi

# Ensure we're on the correct branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "feature/recursive-task-execution" ]; then
    echo "⚠️  Not on feature/recursive-task-execution branch"
    echo "Current branch: $CURRENT_BRANCH"
    echo "Switching to feature/recursive-task-execution..."
    git checkout feature/recursive-task-execution
    if [ $? -ne 0 ]; then
        echo "❌ Failed to switch branches"
        exit 1
    fi
fi

# Pull latest changes
echo "📥 Pulling latest changes..."
git pull origin feature/recursive-task-execution

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install -e ".[dev]" --upgrade

# Create an alias for this specific version
echo "💡 Creating alias 'tc-recursive' for this version..."
ALIAS_COMMAND="alias tc-recursive='cd $(pwd) && source venv/bin/activate && python -m tunacode'"

# Add to current session
eval "$ALIAS_COMMAND"

# Check if alias already exists in shell config
SHELL_CONFIG=""
if [ -f "$HOME/.bashrc" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
elif [ -f "$HOME/.zshrc" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
fi

if [ -n "$SHELL_CONFIG" ]; then
    if ! grep -q "alias tc-recursive=" "$SHELL_CONFIG"; then
        echo "" >> "$SHELL_CONFIG"
        echo "# TunaCode recursive branch alias" >> "$SHELL_CONFIG"
        echo "$ALIAS_COMMAND" >> "$SHELL_CONFIG"
        echo "✅ Added tc-recursive alias to $SHELL_CONFIG"
    fi
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎯 You can now run this version using:"
echo "   1. From this directory: python -m tunacode"
echo "   2. From anywhere (after restarting terminal): tc-recursive"
echo ""
echo "📋 Key features in this version:"
echo "   - Multi-turn recursive loop for complex tasks"
echo "   - Automatic task decomposition (threshold: 0.7)"
echo "   - Iteration budget management"
echo "   - Enhanced UI progress tracking"
echo ""
echo "🔧 Configuration options:"
echo "   - use_recursive_execution: true/false (default: true)"
echo "   - recursive_complexity_threshold: 0.0-1.0 (default: 0.7)"
echo "   - max_recursion_depth: 1-10 (default: 5)"
echo ""
echo "💡 To test recursive execution:"
echo "   1. Enable thoughts: /thoughts on"
echo "   2. Give a complex task like:"
echo "      'Build a REST API with authentication, CRUD operations, and tests'"
echo ""
echo "🚀 Starting TunaCode (recursive branch)..."
echo ""

# Run TunaCode
python -m tunacode