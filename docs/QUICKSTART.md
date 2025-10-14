# 🚀 Quick Start Guide

Welcome to the Aruba AOS-CX Switch Ansible role development!

## Choose Your Path

### 🐳 Option 1: Dev Container (Recommended - 2 minutes)

**Best for most developers** - Everything is pre-configured!

1. ✅ Install [VS Code](https://code.visualstudio.com/)
2. ✅ Install [Docker Desktop](https://www.docker.com/get-started)
3. ✅ Install [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
4. ✅ Click "Reopen in Container" when VS Code prompts you
5. ✅ Wait 2-3 minutes for automatic setup
6. ✅ Start coding!

**That's it!** All dependencies are automatically installed.

### 📦 Option 2: Traditional Setup (5-10 minutes)

**For those without Docker:**

```bash
# Quick setup
./setup-testing.sh

# Then activate virtual environment
source .venv/bin/activate
```

## Test Your Setup

```bash
# Quick tests
make test-quick

# Full test suite
make test
```

## Common Commands

```bash
make test-quick              # Fast: lint + syntax
make test                    # Full: includes molecule
ansible-lint                 # Lint Ansible code
yamllint .                   # Lint YAML files
molecule test                # Full molecule test cycle
pre-commit run --all-files   # Run all pre-commit hooks
```

## Need Help?

📚 **Documentation:**
- [DEVELOPMENT.md](DEVELOPMENT.md) - Complete development guide
- [TESTING.md](TESTING.md) - Testing instructions
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [Main Documentation](index.md) - Role usage and features

🐛 **Issues?**
- Check [Troubleshooting section](DEVELOPMENT.md#troubleshooting)
- Open an issue on GitHub

---

**Ready to contribute?** See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Happy coding!** 🎉
