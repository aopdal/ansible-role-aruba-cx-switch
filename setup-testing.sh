#!/usr/bin/env bash
# Setup script for testing infrastructure

set -e

echo "🚀 Setting up testing i# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup complete!"
echo ""
echo "🔐 Virtual Environment:"
echo "   Location: .venv/"
echo "   Activate: source .venv/bin/activate"
echo "   Deactivate: deactivate"
echo ""
echo "⚠️  IMPORTANT: Always activate the virtual environment before running tests!"
echo "   Run: source .venv/bin/activate"
echo ""
echo "📚 Next steps:"
echo "   - Review TESTING.md for detailed testing guide"
echo "   - Run 'make test' for full integration tests"
echo "   - Run 'pre-commit run --all-files' before commits"
echo "   - Check .github/workflows/ci.yml for CI/CD pipeline"
echo ""
echo "🔗 Quick commands (after activating venv):"
echo "   source .venv/bin/activate                     # Activate venv"
echo "   make lint                                     # Lint all"
echo "   make syntax                                   # Syntax check"
echo "   make molecule-test                            # Molecule tests"
echo "   make test-quick                               # Quick tests"
echo "   make test                                     # Full test suite"
echo ""
echo "Happy testing! 🎉"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"sible-role-aruba-cx-switch"
echo ""

# Check Python version
echo "📌 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Found Python $python_version"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install Python pip."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo ""
    echo "🔧 Creating virtual environment..."
    python3 -m venv .venv
    echo "   ✅ Virtual environment created at .venv/"
else
    echo ""
    echo "✅ Virtual environment already exists at .venv/"
fi

# Activate virtual environment
echo ""
echo "🔌 Activating virtual environment..."
source .venv/bin/activate
echo "   ✅ Virtual environment activated"

# Upgrade pip in venv
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1

# Install runtime dependencies
echo ""
echo "📦 Installing runtime dependencies (aoscx, netbox)..."
pip install -r requirements.txt

# Install test dependencies
echo ""
echo "📦 Installing test dependencies (pytest, molecule, etc.)..."
pip install -r requirements-test.txt

# Install Ansible collections
echo ""
echo "📦 Installing Ansible collections..."
ansible-galaxy collection install -r requirements.yml

# Check Docker (optional for Molecule)
echo ""
if command -v docker &> /dev/null; then
    echo "✅ Docker found - Molecule tests will work"
    docker --version
else
    echo "⚠️  Docker not found - Molecule tests will not work"
    echo "   Install Docker to run full test suite"
fi

# Setup pre-commit hooks
echo ""
echo "🪝 Setting up pre-commit hooks..."
if command -v pre-commit &> /dev/null; then
    pre-commit install
    echo "✅ Pre-commit hooks installed"
else
    echo "⚠️  pre-commit not found in PATH"
    echo "   Run: pip3 install pre-commit && pre-commit install"
fi

# Run initial tests
echo ""
echo "🧪 Running initial tests..."
echo ""

echo "1️⃣ YAML Lint..."
if yamllint . 2>/dev/null; then
    echo "   ✅ YAML lint passed"
else
    echo "   ⚠️  YAML lint found issues (check output above)"
fi

echo ""
echo "2️⃣ Ansible Lint..."
if ansible-lint 2>/dev/null; then
    echo "   ✅ Ansible lint passed"
else
    echo "   ⚠️  Ansible lint found issues (check output above)"
fi

echo ""
echo "3️⃣ Syntax Check..."
if ansible-playbook tests/test.yml -i tests/inventory --syntax-check 2>/dev/null; then
    echo "   ✅ Syntax check passed"
else
    echo "   ⚠️  Syntax check failed (check output above)"
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup complete!"
echo ""
echo "📚 Next steps:"
echo "   - Review TESTING.md for detailed testing guide"
echo "   - Run 'molecule test' for full integration tests"
echo "   - Run 'pre-commit run --all-files' before commits"
echo "   - Check .github/workflows/ci.yml for CI/CD pipeline"
echo ""
echo "🔗 Quick commands:"
echo "   yamllint .                                    # Lint YAML"
echo "   ansible-lint                                  # Lint Ansible"
echo "   ansible-playbook tests/test.yml --syntax-check # Syntax check"
echo "   molecule test                                 # Full test suite"
echo "   pre-commit run --all-files                    # Pre-commit checks"
echo ""
echo "Happy testing! 🎉"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
