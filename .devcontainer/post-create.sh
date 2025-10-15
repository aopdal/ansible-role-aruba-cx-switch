#!/bin/bash
set -e

echo "🔧 Running post-create setup..."

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install Python runtime requirements
if [ -f "requirements.txt" ]; then
    echo "📦 Installing runtime dependencies (aoscx, netbox)..."
    pip install -r requirements.txt
else
    echo "⚠️  requirements.txt not found, skipping..."
fi

# Install Python testing requirements
if [ -f "requirements-test.txt" ]; then
    echo "📦 Installing testing dependencies (pytest, molecule)..."
    pip install -r requirements-test.txt
else
    echo "⚠️  requirements-test.txt not found, skipping..."
fi

# Install Ansible collections
if [ -f "requirements.yml" ]; then
    echo "📦 Installing Ansible collections..."
    ansible-galaxy collection install -r requirements.yml --force
else
    echo "⚠️  requirements.yml not found, skipping..."
fi

# Install pre-commit hooks
if [ -f ".pre-commit-config.yaml" ]; then
    echo "🪝 Installing pre-commit hooks..."
    pre-commit install --install-hooks
else
    echo "⚠️  .pre-commit-config.yaml not found, skipping pre-commit setup..."
fi

# Create molecule symlink if needed
if [ -d "molecule/default" ]; then
    echo "🔗 Setting up molecule directories..."
    mkdir -p molecule/default/roles
fi

echo ""
echo "✅ Post-create setup complete!"
echo ""
echo "🚀 Quick Start Commands:"
echo "  • make test-quick      - Run quick tests (lint + syntax)"
echo "  • make test            - Run full test suite with molecule"
echo "  • molecule test        - Run molecule tests"
echo "  • ansible-lint         - Run Ansible linting"
echo "  • yamllint .           - Run YAML linting"
echo "  • pre-commit run -a    - Run all pre-commit checks"
echo ""
echo "📚 Documentation:"
echo "  • README.md            - Role overview and usage"
echo "  • TESTING.md           - Testing guide"
echo "  • DEVELOPMENT.md       - Development guide"
echo ""
