#!/bin/bash
# New Printer Installation Script for uv
set -e

echo "🚀 Setting up New Printer with uv"
echo "=================================="

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install it first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✅ Found uv: $(uv --version)"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    uv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment and install dependencies
echo "📥 Installing dependencies..."
uv pip install -e .

echo ""
echo "🧪 Testing installation..."

# Test basic import
uv run python -c "
try:
    import new_printer
    print('✅ New Printer modules loaded successfully')
except ImportError as e:
    print(f'❌ Import failed: {e}')
    exit(1)
"

# Test CLI
echo ""
echo "🔧 Testing CLI..."
uv run python -m new_printer.cli --help > /dev/null && echo "✅ CLI working" || echo "❌ CLI failed"

# Check dependencies
echo ""
echo "📋 Checking system dependencies..."
uv run python -m new_printer.cli info --check-deps

echo ""
echo "🎉 Installation complete!"
echo ""
echo "🚀 Next steps:"
echo "   1. Install system dependencies (Pandoc + LaTeX):"
echo "      macOS: brew install --cask basictex && brew install pandoc"
echo "      Ubuntu: sudo apt-get install pandoc texlive-latex-recommended"
echo ""
echo "   2. Test with a simple conversion:"
echo "      uv run python -m new_printer.cli convert https://example.com"
echo ""
echo "   3. Start web interface (optional):"
echo "      uv run python -m new_printer.cli serve --port 3000"
echo ""
echo "💡 To activate the environment manually:"
echo "   source .venv/bin/activate" 