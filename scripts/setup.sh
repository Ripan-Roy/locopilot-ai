#!/bin/bash

# Locopilot Setup Script
echo "🚀 Setting up Locopilot..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
    echo "✓ Python $python_version detected (>= 3.8 required)"
else
    echo "✗ Python 3.8+ required. Current version: $python_version"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "env" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv env
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source env/bin/activate

# Install dependencies
echo "📋 Installing dependencies..."
pip install -e .

# Run tests
echo "🧪 Running tests..."
python -m pytest tests/ -v

echo ""
echo "✅ Locopilot setup complete!"
echo ""
echo "Next steps:"
echo "1. Start Ollama:"
echo "   ollama serve && ollama pull codellama:latest"
echo ""
echo "2. Initialize Locopilot in your project:"
echo "   locopilot init"
echo ""
echo "3. Start coding with your AI assistant!"