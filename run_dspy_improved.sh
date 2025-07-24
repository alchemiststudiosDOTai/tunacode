#!/bin/bash

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    echo "OPENROUTER_API_KEY=your_api_key_here" > .env
    echo "⚠️  Please edit .env and add your OpenRouter API key"
    exit 1
fi

# Check if OpenRouter API key is set
if grep -q "your_api_key_here" .env; then
    echo "⚠️  Please edit .env and add your actual OpenRouter API key"
    echo "Get your API key from: https://openrouter.ai/keys"
    exit 1
fi

# Install required dependencies
echo "📦 Installing dependencies..."
pip install dspy-ai python-dotenv

# Run the improved DSPy implementation
echo "🚀 Running TunaCode DSPy Enhanced..."
python3 dspy_improved.py